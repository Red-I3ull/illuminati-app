import io
import os
from django.http import HttpResponse
from django.core import serializers
from django.core.files import File
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from .models import Marker
from rest_framework import viewsets, permissions
from .permissions import IsArchitectUser

class BackupViewSet(viewsets.ViewSet):

    def get_permissions(self):
        if self.action in ['create', 'list']:
            permission_classes = [permissions.IsAuthenticated, IsArchitectUser]
        return [permission() for permission in permission_classes]

    parser_classes = [MultiPartParser]

    def list(self, request):
        """Download Marker data and images as a zip"""
        markers = Marker.objects.all()
        data = serializers.serialize('json', markers)

        response = HttpResponse(data, content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="marker_backup.json"'
        return response

    def create(self, request):
        """Upload the  backup.zip file for restores"""

        backup_file = request.FILES.get('backup_file')
        if not backup_file or not backup_file.name.endswith('.json'):
            return Response(
                {"error": "No .json file provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            json_data = backup_file.read().decode('utf-8')
            deserialized_objects = serializers.deserialize('json', json_data)

            for obj in deserialized_objects:
                old_marker_data = obj.object
                new_marker = Marker(
                    name=old_marker_data.name,
                    lat=old_marker_data.lat,
                    lng=old_marker_data.lng,
                    user=request.user
                )
                if old_marker_data.image.name:
                    new_marker.image.name = old_marker_data.image.name

                new_marker.save()

        except (IOError, OSError) as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"status": "Restore successful"},
            status=status.HTTP_201_CREATED
        )
