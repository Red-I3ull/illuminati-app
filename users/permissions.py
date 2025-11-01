from rest_framework import permissions
from .models import Role, Vote, UserVote
from django.utils import timezone

errorMessage = 'You must have permission to perform that'

class IsMasonUser(permissions.BasePermission):

    message = errorMessage

    def has_permission(self, request, view):
        user_role = getattr(request.user, 'role', None)
        return request.user and request.user.is_authenticated and user_role == Role.MASON

class IsSilverUser(permissions.BasePermission):

    message = errorMessage

    def has_permission(self, request, view):
        user_role = getattr(request.user, 'role', None)
        return request.user and request.user.is_authenticated and user_role == Role.SILVER

class IsGoldenUser(permissions.BasePermission):

    message = errorMessage

    def has_permission(self, request, view):
        user_role = getattr(request.user, 'role', None)
        return request.user and request.user.is_authenticated and user_role == Role.GOLDEN

class IsArchitectUser(permissions.BasePermission):

    message = errorMessage

    def has_permission(self, request, view):
        user_role = getattr(request.user, 'role', None)
        return request.user and request.user.is_authenticated and user_role == Role.ARCHITECT

class IsInquisitor(permissions.BasePermission):
    """Let access only to inquisitor."""
    message = "Only inquisitor can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_inquisitor)

class CanNominateForBan(permissions.BasePermission):
    """
    Let the inquisitor nominate for a ban.
    Also saves active nomination voting in view for future use.
    """
    message = "You are not inquisitor or nomination period is over."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_inquisitor):
            self.message = "Only inquisitor can nominate for ban."
            return False

        try:
            nomination_vote = Vote.objects.select_related('vote_type').get(
                initiator=user,
                status=Vote.Status.NOMINATION,
                vote_type__name='BAN'
            )
            if nomination_vote.nomination_end_time and timezone.now() >= nomination_vote.nomination_end_time:
                self.message = "Nominate period is over."
                return False

            view.nomination_vote = nomination_vote
            return True

        except Vote.DoesNotExist:
            self.message = "Didn't find nomination vote."
            return False
        except Vote.MultipleObjectsReturned:
            self.message = "Error find more than one nomination vote."
            return False
        except Exception as e:
            print(f"Error in CanNominateForBan: {e}") # aDD loging logic
            self.message = "Error happen when nominate"
            return False

class CanVoteOnThis(permissions.BasePermission):
    """
    check if users can vote this
    used like object-level permission.
    """
    message = "you can't vote on this. vote ends or vote type is not eligible."

    def has_object_permission(self, request, view, obj):
        if not isinstance(obj, Vote):
            return False

        user = request.user
        vote = obj

        if not user or not user.is_authenticated:
            return False

        if vote.status != Vote.Status.ACTIVE:
            self.message = "active vote"
            return False

        if vote.end_time and timezone.now() >= vote.end_time:
            self.message = "times up"
            return False

        vote_type = vote.vote_type
        eligible_roles = vote_type.eligible_voter_roles

        if not eligible_roles:
            self.message = "noone can vote for this vote type."
            return False

        if "ALL" in eligible_roles:
            return True

        # Special logic for future promotion
        # if "TARGET_ROLE" in eligible_roles:
        #
        #     if user.role == target_role:
        #         return True

        if user.role in eligible_roles:
            return True

        self.message = "Your role is not eligible to vote."
        return False
