# Create your views here.
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import Context,RequestContext

from django.contrib.auth.models import User

from django.views.generic import UpdateView

from members.forms import MemberForm

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from helpers.challenges import is_officer
from helpers.mixins import LoginRequiredMixin, OfficerMixin

@login_required
@user_passes_test(is_officer, login_url='/NOTOUCHING')
def officers(request):
    context = RequestContext(request)
    users = User.objects.filter(groups__name='Officer').order_by('last_name')
    
    context['users'] = users
    context['h2'] = "Officer List"
    
    return render_to_response('users.html', context)

@login_required
@user_passes_test(is_officer, login_url='/NOTOUCHING')
def active(request):
    context = RequestContext(request)
    users = User.objects.filter(groups__name='Active').order_by('last_name')
    
    context['users'] = users
    context['h2'] = "Active Members"
    
    return render_to_response('users.html', context)

@login_required
@user_passes_test(is_officer, login_url='/NOTOUCHING')
def associate(request):
    context = RequestContext(request)
    users = User.objects.filter(groups__name='Associate').order_by('last_name')
    
    context['users'] = users
    context['h2'] = "Associate Members"
    
    return render_to_response('users.html', context)

@login_required
@user_passes_test(is_officer, login_url='/NOTOUCHING')
def alum(request):
    context = RequestContext(request)
    users = User.objects.filter(groups__name='Alumni').order_by('last_name')
    
    context['users'] = users
    context['h2'] = "Alumni Members"
    
    return render_to_response('users.html', context)

@login_required
@user_passes_test(is_officer, login_url='/NOTOUCHING')
def away(request):
    context = RequestContext(request)
    users = User.objects.filter(groups__name='Away').order_by('last_name')
    
    context['users'] = users
    context['h2'] = "Inactive Members"
    
    return render_to_response('users.html', context)


@login_required
@user_passes_test(is_officer, login_url='/NOTOUCHING')
def contactusers(request):
    context = RequestContext(request)
    users = User.objects.filter(groups__name='Contact').order_by('last_name')
    
    context['users'] = users
    context['h2'] = "Contact Users"
    
    return render_to_response('users.html', context)


@login_required
@user_passes_test(is_officer, login_url='/NOTOUCHING')
def limbousers(request):
    context = RequestContext(request)
    users = User.objects.filter(groups__isnull=True)
    
    context['users'] = users
    context['h2'] = "Users Without Association"
    
    return render_to_response('users.html', context)


@login_required
@user_passes_test(is_officer, login_url='/NOTOUCHING')
def detail(request,id):
    context = RequestContext(request)
    user = get_object_or_404(User,pk=id)
    
    context['u'] = user
    return render_to_response('userdetail.html', context)



class UserUpdate(OfficerMixin,LoginRequiredMixin,UpdateView):
    model = User
    form_class = MemberForm
    template_name = "form_crispy_cbv.html"
    
    #def get_object(self,queryset=None):
        #return User.objects.get(pk=pk)
    def form_valid(self,form):
        messages.success(self.request,"Account Info Saved!", extra_tags='success')
        return super(UserUpdate,self).form_valid(form)