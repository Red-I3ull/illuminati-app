import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from users.models import CustomUser

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def golden_user(db):
    return CustomUser.objects.create_user(
        email="golden@example.com",
        password="pass1234",
        role="GOLDEN",
        is_active=True
    )

@pytest.fixture
def mason_user(db):
    return CustomUser.objects.create_user(
        email="mason@example.com",
        password="pass1234",
        role="MASON",
        is_active=True
    )

@pytest.mark.django_db
def test_invite_success(api_client, golden_user):
    api_client.force_authenticate(user=golden_user)
    url = reverse("invite-list")  # DRF router name
    payload = {"email": "newuser@example.com"}

    response = api_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert CustomUser.objects.filter(email="newuser@example.com").exists()

@pytest.mark.django_db
def test_invite_fails_if_not_allowed_role(api_client, mason_user):
    api_client.force_authenticate(user=mason_user)
    url = reverse("invite-list")
    payload = {"email": "blocked@example.com"}

    response = api_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not CustomUser.objects.filter(email="blocked@example.com").exists()

@pytest.mark.django_db
def test_invite_fails_if_email_exists(api_client, golden_user):
    existing = CustomUser.objects.create_user(
        email="exists@example.com",
        password="pass1234",
        role="MASON"
    )
    api_client.force_authenticate(user=golden_user)
    url = reverse("invite-list")
    payload = {"email": "exists@example.com"}

    response = api_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Цей email вже існує" in str(response.data)