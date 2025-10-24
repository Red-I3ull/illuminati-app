from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from users.models import Marker, Role


User = get_user_model()

class MarkerViewSetTests(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.mason_user = User.objects.create_user(
            email='mason@example.com',
            password='password123',
            role=Role.MASON
        )
        self.silver_user = User.objects.create_user(
            email='silver@example.com',
            password='password123',
            role=Role.SILVER
        )
        self.golden_user = User.objects.create_user(
            email='golden@example.com',
            password='password123',
            role=Role.GOLDEN
        )
        self.architect_user = User.objects.create_user(
            email='architect@example.com',
            password='password123',
            role=Role.ARCHITECT
        )

        self.marker = Marker.objects.create(
            name="Initial Marker",
            lat=40.7128,
            lng=-74.0060,
        )

        self.list_url = reverse('markers-list')
        self.create_url = reverse('markers-list')
        self.delete_url = reverse('markers-detail', args=[self.marker.id])

#Tests for list
    def test_list_requires_authentication(self):
        """Unauthenticated users cannot list markers"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    def test_any_authenticated_user_can_list_markers(self):
        """Authenticated user can list markers"""
        for user in [self.mason_user, self.silver_user, self.golden_user, self.architect_user]:
            self.client.force_authenticate(user=user)
            response = self.client.get(self.list_url)
            self.assertEqual(
                response.status_code, status.HTTP_200_OK,)
        self.client.force_authenticate(user=None)

#Tests for create
    def test_create_marker_forbidden_role_mason(self):
        """Mason user cannot create markers"""
        self.client.force_authenticate(user=self.mason_user)
        data = {"name": "New Marker", "lat": 40.7128, "lng": -74.0060}
        response = self.client.post(self.create_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=None)

    def test_create_for_allowed_users(self):
        """Silver/Golden/Architect can create markers"""
        for user in [self.silver_user, self.golden_user, self.architect_user]:
            self.client.force_authenticate(user=user)
            data = {"name": "New Marker", "lat": 40.7128, "lng": -74.0060}
            response = self.client.post(self.create_url, data)
            self.assertEqual(
                response.status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(user=None)

#Tests for delete
    def test_delete_for_forbidden_users(self):
        """Mason/Silver cannot delete markers"""
        for user in [self.mason_user, self.silver_user]:
            self.client.force_authenticate(user=user)
            response = self.client.delete(self.delete_url)
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=None)

    def test_delete_for_allowed_users(self):
        """Golden/Architect can delete markers"""
        for user in [self.golden_user, self.architect_user]:
            self.client.force_authenticate(user=user)
            marker_to_delete = Marker.objects.create(
                name="Marker for deletion test",
                lat=10.0,
                lng=10.0,
                user=user
            )
            delete_url = reverse('markers-detail', args=[marker_to_delete.id])
            response = self.client.delete(delete_url)
            self.assertEqual(
                response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertFalse(Marker.objects.filter(id=marker_to_delete.id).exists())
        self.client.force_authenticate(user=None)