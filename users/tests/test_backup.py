import io
import zipfile
from unittest import TestCase
from unittest.mock import patch, MagicMock, mock_open
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory
from rest_framework import status
from users.backup_api import BackupViewSet

class BackupViewSetCreateUnitTest(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = BackupViewSet.as_view({'post': 'create'})
        self.view_list = BackupViewSet.as_view({'get': 'list'})

        self.user = MagicMock()
        self.user.is_authenticated = True
        self.user.role = "ARCHITECT"

        patcher = patch('users.backup_api.BackupViewSet.get_permissions', return_value=[])
        self.mock_permissions = patcher.start()
        self.addCleanup(patcher.stop)
        self.fake_zip = self._make_fake_zip_file()

    def _make_fake_zip_file(self):
        """Creates a test .zip for tests"""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            fake_json = '[{"model": "users.marker", "pk": 1,' \
            '"fields": {"name": "Test", "lat": 10, "lng": 20}}]'
            zipf.writestr("backup_data.json", fake_json)
        buffer.seek(0)
        return SimpleUploadedFile(
            "backup.zip", 
            buffer.read(),
            content_type="application/zip"
        )


    @patch("users.backup_api.open", new_callable=mock_open)
    @patch("users.backup_api.os.path.exists")
    @patch("users.backup_api.tempfile.TemporaryDirectory")
    @patch("users.backup_api.zipfile.ZipFile")
    @patch("users.backup_api.serializers.deserialize")
    @patch("users.backup_api.Marker")
    def test_create_valid_backup_restores_successfully(self, mock_marker, mock_deserialize, mock_zipfile,
                                                        mock_tmpdir, mock_exists, mock_open_file):
        """Successful restore from backup.zip"""

        mock_tmpdir.return_value.__enter__.return_value = "/fake/tmp"
        mock_exists.return_value = True

        fake_obj = MagicMock()
        fake_obj.object.name = "Test Marker"
        fake_obj.object.lat = 1.0
        fake_obj.object.lng = 2.0
        fake_obj.object.image.name = "test"
        mock_deserialize.return_value = [fake_obj]

        mock_marker_instance = MagicMock()
        mock_marker.return_value = mock_marker_instance

        request = self.factory.post("/backup/", {"backup_file": self.fake_zip})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "Restore successful")
        mock_marker_instance.save.assert_called_once()

    def test_create_without_file_returns_error(self):
        """Should return 400 if no file is uploaded"""
        request = self.factory.post("/backup/", {})
        request.user = self.user
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No .zip file provided", response.data["error"])

    def test_create_with_invalid_file_type_returns_error(self):
        """Should return 400 if file is not .zip"""
        fake_file = SimpleUploadedFile("backup.txt", b"fake", content_type="text/plain")
        request = self.factory.post("/backup/", {"backup_file": fake_file})
        request.user = self.user
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No .zip file provided", response.data["error"])

    @patch("users.backup_api.open", new_callable=mock_open, read_data=b"fake-image-bytes")
    @patch("users.backup_api.os.path.exists")
    @patch("users.backup_api.serializers.serialize")
    @patch("users.backup_api.Marker.objects.all")
    def test_list_download_backup_successfully(self, mock_markers_all, mock_serialize, mock_exists, mock_open_file):
        """ Dowloading  a zip file"""
        mock_image = MagicMock()
        mock_image.path = "/fake/path/to/image.png"
        mock_image.name = "image.png"

        mock_marker = MagicMock(image=mock_image)
        mock_markers_all.return_value = [mock_marker]

        mock_serialize.return_value = '[{"model": "fake.marker"}]'

        mock_exists.return_value = True

        request = self.factory.get("/backup/")
        request.user = self.user

        response = self.view_list(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('attachment; filename="marker_backup.zip"', response['Content-Disposition'])

    @patch("users.backup_api.os.path.exists")
    @patch("users.backup_api.tempfile.TemporaryDirectory")
    @patch("users.backup_api.zipfile.ZipFile")
    def test_create_zip_missing_json_returns_error(self, mock_zipfile, mock_tmpdir, mock_exists):
        """Test error when the zip file does not contain backup_data.json"""

        mock_tmpdir.return_value.__enter__.return_value = "/fake/tmp"
        mock_exists.return_value = False

        request = self.factory.post("/backup/", {"backup_file": self.fake_zip})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("backup_data.json not found", response.data["error"])

    @patch("users.backup_api.zipfile.ZipFile")
    def test_create_corrupt_zip_returns_error(self, mock_zipfile):
        """Test that uploading a corrupt .zip file returns a 400 Bad Request"""

        mock_zipfile.side_effect = zipfile.BadZipFile

        fake_file = SimpleUploadedFile("backup.zip", b"not-a-real-zip", content_type="application/zip")
        request = self.factory.post("/backup/", {"backup_file": fake_file})
        request.user = self.user

        response = self.view(request) 

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid .zip file", response.data["error"])