import datetime as dt

from unittest.mock import patch, Mock
from django.test import TestCase, Client, override_settings
from django.conf import settings

from parameterized import parameterized

from .forms import ChangeRequestForm, REASON_CHOICES


class BaseTestCase(TestCase):

    def setUp(self):
        self.test_post_data = {
            'name': 'Mr Smith',
            'department': 'test dept',
            'email': 'test@test.com',
            'telephone': '07700 TEST',
            'action': 'Add new content to Gov.uk',
            'description': 'a description',
            'due_date_0': dt.date.today().day,
            'due_date_1': dt.date.today().month,
            'due_date_2': dt.date.today().year,
            'date_explanation': 'ministerial visit',
            'time_due': 'time due',
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

    def test_due_date_is_optional(self):
        post_data = {k: v for k, v in self.test_post_data.items() if not k.startswith('due_date')}
        form = ChangeRequestForm(post_data)

        self.assertTrue(form.is_valid())

    def test_no_future_limit_on_date(self):
        year = dt.date.today().year
        post_data = self.test_post_data.copy()

        post_data['due_date_2'] = year + 1
        form = ChangeRequestForm(post_data)

        self.assertTrue(form.is_valid())

    @parameterized.expand((action_id,) for action_id, _ in REASON_CHOICES)
    @patch('feedback_form.forms.create_jira_issue')
    def test_jira_project_id(self, action_id, mock_create_jira_issue):

        mock_create_jira_issue.return_value = 'FAKE-JIRA-ID'

        assert settings.JIRA_CONTENT_PROJECT_ID != settings.JIRA_WORKSPACE_PROJECT_ID

        workspace_actions = [
            'Add new content to Digital Workspace',
            'Update or remove content on Digital Workspace'
        ]

        post_data = self.test_post_data.copy()
        post_data['action'] = action_id

        form = ChangeRequestForm(post_data)
        self.assertTrue(form.is_valid())

        form.create_jira_issue()

        project_id = settings.JIRA_WORKSPACE_PROJECT_ID if action_id in workspace_actions \
            else settings.JIRA_CONTENT_PROJECT_ID

        self.assertEquals(mock_create_jira_issue.call_args[0][0], project_id)


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

        submitted_date = '{}-{}-{}'.format(
            str(self.test_post_data['due_date_2']),
            str(self.test_post_data['due_date_1']).zfill(2),
            str(self.test_post_data['due_date_0']).zfill(2),
        )

        self.assertTrue(mock_create_jira_issue.called)
        mock_create_jira_issue.assert_called_with(
            settings.JIRA_CONTENT_PROJECT_ID, self.test_formatted_text, [])
