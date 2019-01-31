import datetime as dt

from unittest.mock import patch, Mock
from django.test import TestCase, Client, override_settings
from django.conf import settings

from parameterized import parameterized

from .forms import ChangeRequestForm


class BaseTestCase(TestCase):

    def setUp(self):
        self.test_post_data = {
            'name': 'Mr Smith',
            'email': 'test@test.com',
            'telephone': '07700 TEST',
            'description': 'a description',
        }

        test_data = self.test_post_data.copy()

        test_data['due_date'] = dt.date.today()

        self.test_formatted_text = (
            'Name: {name}\n'
            'Email: {email}\n'
            'Telephone: {telephone}\n'
            'Description: {description}').format(**test_data)


class ChangeRequestFormTestCase(BaseTestCase):
    def test_valid_data(self):

        form = ChangeRequestForm(self.test_post_data)
        self.assertTrue(form.is_valid())

    def test_formatted_text(self):
        form = ChangeRequestForm(self.test_post_data)
        form.is_valid()

        self.assertEqual(
            form.formatted_text(),
            self.test_formatted_text)


class ChangeRequestFormViewTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()

        self.client = Client()

    def test_requires_auth(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/auth/login/')

    @patch('feedback_form.views.get_profile')
    @patch('authbroker_client.client.has_valid_token')
    @patch('feedback_form.forms.create_jira_issue')
    @override_settings(JIRA_ISSUE_URL='http://jira_url/?selectedIssue={}')
    def test_successful_submission(self, mock_create_jira_issue, mock_has_valid_token, mock_get_profile):
        mock_has_valid_token.return_value = True
        mock_create_jira_issue.return_value = 'FAKE-JIRA-ID'

        response = self.client.post('/', self.test_post_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/success/?issue=FAKE-JIRA-ID')

        self.assertTrue(mock_create_jira_issue.called)
        mock_create_jira_issue.assert_called_with(self.test_formatted_text, [])
