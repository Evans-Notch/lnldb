import datetime
import os
from io import BytesIO

from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.humanize.templatetags.humanize import intcomma
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from xhtml2pdf import pisa

from events.models import Category, Event, ExtraInstance
from projection.models import PITLevel, Projectionist

from .overlay import make_idt_single
from .utils import concat_pdf


# Convert HTML URIs to absolute system paths so xhtml2pdf can access those resources
def link_callback(uri, rel):
    # use short variable names
    surl = settings.STATIC_URL  # Typically /static/
    sroot = settings.STATIC_ROOT  # Typically /home/userX/project_static/
    murl = settings.MEDIA_URL  # Typically /static/media/
    mroot = settings.MEDIA_ROOT  # Typically /home/userX/project_static/media/

    # convert URIs to absolute system paths
    if murl and uri.startswith(murl):
        path = os.path.join(mroot, uri.replace(murl, ""))
    elif surl and uri.startswith(surl):
        search_url = uri.replace(surl, "")
        path = finders.find(search_url) or os.path.join(sroot, search_url)
    else:
        path = ""

    # make sure that file exists
    if not os.path.isfile(path):
        raise Exception('media URI must start with %s or %s' % (surl, murl))
    return path

@login_required
@permission_required("projection.view_pits", raise_exception=True)
def generate_projection_pdf(request):
    data = {}
    # prepare data
    levels = PITLevel.objects.exclude(name_short__in=['PP', 'L']).order_by('ordering')
    unlicensed_users = Projectionist.objects.exclude(pitinstances__pit_level__name_short__in=['PP', 'L'])
    licensed_users = Projectionist.objects.filter(pitinstances__pit_level__name_short__in=['PP', 'L']).exclude(
        user__groups__name="Alumni")
    alumni_users = Projectionist.objects.filter(pitinstances__pit_level__name_short__in=['PP', 'L']).filter(
        user__groups__name="Alumni")
    now = datetime.datetime.now(timezone.get_current_timezone())

    data['now'] = now
    data['unlicensed_users'] = unlicensed_users
    data['licensed_users'] = licensed_users
    data['alumni_users'] = alumni_users
    data['levels'] = levels

    # Render html content through html template with context
    html = render_to_string('pdf_templates/projection.html',
                            context=data,
                            request=request)
    if 'raw' in request.GET and bool(request.GET['raw']):
        return HttpResponse(html)
    # write file
    pdf_file = BytesIO()
    pisa.CreatePDF(html, dest=pdf_file, link_callback=link_callback)

    # return doc
    return HttpResponse(pdf_file.getvalue(), content_type='application/pdf')


@login_required
def generate_event_pdf(request, id):
    # Prepare context
    data = {}
    event = get_object_or_404(Event, pk=id)
    data['events'] = [event]

    # Render html content through html template with context
    html = render_to_string('pdf_templates/events.html',
                            context=data,
                            request=request)

    if 'raw' in request.GET and bool(request.GET['raw']):
        return HttpResponse(html)

    # Write PDF to file
    pdf_file = BytesIO()
    pisa.CreatePDF(html, dest=pdf_file, link_callback=link_callback)

    # Return PDF document through a Django HTTP response
    resp = HttpResponse(pdf_file.getvalue(), content_type='application/pdf')
    resp['Content-Disposition'] = 'inline; filename="%s.pdf"' % slugify(event.event_name)
    return resp


def currency(dollars):
    dollars = round(float(dollars), 2)
    return "$%s%s" % (intcomma(int(dollars)), ("%0.2f" % dollars)[-3:])


@login_required
def generate_event_bill_pdf(request, event):
    # Prepare context
    data = {}
    event = get_object_or_404(Event, pk=event)
    data['event'] = event
    cats = Category.objects.all()
    extras = {}
    for cat in cats:
        e_for_cat = ExtraInstance.objects.filter(event=event).filter(extra__category=cat)
        if len(e_for_cat) > 0:
            extras[cat] = e_for_cat
    data['extras'] = extras
    # Render html content through html template with context
    html = render_to_string('pdf_templates/bill-itemized.html',
                            context=data,
                            request=request)

    if 'raw' in request.GET and bool(request.GET['raw']):
        return HttpResponse(html)

    # Write PDF to file
    pdf_file = BytesIO()
    pisa.CreatePDF(html, dest=pdf_file, link_callback=link_callback)

    # if it's actually an invoice, attach an idt, eh?
    if event.reviewed and "invoiceonly" not in request.GET:
        idt = make_idt_single(event, request.user)
        pdf_file = concat_pdf(pdf_file, idt)

    # Return PDF document through a Django HTTP response
    resp = HttpResponse(pdf_file.getvalue(), content_type='application/pdf')
    resp['Content-Disposition'] = 'inline; filename="%s-bill.pdf"' % slugify(event.event_name)
    return resp


def generate_event_bill_pdf_standalone(event, idt_originator):
    data = {}
    data['event'] = event
    cats = Category.objects.all()
    extras = {}
    for cat in cats:
        e_for_cat = ExtraInstance.objects.filter(event=event).filter(extra__category=cat)
        if len(e_for_cat) > 0:
            extras[cat] = e_for_cat
    data['extras'] = extras
    # Render html content through html template with context
    html = render_to_string('pdf_templates/bill-itemized.html', context=data)

    # Write PDF to file
    pdf_file = BytesIO()
    pisa.CreatePDF(html, dest=pdf_file, link_callback=link_callback)

    # if it's actually an invoice, attach an idt, eh?
    if event.reviewed:
        idt = make_idt_single(event, idt_originator)
        pdf_file = concat_pdf(pdf_file, idt)

    return pdf_file.getvalue()


def generate_pdfs_standalone(ids=None):
    if ids is None:
        ids = []
    # returns a standalone pdf, for sending via email
    timezone.activate(timezone.get_current_timezone())

    data = {}
    events = Event.objects.filter(pk__in=ids)
    data['events'] = events

    html = render_to_string('pdf_templates/events.html',
                            context=data)

    pdf_file = BytesIO()
    pisa.CreatePDF(html, dest=pdf_file, link_callback=link_callback)

    return pdf_file.getvalue()


def generate_event_pdf_multi(request, ids=None):
    # this shoud fix UTC showing up in PDFs
    timezone.activate(timezone.get_current_timezone())

    if not ids:
        return HttpResponse("Should probably give some ids to return pdfs for..")
    # Prepare IDs
    idlist = ids.split(',')
    # Prepare context
    data = {}
    events = Event.objects.filter(pk__in=idlist)
    data['events'] = events

    # Render html content through html template with context
    html = render_to_string('pdf_templates/events.html',
                            context=data,
                            request=request)

    if 'raw' in request.GET and bool(request.GET['raw']):
        return HttpResponse(html)

    # Write PDF to file
    pdf_file = BytesIO()
    pisa.CreatePDF(html, dest=pdf_file, link_callback=link_callback)

    # Return PDF document through a Django HTTP response
    resp = HttpResponse(pdf_file.getvalue(), content_type='application/pdf')
    resp['Content-Disposition'] = 'inline; filename="events.pdf"'
    return resp
