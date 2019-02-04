import datetime as dt

from unittest.mock import patch, Mock
from django.test import TestCase, Client, override_settings
from django.conf import settings

from parameterized import parameterized
import requests_mock

from .forms import ChangeRequestForm


class BaseTestCase(TestCase):

    def setUp(self):
        self.test_post_data = {
            'name': 'Mr Smith',
            'email': 'test@test.com',
            'description': 'a description',
        }

        test_data = self.test_post_data.copy()

        test_data['due_date'] = dt.date.today()

        self.test_formatted_text = (
            'Name: {name}\n'
            'Email: {email}\n'
            'Description: {description}').format(**test_data)


class ChangeRequestFormViewTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()

        self.client = Client()

    def test_requires_auth(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/auth/login/')

    @requests_mock.mock()
    @patch('feedback_form.views.get_profile')
    @patch('authbroker_client.client.has_valid_token')
    def test_successful_submission(self, m, mock_has_valid_token, mock_get_profile):
        mock_has_valid_token.return_value = True
        m.post('https://desk.zendesk.com/api/v2/tickets.json', json={
            'ticket': {
                'id': 3543,
            },
            'audit': {
                'id': 1234,
            },
        })

        response = self.client.post('/', self.test_post_data)

        self.assertEqual(m.request_history[0].json()['ticket'], {
            'subject': 'JupyterHub feedback',
            'tags': ['jupyterhub'],
            'custom_fields': [
                {'id': 31281329, 'value': 'JupyterHub'},
                {'id': 45522485, 'value': 'test@test.com'},
            ],
            'description': self.test_formatted_text,
            'id': None,
            'requester': {
                'email': 'test@test.com',
                'name': 'Mr Smith',
                'id': None,    
            }
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/success/?issue=3543')
