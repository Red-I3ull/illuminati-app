import pytest
import os
from dotenv import load_dotenv
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from users.serializers import InviteSerializer
from django.contrib.auth import get_user_model


load_dotenv()
User = get_user_model()
test_password = os.environ.get('TEST_PASSWORD')

@pytest.mark.django_db
def test_invite_serializer_str_smoke():
    """Smoke test: serializer with valid email is valid"""
    user = User.objects.create_user(
        username="golden",
        email="golden@example.com",
        password=test_password,
        role="GOLDEN"
    )
    data = {"email": "smoke@example.com"}
    serializer = InviteSerializer(data=data, context={"request": type("Req", (), {"user": user})()})
    assert serializer.is_valid()


@pytest.mark.django_db
def test_invite_serializer_repr_smoke():
    """Smoke test: serializer errors stringifies without crash"""
    data = {"email": "not-an-email"}
    serializer = InviteSerializer(data=data)
    serializer.is_valid()
    assert "email" in str(serializer.errors)


@pytest.mark.django_db
def test_invite_api_options_head(client):
    """Smoke test: OPTIONS and HEAD requests work"""
    api_client = APIClient()
    url = reverse("invite-list")
    user = User.objects.create_user(
        username="golden",
        email="golden2@example.com",
        password=test_password,
        role="GOLDEN"
    )
    api_client.force_authenticate(user=user)

    # OPTIONS
    resp = api_client.options(url)
    assert resp.status_code == 200

    # HEAD
    resp = api_client.head(url)
    assert resp.status_code in (200, 405)  


@pytest.mark.django_db
def test_invite_api_get_list(client):
    """Smoke test: GET list returns 200 for authenticated user"""
    api_client = APIClient()
    user = User.objects.create_user(
        username="golden",
        email="golden3@example.com",
        password=test_password,
        role="GOLDEN"
    )
    api_client.force_authenticate(user=user)
    url = reverse("invite-list")
    resp = api_client.get(url)
    assert resp.status_code == 200
