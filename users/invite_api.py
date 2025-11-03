from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from .models import Invite
from .serializers import InviteSerializer

User = get_user_model()

class InviteViewSet(viewsets.ModelViewSet):
    serializer_class = InviteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(invited_by=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in ["GOLDEN", "ARCHITECT"]:
            raise PermissionDenied("You do not have permission to invite users.")
        serializer.save(invited_by=user)