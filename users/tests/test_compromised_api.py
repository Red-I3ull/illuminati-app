import os
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from unittest.mock import patch
from django.db import DatabaseError
from users.compromised_api import CompromisedViewSet
from users.models import CustomUser, Marker, EntryPassword
from dotenv import load_dotenv
load_dotenv()

class CompromisedViewSetTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CompromisedViewSet.as_view({'post': 'create'})

        test_password = os.environ.get('TEST_PASSWORD')
        self.user = CustomUser.objects.create_user(
            username='architect',
            email='architect@example.com',
            password=test_password,
        )

        self.user.role = 'ARCHITECT'
        self.user.save()

        self.marker1 = Marker.objects.create(name='Marker 1', lat=1.0, lng=1.0)
        self.marker2 = Marker.objects.create(name='Marker 2', lat=2.0, lng=2.0)

        self.entry_pw_active = EntryPassword.objects.create(password='abc123', is_active=True)

    def test_compromised_success(self):
        """Test successful compromised protocol execution"""
        request = self.factory.post('/compromised/')
        force_authenticate(request, user=self.user)
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['message'], 'Compromise protocol initiated')

        self.assertEqual(Marker.objects.count(), 0)
        self.assertEqual(EntryPassword.objects.filter(is_active=True).count(), 0)

        updated_user = CustomUser.objects.get(id=self.user.id)
        self.assertEqual(updated_user.password, ' ')
        self.assertIsNone(updated_user.username)

    @patch('users.compromised_api.Marker.objects.all')
    def test_compromised_database_error(self, mock_marker_all):
        """Test database error handling in compromised endpoint"""
        mock_marker_all.side_effect = DatabaseError("DB failure")

        request = self.factory.post('/compromised/')
        force_authenticate(request, user=self.user)
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertIn('DB failure', response.data['error'])