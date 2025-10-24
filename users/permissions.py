from rest_framework import permissions
from .models import Role

class IsMasonUser(permissions.BasePermission):

    message = 'You must have permission to perform that'

    def has_permission(self, request, view):
        user_role = getattr(request.user, 'role', None)
        return request.user and request.user.is_authenticated and user_role == Role.MASON

class IsSilverUser(permissions.BasePermission):

    message = 'You must have permission to perform that'

    def has_permission(self, request, view):
        user_role = getattr(request.user, 'role', None)
        return request.user and request.user.is_authenticated and user_role == Role.SILVER

class IsGoldenUser(permissions.BasePermission):

    message = 'You must have permission to perform that'

    def has_permission(self, request, view):
        user_role = getattr(request.user, 'role', None)
        return request.user and request.user.is_authenticated and user_role == Role.GOLDEN

class IsArchitectUser(permissions.BasePermission):

    message = 'You must have permission to perform that'

    def has_permission(self, request, view):
        user_role = getattr(request.user, 'role', None)
        return request.user and request.user.is_authenticated and user_role == Role.ARCHITECT