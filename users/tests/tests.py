import os
from dotenv import load_dotenv
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from users.models import EntryPassword
from rest_framework.exceptions import ValidationError
from users.serializers import LoginSerializer, RegisterSerializer

load_dotenv()

User = get_user_model()

test_password = os.environ.get('TEST_PASSWORD')

class VerifyEntryPasswordViewsetTests(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('verify-entry-password-list')

    def test_verify_entry_password_success(self):
        """Test successful entry password verification"""
        EntryPassword.objects.create(password=test_password, is_active=True)
        data = {'password': test_password}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['message'], 'Entry password verified successfully')

    def test_verify_entry_password_incorrect(self):
        """Test incorrect entry password"""
        EntryPassword.objects.create(password=test_password, is_active=True)
        data = {'password': 'wrong_password'}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error'], 'Incorrect password')

    def test_verify_entry_password_not_configured(self):
        """Test when entry password is not configured"""
        data = {'password': test_password}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['error'], 'Entry password not configured')

    def test_verify_entry_password_invalid_data(self):
        """Test with invalid data (missing password field)"""
        data = {}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_verify_entry_password_uses_only_active(self):
        """Test that only active entry password is used"""
        EntryPassword.objects.create(password=test_password, is_active=False)
        EntryPassword.objects.create(password=test_password, is_active=True)

        data = {'password': 'inactive_password'}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])

    def test_verify_entry_password_allows_any_user(self):
        """Test that endpoint allows any user (no authentication required)"""
        EntryPassword.objects.create(password=test_password, is_active=True)
        data = {'password': test_password}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

class SerializerTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="oldname",
            email="test@example.com",
            password="oldpass123"
        )

    def test_login_serializer_removes_password(self):
        data = {"username": "oldname", "password": "oldpass123"}
        serializer = LoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        rep = serializer.data
        self.assertNotIn("password", rep)
        self.assertEqual(rep["username"], "oldname")

    def test_register_serializer_fails_if_email_not_in_db(self):
        data = {"email": "nouser@example.com", "username": "newname", "password": "newpass123"}
        serializer = RegisterSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_register_serializer_updates_existing_user(self):
        data = {"email": "test@example.com", "username": "newname", "password": "newpass123"}
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.username, "newname")
        self.assertTrue(user.check_password("newpass123"))
        
class RegisterAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="oldname",
            email="test@example.com",
            password="oldpass123"
        )

    def test_register_with_nonexistent_email_fails(self):
        url = reverse("register-list")  # якщо у тебе ViewSet з basename="register"
        response = self.client.post(url, {
            "email": "nouser@example.com",
            "username": "newname",
            "password": "newpass123"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_with_existing_email_updates_user(self):
        url = reverse("register-list")
        response = self.client.post(url, {
            "email": "test@example.com",
            "username": "newname",
            "password": "newpass123"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "newname")
        self.assertTrue(self.user.check_password("newpass123"))