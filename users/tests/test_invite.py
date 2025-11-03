import os
from dotenv import load_dotenv
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from users.serializers import InviteSerializer
from users.models import Invite
from users.invite_api import InviteViewSet

load_dotenv()
User = get_user_model()
test_password = os.environ.get("TEST_PASSWORD", "test-pass")


class SimpleInviteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("invite-list")
        self.golden = User.objects.create_user(
            username="golden",
            email="golden@example.com",
            password=test_password,
            role="GOLDEN",
        )
        self.mason = User.objects.create_user(
            username="mason",
            email="mason@example.com",
            password=test_password,
            role="MASON",
        )

    def test_get_queryset_smoke(self):
        self.client.force_authenticate(user=self.golden)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_perform_create_allowed_role(self):
        self.client.force_authenticate(user=self.golden)
        resp = self.client.post(self.url, {"email": "new@example.com"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_perform_create_denied_role(self):
        self.client.force_authenticate(user=self.mason)
        resp = self.client.post(self.url, {"email": "blocked@example.com"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
