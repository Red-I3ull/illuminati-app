from rest_framework.response import Response
from rest_framework import status
from .models import Marker, CustomUser, EntryPassword
from rest_framework import viewsets, permissions
from rest_framework.permissions import IsAuthenticated
from .permissions import IsArchitectUser, IsGoldenUser
from django.db import transaction, DatabaseError


class CompromisedViewSet(viewsets.ViewSet):
    """ A ViewSet for we-are-compromised endpoint """

    permission_classes = [IsAuthenticated, IsArchitectUser | IsGoldenUser]

    @transaction.atomic
    def create(self, request, *args, **kwargs):

        try:

            marker_count, _ = Marker.objects.all().delete()

            entry_pw_count, _ = EntryPassword.objects.filter(is_active=True).delete()

            user_count = CustomUser.objects.all().update(
                username=None,
                password=''
            )

            response_data = {
                'message': 'Compromise protocol initiated',
                'markers_deleted': marker_count,
                'active_entry_passwords_deleted': entry_pw_count,
                'users_deleted (passwords wiped)': user_count
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except DatabaseError as e:

            return Response(
                {'error': f'Compromised operation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )