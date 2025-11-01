import io
from unittest import TestCase
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory
from rest_framework import status
from users.backup_api import BackupViewSet

class BackupViewSetUnitTest(TestCase):
    """Unit tests for BackupViewSet"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view_create = BackupViewSet.as_view({'post': 'create'})
        self.view_list = BackupViewSet.as_view({'get': 'list'})

        self.user = MagicMock()
        self.user.is_authenticated = True
        self.user.role = "ARCHITECT"

        patcher = patch('users.backup_api.BackupViewSet.get_permissions', return_value=[])
        self.mock_permissions = patcher.start()
        self.addCleanup(patcher.stop)

        self.fake_json_content = (b'[{"model": "users.marker", "pk": 1, "fields": '
                                  b'{"name": "Test", "lat": 10, "lng": 20, "image": "path/to/image.png"}}]')
        self.fake_json_file = SimpleUploadedFile(
            "backup.json",
            self.fake_json_content,
            content_type="application/json"
        )

#test
    @patch("users.backup_api.serializers.serialize")
    @patch("users.backup_api.Marker.objects.all")
    def test_list_download_backup_successfully(self, mock_markers_all, mock_serialize):
        """Test downloading a backup json"""
        mock_marker_list = [MagicMock()]
        mock_markers_all.return_value = mock_marker_list
        mock_serialize.return_value = '{"fake": "json data"}'

        request = self.factory.get("/backup/")
        request.user = self.user

        response = self.view_list(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response['Content-Disposition'], 'attachment; ' \
        'filename="marker_backup.json"')

        mock_markers_all.assert_called_once()
        mock_serialize.assert_called_with('json', mock_marker_list)

        self.assertEqual(response.content, b'{"fake": "json data"}')

    @patch("users.backup_api.serializers.deserialize")
    @patch("users.backup_api.Marker")
    def test_create_valid_json_restores_successfully(self, mock_marker, mock_deserialize):
        """Test successfully uploading and restoring a backup"""

        fake_obj = MagicMock()
        fake_obj.object.name = "Test Marker"
        fake_obj.object.lat = 1.0
        fake_obj.object.lng = 2.0
        fake_obj.object.image.name = "path/to/image.png"
        mock_deserialize.return_value = [fake_obj]

        mock_marker_instance = MagicMock()
        mock_marker.return_value = mock_marker_instance

        request = self.factory.post("/backup/", {"backup_file": self.fake_json_file})
        request.user = self.user

        response = self.view_create(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "Restore successful")

    def test_create_without_file_returns_error(self):
        """Test return 400 if no file is uploaded"""
        request = self.factory.post("/backup/", {})
        request.user = self.user
        response = self.view_create(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No .json file provided", response.data["error"])

    def test_create_with_invalid_file_type_returns_error(self):
        """Test return 400 if file is not .json"""
        fake_file = SimpleUploadedFile("backup.txt", b"fake", content_type="text/plain")
        request = self.factory.post("/backup/", {"backup_file": fake_file})
        request.user = self.user

        response = self.view_create(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No .json file provided", response.data["error"])
