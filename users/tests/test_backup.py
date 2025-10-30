import io
import os
import json
import zipfile
import shutil
from dotenv import load_dotenv
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from users.models import Marker, Role

load_dotenv()
User = get_user_model()


TEST_MEDIA_ROOT = os.path.join(settings.BASE_DIR, 'test_media_root')

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class BackupViewSetTests(APITestCase):

    @classmethod
    def setUpClass(cls):
        """Temporary media directory before any tests run"""
        super().setUpClass()
        os.makedirs(TEST_MEDIA_ROOT, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up and remove the temporary media directory after all tests run"""
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        """ Initial data for each test"""

        test_password = os.environ.get('TEST_PASSWORD')
        self.architect_user = User.objects.create_user(
            email='architect@example.com',
            password=test_password,
            role=Role.ARCHITECT
        )

        self.test_image = SimpleUploadedFile(
            name='test_image.jpg',
            content=b'fake image data',
            content_type='image/jpeg'
        )

        self.url = reverse('backup-list')

#tests
    def test_list_download_with_data_and_image(self):
        """Test downloading a backup with a Marker and image"""
        Marker.objects.create(
            name='Test Marker',
            lat=10.0,
            lng=20.0,
            user=self.architect_user,
            image=self.test_image
        )

        self.client.force_authenticate(user=self.architect_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def _create_test_zip(self, json_data_str, image_name=None, image_content=None):
        """Additional function to create a backup zip file in memory for tests"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr('backup_data.json', json_data_str)
            if image_name and image_content:
                zipf.writestr(image_name, image_content)

        zip_buffer.seek(0)
        return SimpleUploadedFile(
            "backup.zip", 
            zip_buffer.read(),
            content_type="application/zip"
        )

    def test_create_upload_success(self):
        """Test successfully uploading and restoring a backup"""
        self.assertEqual(Marker.objects.count(), 0)
        self.client.force_authenticate(user=self.architect_user)

        image_path_in_zip = 'marker_photos/restored_image.jpg'
        image_content = b'fake image data for restore'
        json_data_str = json.dumps([
            {
                "model": "users.marker",
                "pk": 1,
                "fields": {
                    "name": "Restored Marker",
                    "lat": 12.34,
                    "lng": 56.78,
                    "user": None,
                    "image": image_path_in_zip,
                    "created_at": "2023-01-01T00:00:00Z"
                }
            }
        ])

        upload_file = self._create_test_zip(json_data_str, image_path_in_zip, image_content)

        response = self.client.post(self.url, {'backup_file': upload_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {"status": "Restore successful"})

    def test_create_no_file_provided(self):
        """Test error when no file is uploaded"""
        self.client.force_authenticate(user=self.architect_user)
        response = self.client.post(self.url, {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"error": "No .zip file provided."})

    def test_create_not_a_zip_file(self):
        """Test error when the uploaded file is not a .zip"""
        self.client.force_authenticate(user=self.architect_user)
        not_a_zip = SimpleUploadedFile("backup.txt", b"i am text", content_type="text/plain")
        response = self.client.post(self.url, {'backup_file': not_a_zip}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"error": "No .zip file provided."})

    def test_create_corrupt_zip_file(self):
        """Test error when the .zip file is corrupt"""
        self.client.force_authenticate(user=self.architect_user)
        corrupt_zip = SimpleUploadedFile("backup.zip", b"i am corrupt zip",
                                         content_type="application/zip")
        response = self.client.post(self.url, {'backup_file': corrupt_zip}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"error": "Invalid .zip file"})

    def test_create_zip_missing_json(self):
        """Test error when the zip file does not contain backup_data.json"""
        self.client.force_authenticate(user=self.architect_user)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            zipf.writestr('some_other_file.txt', 'hello')
        zip_buffer.seek(0)

        upload_file = SimpleUploadedFile("backup.zip", zip_buffer.read(),
                                         content_type="application/zip")

        response = self.client.post(self.url, {'backup_file': upload_file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"error": "backup_data.json not found"})
