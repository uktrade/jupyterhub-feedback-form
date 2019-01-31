import json
import datetime as dt

from django import forms
from django.conf import settings
from django.utils.safestring import mark_safe
from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket, CustomField, Comment

from jira import JIRA
from govuk_forms.forms import GOVUKForm
from govuk_forms import widgets, fields
import requests

from .fields import AVFileField


def create_jira_issue(project_id, issue_text, attachments, **extra_fields):
    jira_client = JIRA(
        settings.JIRA_URL,
        basic_auth=(settings.JIRA_USERNAME, settings.JIRA_PASSWORD))

    issue_dict = {
        'project': {'id': project_id},
        'summary': 'New change request',
        'description': issue_text,
        'issuetype': {'name': 'Task'},
        'priority': {'name': 'Medium'},
    }

    if extra_fields:
        issue_dict.update(extra_fields)

    issue = jira_client.create_issue(fields=issue_dict)

    for attachment in attachments:
        jira_client.add_attachment(issue=issue, attachment=attachment, filename=attachment.name)

    for watcher_username in settings.JIRA_WATCHERS:
        jira_client.add_watcher(issue, watcher_username)

    return issue.key


REASON_CHOICES = (
    ('Add new content to Gov.uk', 'Add new content to Gov.uk'),
    ('Update or remove content on Gov.uk', 'Update or remove content on Gov.uk'),
    ('Add new content to Great.gov.uk', 'Add new content to Great.gov.uk'),
    ('Update or remove content on Great.gov.uk', 'Update or remove content on Great.gov.uk'),
    ('Add new content to Digital Workspace', 'Add new content to Digital Workspace'),
    ('Update or remove content on Digital Workspace', 'Update or remove content on Digital Workspace'),
)


REASON_CHOICES_JIRA_PROJECT_MAP = {
    'Add new content to Gov.uk': settings.JIRA_CONTENT_PROJECT_ID,
    'Update or remove content on Gov.uk': settings.JIRA_CONTENT_PROJECT_ID,
    'Add new content to Great.gov.uk': settings.JIRA_CONTENT_PROJECT_ID,
    'Update or remove content on Great.gov.uk': settings.JIRA_CONTENT_PROJECT_ID,
    'Add new content to Digital Workspace': settings.JIRA_WORKSPACE_PROJECT_ID,
    'Update or remove content on Digital Workspace': settings.JIRA_WORKSPACE_PROJECT_ID,
}


JIRA_FIELD_MAPPING = {
    'name': 'customfield_11227',
    'email': 'customfield_11225',
    'department': 'customfield_11224',
    'action': {'field': 'customfield_11228', 'type': 'select'}
}


class ChangeRequestForm(GOVUKForm):
    name = forms.CharField(
        label='Your full name',
        max_length=255,
        widget=widgets.TextInput()
    )

    email = forms.EmailField(
        label='Your email address',
        widget=widgets.TextInput()
    )

    telephone = forms.CharField(
        label='Phone number',
        max_length=255,
        widget=widgets.TextInput(),
        help_text='Please provide a direct number in case we need to discuss your feedback.'
    )

    action = forms.ChoiceField(
        label='Do you want to add, update or remove content?',
        choices=REASON_CHOICES,
        help_text='Please allow a minimum of 3 working days to allow for feedback, approval and upload.',
        widget=widgets.RadioSelect(),
    )

    description = forms.CharField(
        label='What\'s your feedback?',
        widget=widgets.Textarea(),
        help_text=mark_safe(
            'If you\'re reporting a bug, please include'
            '<ol>'
            '<li>1. Enough step by step instructions for us to experience the bug: so we know what to fix.</li>'
            '<li>2. What you\'ve already tried: we don\'t want to waste time by suggesting these.</li>'
            '<li>3. Your aim: we may have an alternative.</li>'
            '</ol>'
        )
    )

    attachment1 = AVFileField(
        label='Please attach screenshots or small data files. Do not submit sensitive data.',
        max_length=255,
        widget=widgets.ClearableFileInput(),
        required=False
    )

    attachment2 = AVFileField(
        label='',
        max_length=255,
        widget=widgets.ClearableFileInput(),
        help_text='',
        required=False
    )

    attachment3 = AVFileField(
        label='',
        max_length=255,
        widget=widgets.ClearableFileInput(),
        help_text='',
        required=False
    )

    attachment4 = AVFileField(
        label='',
        max_length=255,
        widget=widgets.ClearableFileInput(),
        help_text='',
        required=False
    )

    attachment5 = AVFileField(
        label='',
        max_length=255,
        widget=widgets.ClearableFileInput(),
        help_text='',
        required=False
    )

    def formatted_text(self):
        return ('Name: {name}\n'
                'Email: {email}\n'
                'Telephone: {telephone}\n'
                'Description: {description}'.format(**self.cleaned_data))

    def create_jira_issue(self):

        attachments = [value for field, value in self.cleaned_data.items() if field.startswith('attachment') if value]

        project_id = REASON_CHOICES_JIRA_PROJECT_MAP[self.cleaned_data['action']]

        jira_id = create_jira_issue(
            project_id, self.formatted_text(), attachments)

        jira_url = settings.JIRA_ISSUE_URL.format(jira_id)

        return jira_id

    def create_zendesk_ticket(self):
        zenpy_client = Zenpy(
            subdomain=settings.ZENDESK_SUBDOMAIN,
            email=settings.ZENDESK_EMAIL,
            token=settings.ZENDESK_TOKEN,
        )

        custom_fields = {
            CustomField(id=30041969, value='Content Delivery'),                         # service
            CustomField(id=360000180437, value=self.cleaned_data['department']),        # directorate
            CustomField(id=45522485, value=self.cleaned_data['email']),                 # email
            CustomField(id=360000188178, value=self.cleaned_data['telephone']),         # Phone number
            CustomField(id=360000182638, value=self.cleaned_data['action']),            # Content request
            CustomField(id=360000180477, value=self.cleaned_data['date_explanation']),  # reason
        }

        ticket = zenpy_client.tickets.create(Ticket(
            subject='Content change request',
            description=self.formatted_text(),
            custom_fields=custom_fields,
            tags=['content delivery']
        )).ticket

        attachments = [value for field, value in self.cleaned_data.items() if field.startswith('attachment') and value]

        if attachments:
            uploads = []
            for attachment in attachments:
                upload_instance = zenpy_client.attachments.upload(attachment.temporary_file_path())
                uploads.append(upload_instance.token)

            ticket.comment = Comment(body=str(attachment), uploads=uploads)

            zenpy_client.tickets.update(ticket)

        return ticket.id