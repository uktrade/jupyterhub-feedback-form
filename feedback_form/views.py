import logging

from django.shortcuts import redirect
from django.views.generic.edit import FormView
from django.views.generic.base import TemplateView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError

from .forms import ChangeRequestForm
from authbroker_client.client import authbroker_login_required, get_profile


logger = logging.getLogger(__file__)


@method_decorator(authbroker_login_required, name="dispatch")
class ChangeRequestFormView(FormView):
    template_name = 'change_request.html'
    form_class = ChangeRequestForm
    success_url = reverse_lazy('success')

    def dispatch(self, request, *args, **kwargs):
        try:
            self._profile = get_profile(self.request)
        except TokenExpiredError:
            return redirect('authbroker_login')
        else:
            return super(ChangeRequestFormView, self).dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial['email'] = self._profile['email']
        initial['name'] = self._profile['first_name'] + ' ' + self._profile['last_name']
        return initial

    def form_valid(self, form):
        self.request._ticket_id = form.create_zendesk_ticket()
        return super().form_valid(form)

    def get_success_url(self):
        url = super().get_success_url()

        return f'{url}?issue={self.request._ticket_id}'


@method_decorator(authbroker_login_required, name="dispatch")
class ChangeRequestFormSuccessView(TemplateView):
    template_name = 'change_request_success.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['issue'] = self.request.GET.get('issue', 'Not specified')
        return context
