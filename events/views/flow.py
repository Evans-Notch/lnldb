import datetime
from functools import wraps, partial
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.urlresolvers import reverse
from django.forms.models import inlineformset_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.generic import CreateView, DeleteView, UpdateView
from django.views.decorators.http import require_POST
from reversion.models import Version

from emails.generators import (ReportReminderEmailGenerator, EventEmailGenerator,
                               DefaultLNLEmailGenerator as DLEG)
from events.forms import (AttachmentForm, BillingForm, BillingUpdateForm, MultiBillingForm,
                          MultiBillingUpdateForm, CCIForm, CrewAssign, EventApprovalForm,
                          EventDenialForm, EventReviewForm, ExtraForm,
                          InternalReportForm, MKHoursForm, BillingEmailForm, MultiBillingEmailForm)
from events.models import (Billing, MultiBilling, BillingEmail, MultiBillingEmail, CCReport, Event,
                           EventArbitrary, EventAttachment, EventCCInstance, ExtraInstance, Hours,
                           ReportReminder)
from helpers.mixins import (ConditionalFormMixin, HasPermMixin, HasPermOrTestMixin,
                            LoginRequiredMixin, SetFormMsgMixin)
from pdfs.views import (generate_pdfs_standalone, generate_event_bill_pdf_standalone,
                        generate_multibill_pdf_standalone)


def curry_class(cls, *args, **kwargs):
    return wraps(cls)(partial(cls, *args, **kwargs))


@login_required
@permission_required('events.approve_event', raise_exception=True)
def approval(request, id):
    context = {}
    context['msg'] = "Approve Event"
    event = get_object_or_404(Event, pk=id)
    if not request.user.has_perm('events.approve_event', event):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    if event.approved:
        messages.add_message(request, messages.INFO, 'Event has already been approved!')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))

    if request.method == 'POST':
        form = EventApprovalForm(request.POST, instance=event)
        if form.is_valid():
            e = form.save(commit=False)
            e.approved = True
            e.approved_on = timezone.now()
            e.approved_by = request.user
            e.save()
            # confirm with user
            messages.add_message(request, messages.INFO, 'Approved Event')
            if e.contact and e.contact.email:
                email_body = 'Your event "%s" has been approved!' % event.event_name
                email = DLEG(subject="Event Approved", to_emails=[e.contact.email], body=email_body,
                             bcc=[settings.EMAIL_TARGET_VP])
                email.send()
            else:
                messages.add_message(request, messages.INFO,
                                     'No contact info on file for approval. Please give them the good news!')

            return HttpResponseRedirect(reverse('events:detail', args=(e.id,)))
        else:
            context['form'] = form
    else:
        # has a bill, but no paid bills, and is not otherwise closed
        unbilled_events = Event.objects.filter(org__in=event.org.all())\
                                       .exclude(billings__date_paid__isnull=False)\
                                       .filter(billings__date_billed__isnull=False)\
                                       .filter(closed=False)\
                                       .filter(cancelled=False)\
                                       .filter(test_event=False)\
                                       .distinct()
        unbilled_events = map(str, unbilled_events)
        if event.org.exists() and unbilled_events:
            messages.add_message(request, messages.WARNING, "Organization has unbilled events: %s" % ", ".join(unbilled_events))
        form = EventApprovalForm(instance=event)
        context['form'] = form
    return render(request, 'form_crispy.html', context)


@login_required
def denial(request, id):
    context = {}
    context['msg'] = "Deny Event"
    event = get_object_or_404(Event, pk=id)
    if not request.user.has_perm('events.decline_event', event):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    if event.cancelled:
        messages.add_message(request, messages.INFO, 'Event has already been cancelled!')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))

    if request.method == 'POST':
        form = EventDenialForm(request.POST, instance=event)
        if form.is_valid():
            e = form.save(commit=False)
            e.cancelled = True
            e.cancelled_by = request.user
            e.cancelled_on = timezone.now()
            e.closed = True
            e.closed_by = request.user
            e.closed_on = timezone.now()
            e.save()
            # confirm with user
            messages.add_message(request, messages.INFO, 'Denied Event')
            if e.contact and e.contact.email:
                email_body = 'Sorry, but your event "%s" has been denied. \n Reason: "%s"' % (
                    event.event_name, event.cancelled_reason)
                email = DLEG(subject="Event Denied", to_emails=[e.contact.email], body=email_body,
                             bcc=[settings.EMAIL_TARGET_VP])
                email.send()
            else:
                messages.add_message(request, messages.INFO,
                                     'No contact info on file for denial. Please give them the bad news.')
            return HttpResponseRedirect(reverse('events:detail', args=(e.id,)))
        else:
            context['form'] = form
    else:
        form = EventDenialForm(instance=event)
        context['form'] = form
    return render(request, 'form_crispy.html', context)


@login_required
def review(request, id):
    context = {}
    context['h2'] = "Review Event for Billing"
    event = get_object_or_404(Event, pk=id)
    if not request.user.has_perm('events.review_event', event):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    if event.reviewed:
        messages.add_message(request, messages.INFO, 'Event has already been reviewed!')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))

    context['event'] = event

    if request.method == 'POST':
        form = EventReviewForm(request.POST, instance=event, event=event)
        if form.is_valid():
            e = form.save(commit=False)
            e.reviewed = True
            e.reviewed_on = timezone.now()
            e.reviewed_by = request.user
            e.save()
            # confirm with user
            messages.add_message(request, messages.INFO, 'Event has been reviewed and is ready for billing!')

            return HttpResponseRedirect(reverse('events:detail', args=(e.id,)) + "#billing")
        else:
            context['formset'] = form
    else:
        form = EventReviewForm(instance=event, event=event)
        context['formset'] = form
    return render(request, 'event_review.html', context)


@login_required
def reviewremind(request, id, uid):
    event = get_object_or_404(Event, pk=id)
    if not (request.user.has_perm('events.review_event') or
            request.user.has_perm('events.review_event', event)):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    if event.reviewed or not event.approved:
        messages.add_message(request, messages.ERROR, 'Can only send reminders for an event that is approved and not reviewed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))

    cci = event.ccinstances.filter(crew_chief_id=uid)
    if cci:
        # only do heavy lifting if we need to

        pdf_handle = generate_pdfs_standalone([event.id])
        filename = "%s.workorder.pdf" % slugify(event.event_name)
        attachments = [{"file_handle": pdf_handle, "name": filename}]

        cci = cci[0]
        reminder = ReportReminder.objects.create(event=cci.event, crew_chief=cci.crew_chief)
        email = ReportReminderEmailGenerator(reminder=reminder, attachments=attachments)
        email.send()
        messages.add_message(request, messages.INFO, 'Reminder Sent')
        return HttpResponseRedirect(reverse("events:review", args=(event.id,)))
    else:
        return HttpResponse("Bad Call")


@require_POST
@login_required
def remindall(request, id):
    event = get_object_or_404(Event, pk=id)
    if not (request.user.has_perm('events.review_event') or
            request.user.has_perm('events.review_event', event)):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    if event.reviewed or not event.approved:
        messages.add_message(request, messages.ERROR, 'Can only send reminders for an event that is approved and not reviewed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))

    if event.num_crew_needing_reports == 0:
        messages.add_message(request, messages.INFO, 'All crew chiefs have already submitted reports.')
        return HttpResponseRedirect(reverse("events:review", args=(event.id,)))

    pdf_handle = generate_pdfs_standalone([event.id])
    filename = "%s.workorder.pdf" % slugify(event.event_name)
    attachments = [{"file_handle": pdf_handle, "name": filename}]

    for cci in event.crew_needing_reports:
        reminder = ReportReminder.objects.create(event=event, crew_chief=cci.crew_chief)
        email = ReportReminderEmailGenerator(reminder=reminder, attachments=attachments)
        email.send()

    messages.add_message(request, messages.INFO, 'Reminders sent to all crew chiefs needing reports for %s' % event.event_name)
    if 'next' in request.GET:
        return HttpResponseRedirect(request.GET['next'])
    else:
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))


@login_required
def close(request, id):
    context = {}
    context['msg'] = "Closing Event"
    event = get_object_or_404(Event, pk=id)
    if not request.user.has_perm('events.close_event', event):
        raise PermissionDenied
    event.closed = True
    event.closed_by = request.user
    event.closed_on = timezone.now()

    event.save()

    return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))


@login_required
def cancel(request, id):
    context = {}
    context['msg'] = "Event Cancelled"
    event = get_object_or_404(Event, pk=id)
    if not request.user.has_perm('events.cancel_event', event):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    event.cancelled = True
    event.cancelled_by = request.user
    event.cancelled_on = timezone.now()
    event.save()

    if event.contact and event.contact.email:
        targets = [event.contact.email]
    else:
        targets = []

    email_body = 'The event "%s" has been cancelled by %s. If this is incorrect, please contact our vice president at lnl-vp@wpi.edu.' % (event.event_name, str(request.user))
    if request.user.email:
        email_body = email_body[:-1]
        email_body += " or try them at %s." % request.user.email
    email = DLEG(subject="Event Cancelled", to_emails=targets, body=email_body, bcc=[settings.EMAIL_TARGET_VP])
    email.send()
    return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))


@login_required
def reopen(request, id):
    context = {}
    context['msg'] = "Event Reopened"
    event = get_object_or_404(Event, pk=id)
    if not request.user.has_perm('events.reopen_event', event):
        raise PermissionDenied
    event.closed = False
    event.closed_by = None
    event.closed_on = None

    event.save()

    return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))


@login_required
def rmcrew(request, id, user):
    event = get_object_or_404(Event, pk=id)
    if not (request.user.has_perm('events.edit_event_hours') or
            request.user.has_perm('events.edit_event_hours', event)):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    event.crew.remove(user)
    return HttpResponseRedirect(reverse("events:add-crew", args=(event.id,)))


@login_required
def assigncrew(request, id):
    context = {}
    context['msg'] = "Crew"

    event = get_object_or_404(Event, pk=id)
    if not (request.user.has_perm('events.edit_event_hours') or
            request.user.has_perm('events.edit_event_hours', event)):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    context['event'] = event

    if request.method == 'POST':
        formset = CrewAssign(request.POST, instance=event)
        if formset.is_valid():
            formset.save()
            return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
        else:
            context['formset'] = formset

    else:
        formset = CrewAssign(instance=event)

        context['formset'] = formset

    return render(request, 'form_crew_add.html', context)


@login_required
def hours_bulk_admin(request, id):
    context = {}

    context['msg'] = "Bulk Hours Entry"
    event = get_object_or_404(Event, pk=id)
    if not (request.user.has_perm('events.edit_event_hours') or
            request.user.has_perm('events.edit_event_hours', event) and event.reports_editable):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    context['event'] = event

    mk_hours_formset = inlineformset_factory(Event, Hours, extra=15, exclude=[])
    mk_hours_formset.form = curry_class(MKHoursForm, event=event)

    if request.method == 'POST':
        formset = mk_hours_formset(request.POST, instance=event)
        if formset.is_valid():
            formset.save()
            return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    else:
        formset = mk_hours_formset(instance=event)

    context['formset'] = formset
    return render(request, 'formset_hours_bulk.html', context)


@login_required
def rmcc(request, id, user):
    event = get_object_or_404(Event, pk=id)
    if not (request.user.has_perm('events.edit_event_hours') or
            request.user.has_perm('events.edit_event_hours', event)):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    event.crew_chief.remove(user)
    return HttpResponseRedirect(reverse("events:chiefs", args=(event.id,)))


@login_required
def assigncc(request, id):
    context = {}

    event = get_object_or_404(Event, pk=id)

    if not (request.user.has_perm('events.edit_event_hours') or
            request.user.has_perm('events.edit_event_hours', event)):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    context['event'] = event

    cc_formset = inlineformset_factory(Event, EventCCInstance, extra=5, exclude=[])
    cc_formset.form = curry_class(CCIForm, event=event)

    if request.method == 'POST':
        formset = cc_formset(request.POST, instance=event)
        if formset.is_valid():
            formset.save()
            return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
        else:
            context['formset'] = formset

    else:
        formset = cc_formset(instance=event)

        context['formset'] = formset

    return render(request, 'formset_crispy_helpers.html', context)


@login_required
def assignattach(request, id):
    context = {}

    event = get_object_or_404(Event, pk=id)
    if not (request.user.has_perm('events.event_attachments') or
            request.user.has_perm('events.event_attachments', event)):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    context['event'] = event

    att_formset = inlineformset_factory(Event, EventAttachment, extra=2, exclude=[])
    att_formset.form = curry_class(AttachmentForm, event=event)

    if request.method == 'POST':
        formset = att_formset(request.POST, request.FILES, instance=event)
        if formset.is_valid():
            formset.save()
            return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
        else:
            context['formset'] = formset

    else:
        formset = att_formset(instance=event)

        context['formset'] = formset

    return render(request, 'formset_crispy_attachments.html', context)


@login_required
def assignattach_external(request, id):
    context = {}

    event = get_object_or_404(Event, pk=id)
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))

    context['event'] = event

    mk_att_formset = inlineformset_factory(Event, EventAttachment, extra=1, exclude=[])
    # mk_att_formset.queryset = mk_att_formset.queryset.filter(externally_uploaded=True)
    mk_att_formset.form = curry_class(AttachmentForm, event=event, externally_uploaded=True)

    if request.method == 'POST':
        formset = mk_att_formset(request.POST, request.FILES, instance=event,
                                 queryset=EventAttachment.objects.filter(externally_uploaded=True))
        if formset.is_valid():
            f = formset.save(commit=False)
            for i in f:
                i.externally_uploaded = True
                i.save()
            return HttpResponseRedirect(reverse('my:workorders', ))
        else:
            context['formset'] = formset

    else:
        formset = mk_att_formset(instance=event, queryset=EventAttachment.objects.filter(externally_uploaded=True))

        context['formset'] = formset

    return render(request, 'formset_crispy_attachments.html', context)


@login_required
def extras(request, id):
    """ This form is for adding extras to an event """
    context = {}
    context['msg'] = "Extras"

    event = get_object_or_404(Event, pk=id)

    if not (request.user.has_perm('events.adjust_event_charges') or
            request.user.has_perm('events.adjust_event_charges', event)):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    context['event'] = event

    mk_extra_formset = inlineformset_factory(Event, ExtraInstance, extra=1, exclude=[])
    mk_extra_formset.form = ExtraForm

    if request.method == 'POST':
        formset = mk_extra_formset(request.POST, request.FILES, instance=event)
        if formset.is_valid():
            formset.save()
            return HttpResponseRedirect(reverse('events:detail', args=(event.id,)) + "#billing")
        else:
            context['formset'] = formset

    else:
        formset = mk_extra_formset(instance=event)

        context['formset'] = formset

    return render(request, 'formset_crispy_extras.html', context)


@login_required
def oneoff(request, id):
    """ This form is for adding oneoff fees to an event """
    context = {}
    context['msg'] = "One-Off Charges"

    event = get_object_or_404(Event, pk=id)
    context['event'] = event

    if not (request.user.has_perm('events.adjust_event_charges') or
            request.user.has_perm('events.adjust_event_charges', event)):
        raise PermissionDenied
    if event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))

    mk_oneoff_formset = inlineformset_factory(Event, EventArbitrary, extra=3, exclude=[])

    if request.method == 'POST':
        formset = mk_oneoff_formset(request.POST, request.FILES, instance=event)
        if formset.is_valid():
            formset.save()
            return HttpResponseRedirect(reverse('events:detail', args=(event.id,)) + "#billing")
        else:
            context['formset'] = formset

    else:
        formset = mk_oneoff_formset(instance=event)

        context['formset'] = formset

    return render(request, 'formset_crispy_arbitrary.html', context)


@login_required
def viewevent(request, id):
    context = {}
    event = get_object_or_404(Event, pk=id)
    if not (request.user.has_perm('events.view_event') or request.user.has_perm('events.view_event', event)):
        raise PermissionDenied

    context['event'] = event
    context['history'] = Version.objects.get_for_object(event).get_unique()
    return render(request, 'uglydetail.html', context)


class CCRCreate(SetFormMsgMixin, HasPermOrTestMixin, ConditionalFormMixin, LoginRequiredMixin, CreateView):
    model = CCReport
    form_class = InternalReportForm
    template_name = "form_crispy_cbv.html"
    msg = "New Crew Chief Report"
    perms = 'events.add_event_report'

    def dispatch(self, request, *args, **kwargs):
        self.event = get_object_or_404(Event, pk=kwargs['event'])
        return super(CCRCreate, self).dispatch(request, *args, **kwargs)

    def user_passes_test(self, request, *args, **kwargs):
        return self.event.reports_editable and request.user.has_perm(self.perms, self.event)

    def get_form_kwargs(self):
        kwargs = super(CCRCreate, self).get_form_kwargs()
        kwargs['event'] = self.event
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Crew Chief Report Created!", extra_tags='success')
        return super(CCRCreate, self).form_valid(form)

    def get_success_url(self):
        return reverse("events:detail", args=(self.kwargs['event'],))


class CCRUpdate(SetFormMsgMixin, ConditionalFormMixin, HasPermMixin, LoginRequiredMixin, UpdateView):
    model = CCReport
    form_class = InternalReportForm
    template_name = "form_crispy_cbv.html"
    msg = "Update Crew Chief Report"
    perms = 'events.change_ccreport'

    def get_form_kwargs(self):
        kwargs = super(CCRUpdate, self).get_form_kwargs()
        event = get_object_or_404(Event, pk=self.kwargs['event'])
        kwargs['event'] = event
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Crew Chief Report Updated!", extra_tags='success')
        return super(CCRUpdate, self).form_valid(form)

    def get_success_url(self):
        return reverse("events:detail", args=(self.kwargs['event'],))


class CCRDelete(SetFormMsgMixin, HasPermMixin, LoginRequiredMixin, DeleteView):
    model = CCReport
    template_name = "form_delete_cbv.html"
    msg = "Deleted Crew Chief Report"
    perms = 'events.delete_ccreport'

    def get_object(self, queryset=None):
        """ Hook to ensure object isn't closed """
        obj = super(CCRDelete, self).get_object()
        if obj.event.closed:
            raise ValidationError("Event is closed")
        else:
            return obj

    def get_success_url(self):
        return reverse("events:detail", args=(self.kwargs['event'],))


class BillingCreate(SetFormMsgMixin, HasPermMixin, LoginRequiredMixin, CreateView):
    model = Billing
    form_class = BillingForm
    template_name = "form_crispy_cbv.html"
    msg = "New Bill"
    perms = 'events.bill_event'

    def get_context_data(self, **kwargs):
        context = super(BillingCreate, self).get_context_data(**kwargs)
        event = get_object_or_404(Event, pk=self.kwargs['event'])
        if event.closed:
            raise PermissionDenied
        orgs = event.org.all()
        orgstrings = ",".join(["%s's billing account was last verified: %s" % (
            o.name, o.verifications.latest().date if o.verifications.exists() else "Never") for o in orgs])
        context['extra'] = orgstrings
        return context

    def get_form_kwargs(self):
        # pass "user" keyword argument with the current user to your form
        kwargs = super(BillingCreate, self).get_form_kwargs()
        event = get_object_or_404(Event, pk=self.kwargs['event'])
        kwargs['event'] = event
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Bill Created!", extra_tags='success')
        return super(BillingCreate, self).form_valid(form)

    def get_success_url(self):
        if 'save-and-make-email' in self.request.POST:
            return reverse("events:bills:email", args=(self.kwargs['event'], self.object.pk))
        else:
            return reverse("events:detail", args=(self.kwargs['event'],)) + "#billing"


class BillingUpdate(SetFormMsgMixin, HasPermMixin, LoginRequiredMixin, UpdateView):
    model = Billing
    form_class = BillingUpdateForm
    template_name = "form_crispy_cbv.html"
    msg = "Update Bill"
    perms = 'events.bill_event'

    def get_object(self, *args, **kwargs):
        """ Validate preconditions for editing a bill """
        obj = super(BillingUpdate, self).get_object(*args, **kwargs)
        if obj.event.closed:
            raise PermissionDenied
        else:
            return obj

    def get_form_kwargs(self):
        kwargs = super(BillingUpdate, self).get_form_kwargs()
        event = get_object_or_404(Event, pk=self.kwargs['event'])
        kwargs['event'] = event
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Billing Updated!", extra_tags='success')
        return super(BillingUpdate, self).form_valid(form)

    def get_success_url(self):
        return reverse("events:detail", args=(self.kwargs['event'],)) + "#billing"


class BillingDelete(HasPermMixin, LoginRequiredMixin, DeleteView):
    model = Billing
    template_name = "form_delete_cbv.html"
    msg = "Deleted Bill"
    perms = 'events.bill_event'

    def get_object(self, *args, **kwargs):
        """ Validate preconditions for deleting a bill """
        obj = super(BillingDelete, self).get_object(*args, **kwargs)
        if obj.date_paid:
            raise PermissionDenied
        if obj.event.closed:
            raise PermissionDenied
        else:
            return obj

    def get_success_url(self):
        return reverse("events:detail", args=(self.kwargs['event'],)) + "#billing"


class MultiBillingCreate(SetFormMsgMixin, HasPermMixin, LoginRequiredMixin, CreateView):
    model = MultiBilling
    form_class = MultiBillingForm
    template_name = "form_crispy.html"
    msg = "New MultiBill"
    perms = 'events.bill_event'

    def form_valid(self, form):
        messages.success(self.request, "MultiBill Created!", extra_tags='success')
        return super(MultiBillingCreate, self).form_valid(form)

    def get_success_url(self):
        if 'save-and-make-email' in self.request.POST:
            return reverse("events:multibillings:email", args=(self.object.pk,))
        else:
            return reverse("events:multibillings:list")


class MultiBillingUpdate(SetFormMsgMixin, HasPermMixin, LoginRequiredMixin, UpdateView):
    model = MultiBilling
    form_class = MultiBillingUpdateForm
    template_name = "form_crispy.html"
    msg = "Update MultiBill"
    perms = 'events.bill_event'

    def get_object(self, *args, **kwargs):
        """ Validate preconditions for editing a multibill """
        obj = super(MultiBillingUpdate, self).get_object(*args, **kwargs)
        if obj.events.filter(closed=True).exists():
            raise PermissionDenied
        else:
            return obj

    def form_valid(self, form):
        messages.success(self.request, "MultiBill Updated!", extra_tags='success')
        return super(MultiBillingUpdate, self).form_valid(form)

    def get_success_url(self):
        return reverse("events:multibillings:list")


class MultiBillingDelete(HasPermMixin, LoginRequiredMixin, DeleteView):
    model = MultiBilling
    template_name = "form_delete_cbv.html"
    msg = "Delete MultiBill"
    perms = 'events.bill_event'

    def get_object(self, *args, **kwargs):
        """ Validate preconditions for deleting a multibill """
        obj = super(MultiBillingDelete, self).get_object(*args, **kwargs)
        if obj.date_paid:
            raise PermissionDenied
        if obj.events.filter(closed=True).exists():
            raise PermissionDenied
        else:
            return obj

    def get_success_url(self):
        return reverse("events:multibillings:list")


@require_POST
@login_required
def pay_bill(request, event, pk):
    """
    Quietly pays a bill, showing a message on the next page. POST only
    """
    bill = get_object_or_404(Billing, event_id=event, id=pk)
    if not request.user.has_perm('events.bill_event', bill.event):
        raise PermissionDenied
    if bill.event.closed:
        messages.add_message(request, messages.ERROR, 'Event is closed.')
        return HttpResponseRedirect(reverse('events:detail', args=(event.id,)))
    if bill.date_paid:
        messages.info(request, "Bill has already been paid", extra_tags="info")
    else:
        bill.date_paid = timezone.now()
        bill.save()
        if 'next' in request.GET:
            messages.success(request, "Marked latest bill paid for %s" % bill.event.event_name, extra_tags="success")
        else:
            messages.success(request, "Bill paid!", extra_tags="success")
    if 'next' in request.GET:
        return HttpResponseRedirect(request.GET['next'])
    else:
        return HttpResponseRedirect(reverse('events:detail', args=(bill.event_id,)) + "#billing")


class BillingEmailCreate(SetFormMsgMixin, HasPermMixin, LoginRequiredMixin, CreateView):
    model = BillingEmail
    form_class = BillingEmailForm
    template_name = "form_crispy.html"
    msg = "New Billing Email"
    perms = 'events.bill_event'

    def dispatch(self, request, *args, **kwargs):
        self.billing = get_object_or_404(Billing, pk=self.kwargs['billing'])
        return super(BillingEmailCreate, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        # pass "user" keyword argument with the current user to your form
        kwargs = super(BillingEmailCreate, self).get_form_kwargs()
        kwargs['billing'] = self.billing
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Billing Email Created!", extra_tags='success')
        response = super(BillingEmailCreate, self).form_valid(form)
        # send the email
        i = form.instance
        event = self.billing.event
        to = list(i.email_to_users.values_list('email', flat=True))
        to.extend(list(i.email_to_orgs.values_list('exec_email', flat=True)))
        pdf_handle = generate_event_bill_pdf_standalone(event, self.request.user)
        filename = "%s-bill.pdf" % slugify(event.event_name)
        attachments = [{"file_handle": pdf_handle, "name": filename}]
        email = EventEmailGenerator(event=event, subject=i.subject, body=i.message,
                                    to_emails=to, bcc=[settings.EMAIL_TARGET_T], attachments=attachments)
        email.send()
        i.sent_at = timezone.now()
        i.save()
        return response

    def get_success_url(self):
        return reverse("events:detail", args=(self.billing.event_id,)) + "#billing"


class MultiBillingEmailCreate(SetFormMsgMixin, HasPermMixin, LoginRequiredMixin, CreateView):
    model = MultiBillingEmail
    form_class = MultiBillingEmailForm
    template_name = "form_crispy.html"
    msg = "New Billing Email"
    perms = 'events.bill_event'

    def dispatch(self, request, *args, **kwargs):
        self.multibilling = get_object_or_404(MultiBilling, pk=self.kwargs['multibilling'])
        return super(MultiBillingEmailCreate, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        # pass "user" keyword argument with the current user to your form
        kwargs = super(MultiBillingEmailCreate, self).get_form_kwargs()
        kwargs['multibilling'] = self.multibilling
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Billing Email Created!", extra_tags='success')
        response = super(MultiBillingEmailCreate, self).form_valid(form)
        # send the email
        i = form.instance
        to = list(i.email_to_users.values_list('email', flat=True))
        to.extend(list(i.email_to_orgs.values_list('exec_email', flat=True)))
        pdf_handle = generate_multibill_pdf_standalone(self.multibilling, self.request.user)
        filename = "bill.pdf"
        attachments = [{"file_handle": pdf_handle, "name": filename}]
        email = DLEG(subject=i.subject, body=i.message, to_emails=to, bcc=[settings.EMAIL_TARGET_T],
                     attachments=attachments)
        email.send()
        i.sent_at = timezone.now()
        i.save()
        return response

    def get_success_url(self):
        return reverse("events:multibillings:list")
