import io
import os
import zipfile
import tempfile
from django.http import HttpResponse
from django.core import serializers
from django.core.files import File
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from .models import Marker
from rest_framework import viewsets, permissions
from .permissions import IsArchitectUser

class BackupViewSet(viewsets.ViewSet):

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated, IsArchitectUser]
        elif self.action == 'list':
            permission_classes = [permissions.IsAuthenticated, IsArchitectUser]
        return [permission() for permission in permission_classes]

    parser_classes = [MultiPartParser, FormParser]

    def list(self, request):
        """Download Marker data and images as a zip"""
        markers = Marker.objects.all()
        data = serializers.serialize('json', markers)

        s = io.BytesIO()
        with zipfile.ZipFile(s, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr('backup_data.json', data)
            for marker in markers:
                if marker.image:
                    try:
                        if os.path.exists(marker.image.path):
                            zipf.write(marker.image.path, arcname=marker.image.name)
                    except FileNotFoundError as e:
                        print(f"Warning: Could not add file {marker.image.path} to zip: {e}")

        s.seek(0)
        response = HttpResponse(s, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="marker_backup.zip"'
        return response

    def create(self, request):
        """Upload the  backup.zip file for restores"""

        backup_file = request.FILES.get('backup_file')
        if not backup_file or not backup_file.name.endswith('.zip'):
            return Response(
                {"error": "No .zip file provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(backup_file, 'r') as zipf:
                    zipf.extractall(temp_dir)

                json_path = os.path.join(temp_dir, 'backup_data.json')
                if not os.path.exists(json_path):
                    return Response(
                        {"error": "backup_data.json not found"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                with open(json_path, 'r', encoding='utf-8') as f:
                    deserialized_objects = serializers.deserialize('json', f)

                for obj in deserialized_objects:
                    old_marker_data = obj.object
                    new_marker = Marker(
                        name=old_marker_data.name,
                        lat=old_marker_data.lat,
                        lng=old_marker_data.lng,
                        user=request.user
                    )

                    if old_marker_data.image.name:
                        image_path_in_zip = old_marker_data.image.name
                        image_full_path = os.path.join(temp_dir, image_path_in_zip)

                        if os.path.exists(image_full_path):
                            with open(image_full_path, 'rb') as img_f:
                                django_file = File(img_f)
                                new_marker.image.save(os.path.basename(image_path_in_zip),# pylint: disable=no-member
                                                      django_file, save=False)
                    new_marker.save()

        except zipfile.BadZipFile:
            return Response(
                {"error": "Invalid .zip file"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (IOError, OSError) as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"status": "Restore successful"},
            status=status.HTTP_201_CREATED
        )
