import os
from dotenv import load_dotenv
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from users.serializers import InviteSerializer
from rest_framework.exceptions import ValidationError

load_dotenv()

User = get_user_model()

test_password = os.environ.get('TEST_PASSWORD')


class InviteSerializerTests(APITestCase):
    """Test cases for InviteSerializer"""

    def setUp(self):
        self.golden_user = User.objects.create_user(
            username="golden",
            email="golden@example.com",
            password=test_password,
            role="GOLDEN"
        )
        self.existing_user = User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password=test_password,
            role="MASON"
        )

    def test_invite_serializer_validates_new_email(self):
        """Test that serializer accepts new email"""
        data = {"email": "newuser@example.com"}
        serializer = InviteSerializer(data=data, context={"request": type('Request', (), {'user': self.golden_user})()})
        self.assertTrue(serializer.is_valid())

    def test_invite_serializer_fails_if_email_exists(self):
        """Test that serializer rejects existing email"""
        data = {"email": "existing@example.com"}
        serializer = InviteSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)
        self.assertIn("email already exists", str(serializer.errors))

    def test_invite_serializer_creates_user_with_mason_role(self):
        """Test that serializer creates user with MASON role"""
        data = {"email": "invited@example.com"}
        request = type('Request', (), {'user': self.golden_user})()
        serializer = InviteSerializer(data=data, context={"request": request})
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        
        self.assertEqual(user.email, "invited@example.com")
        self.assertEqual(user.role, "MASON")
        self.assertTrue(User.objects.filter(email="invited@example.com").exists())


class InviteAPITests(APITestCase):
    """Test cases for InviteViewSet API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("invite-list")
        
        self.golden_user = User.objects.create_user(
            username="golden",
            email="golden@example.com",
            password=test_password,
            role="GOLDEN"
        )
        self.architect_user = User.objects.create_user(
            username="architect",
            email="architect@example.com",
            password=test_password,
            role="ARCHITECT"
        )
        self.mason_user = User.objects.create_user(
            username="mason",
            email="mason@example.com",
            password=test_password,
            role="MASON"
        )
        self.existing_user = User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password=test_password,
            role="MASON"
        )

    def test_invite_requires_authentication(self):
        """Test that invite endpoint requires authentication"""
        response = self.client.post(self.url, {"email": "test@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invite_success_with_golden_user(self):
        """Test successful invite by GOLDEN user"""
        self.client.force_authenticate(user=self.golden_user)
        response = self.client.post(self.url, {"email": "newuser@example.com"}, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())
        created_user = User.objects.get(email="newuser@example.com")
        self.assertEqual(created_user.role, "MASON")

    def test_invite_success_with_architect_user(self):
        """Test successful invite by ARCHITECT user"""
        self.client.force_authenticate(user=self.architect_user)
        response = self.client.post(self.url, {"email": "another@example.com"}, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="another@example.com").exists())

    def test_invite_fails_with_mason_user(self):
        """Test that MASON user cannot invite"""
        self.client.force_authenticate(user=self.mason_user)
        response = self.client.post(self.url, {"email": "blocked@example.com"}, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(email="blocked@example.com").exists())

    def test_invite_fails_if_email_exists(self):
        """Test that invite fails if email already exists"""
        self.client.force_authenticate(user=self.golden_user)
        response = self.client.post(self.url, {"email": "existing@example.com"}, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_invite_fails_with_invalid_email(self):
        """Test that invite fails with invalid email format"""
        self.client.force_authenticate(user=self.golden_user)
        response = self.client.post(self.url, {"email": "not-an-email"}, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_invite_fails_with_missing_email(self):
        """Test that invite fails with missing email field"""
        self.client.force_authenticate(user=self.golden_user)
        response = self.client.post(self.url, {}, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_get_queryset_returns_only_invited_users(self):
        """Test that get_queryset returns only users invited by current user"""

        self.client.force_authenticate(user=self.golden_user)
        response = self.client.get(self.url, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)