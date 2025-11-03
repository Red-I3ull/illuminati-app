from django.contrib.auth import get_user_model
from django.http import Http404
from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .serializers import (
    VoteSerializer, CastVoteSerializer,
    NominateBanSerializer, BasicUserSerializer, UserSerializer
)
from rest_framework.response import Response
from .models import Role, VoteType, Vote, UserVote, BlacklistedIP, CustomUser

from .permissions import (
    IsInquisitor, CanNominateForBan, CanVoteOnThis, CanInitiatePromotion
)

User = get_user_model()

class UserListView(generics.ListAPIView):
    """
    Returns a list of active users. Only available to the Inquisitor.
    Used to select a ban candidate.
    """
    serializer_class = BasicUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsInquisitor]

    def get_queryset(self):
        return User.objects.filter(is_active=True).exclude(id=self.request.user.id).order_by('username')


class VoteViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing votes.
    List: shows votes that the user can participate in or that are in the nomination phase (for the Inquisitor).
    Retrieve: shows the details of a specific vote, if the user has permission to see it.
    """
    serializer_class = VoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()

        queryset = Vote.objects.filter(
            Q(status=Vote.Status.ACTIVE, end_time__gt=now) |
            Q(status=Vote.Status.NOMINATION, nomination_end_time__gt=now)
        ).select_related('vote_type').prefetch_related('user_votes__voter')

        eligible_vote_ids = []
        for vote in queryset:
            can_see = False
            if vote.status == Vote.Status.NOMINATION and vote.vote_type.name == 'BAN' and vote.initiator == user:
                can_see = True
            elif vote.status == Vote.Status.ACTIVE:
                 checker = CanVoteOnThis()
                 if checker.has_object_permission(self.request, self, vote):
                      can_see = True

            if can_see:
                eligible_vote_ids.append(vote.id)

        return Vote.objects.filter(id__in=eligible_vote_ids).order_by('-start_time')

    def get_permissions(self):
        if self.action == 'retrieve':
            return [permissions.IsAuthenticated()]
        elif self.action == 'cast_vote':
            return [permissions.IsAuthenticated(), CanVoteOnThis()]
        return super().get_permissions()

    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        can_see = False
        if obj.status == Vote.Status.NOMINATION and obj.vote_type.name == 'BAN' and obj.initiator == user:
            can_see = True
        elif obj.status == Vote.Status.ACTIVE:
             checker = CanVoteOnThis()
             checker.message = "you don't have permission to view this vote"
             temp_already_voted = UserVote.objects.filter(vote=obj, voter=user).exists()
             if checker.has_object_permission(self.request, self, obj) or temp_already_voted:
                  can_see = True #allow seen if vote already

        if not can_see:
            raise Http404("You don't have permission to view this vote.")
        return obj


    @action(detail=True, methods=['post'], url_path='cast-vote')
    def cast_vote(self, request, pk=None):
        """let user cast a vote on a vote"""
        vote = self.get_object()
        serializer = CastVoteSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if vote.status != Vote.Status.ACTIVE or (vote.end_time and timezone.now() >= vote.end_time):
            return Response({"detail": "vote inactive or ended"}, status=status.HTTP_400_BAD_REQUEST)

        if UserVote.objects.filter(vote=vote, voter=request.user).exists():
            return Response({"detail": "you voted already"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            UserVote.objects.create(
                vote=vote,
                voter=request.user,
                decision=serializer.validated_data['decision']
            )
            response_serializer = self.get_serializer(vote)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error saving vote: {e}")
            return Response({"detail": "Your vote could not be saved."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NominateForBanView(generics.GenericAPIView):
    """
    Endpoint for Inquisitor to nominate a user. Takes a BAN vote from NOMINATION to ACTIVE.
    """
    serializer_class = NominateBanSerializer
    permission_classes = [permissions.IsAuthenticated, CanNominateForBan]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        target_user_id = serializer.validated_data['target_user_id']
        vote = getattr(self, 'nomination_vote', None)

        if not vote:
             return Response({"detail": "Error: No active vote found for the nomination."}, status=status.HTTP_404_NOT_FOUND)

        try:
            target_user = User.objects.get(pk=target_user_id, is_active=True)
        except User.DoesNotExist:
             return Response({"detail": "The user for the nomination was not found or is inactive."}, status=status.HTTP_404_NOT_FOUND)

        if target_user == request.user:
             return Response({"detail": "You cannot nominate yourself."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        vote.target_user = target_user
        vote.status = Vote.Status.ACTIVE
        vote.nomination_end_time = None

        vote.end_time = now + timedelta(hours=vote.vote_type.duration_hours)
        vote.save()

        response_serializer = VoteSerializer(vote, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class SelectInquisitorView(generics.GenericAPIView):
     """
     Selects a new Inquisitor and creates a BAN vote in the NOMINATION phase.
     """
     permission_classes = [permissions.AllowAny]

     def post(self, request, *args, **kwargs):
        User.objects.filter(is_inquisitor=True).update(is_inquisitor=False)

        eligible_users = User.objects.filter(role=Role.GOLDEN, is_active=True)

        if not eligible_users.exists():
             return Response({"message": "There are no candidates for the role of Inquisitor."}, status=status.HTTP_200_OK)

        import secrets
        new_inquisitor = secrets.choice(list(eligible_users))
        new_inquisitor.is_inquisitor = True
        new_inquisitor.save(update_fields=['is_inquisitor'])

        try:
            ban_vote_type = VoteType.objects.get(name='BAN')
            now = timezone.now()
            nomination_duration = ban_vote_type.nomination_duration_hours or 20
            total_duration = nomination_duration + (ban_vote_type.duration_hours or 4)

            nomination_end = now + timedelta(hours=nomination_duration)
            final_end = now + timedelta(hours=total_duration)

            Vote.objects.create(
                vote_type=ban_vote_type,
                initiator=new_inquisitor,
                status=Vote.Status.NOMINATION,
                start_time=now,
                nomination_end_time=nomination_end,
                end_time=final_end
            )
            return Response({"message": f"New Inquisitor: {new_inquisitor.username}. Created a BAN vote in the nomination phase."}, status=status.HTTP_201_CREATED)
        except VoteType.DoesNotExist:
            return Response({"error": "Vote type 'BAN' not found in the database."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            print(f"Error creating BAN vote:{e}")
            return Response({"error": "Failed to create a vote for the nomination."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StartPromotionVoteView(generics.GenericAPIView):
    """
    Creates a new promotion vote for the requesting user.
    """
    permission_classes = [permissions.IsAuthenticated, CanInitiatePromotion]
    serializer_class = VoteSerializer

    def post(self, request, *args, **kwargs):
        user = request.user

        if user.role == Role.MASON:
            vote_type_name = "PROMOTE_SILVER"
        elif user.role == Role.SILVER:
            vote_type_name = "PROMOTE_GOLDEN"
        elif user.role == Role.GOLDEN:
            vote_type_name = "PROMOTE_ARCHITECT"
        else:
            return Response({"error": "Invalid role for promotion."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vote_type = VoteType.objects.get(name=vote_type_name)
        except VoteType.DoesNotExist:
            return Response({"error": f"VoteType '{vote_type_name}' not configured."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        now = timezone.now()
        end_time = now + timedelta(hours=vote_type.duration_hours or 24)

        vote = Vote.objects.create(
            vote_type=vote_type,
            initiator=user,
            target_user=user,
            status=Vote.Status.ACTIVE,
            start_time=now,
            end_time=end_time
        )

        user.last_promotion_attempt = now
        user.save(update_fields=['last_promotion_attempt'])

        serializer = self.get_serializer(vote)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class EndVoteView(generics.GenericAPIView):
    """
    Ends the vote, tallies the results, and applies the consequences. Called by the scheduler for votes that have timed out.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, vote_id, *args, **kwargs):
        vote = get_object_or_404(
            Vote.objects.select_related('vote_type', 'target_user').prefetch_related('user_votes'),
            pk=vote_id
        )

        now = timezone.now()

        if vote.status == Vote.Status.CLOSED:
             return Response({"message": f"voting {vote_id} over"}, status=status.HTTP_200_OK)

        if vote.status == Vote.Status.NOMINATION:
            if vote.nomination_end_time and now >= vote.nomination_end_time:
                vote.status = Vote.Status.CLOSED
                vote.outcome = Vote.Outcome.EXPIRED
                vote.save()
                return Response({"message": f"voting {vote_id} ended without nomination"}, status=status.HTTP_200_OK)
            else:
                return Response({"message": f"voting {vote_id} in nomination fase"}, status=status.HTTP_200_OK)

        if vote.status == Vote.Status.ACTIVE:
            if vote.end_time and now < vote.end_time:
                 return Response({"message": f"voting {vote_id} is active."}, status=status.HTTP_200_OK)
        else:
             return Response({"error": f"voting {vote_id} have incorrect status '{vote.status}'."}, status=status.HTTP_400_BAD_REQUEST)

        passed = False
        condition = vote.vote_type.pass_condition
        votes_cast = vote.user_votes.all()
        agree_votes = sum(1 for v in votes_cast if v.decision == UserVote.Decision.AGREE)
        disagree_votes = sum(1 for v in votes_cast if v.decision == UserVote.Decision.DISAGREE)
        total_votes_cast = agree_votes + disagree_votes

        if condition == 'MAJORITY':
            passed = agree_votes > disagree_votes
        elif condition == 'UNANIMOUS_AGREE':
            passed = (disagree_votes == 0 and agree_votes > 0)

        vote.status = Vote.Status.CLOSED
        vote.outcome = Vote.Outcome.PASSED if passed else Vote.Outcome.FAILED
        vote.save()

        if passed and vote.target_user:
            target_user = vote.target_user
            now = timezone.now()

            if vote.vote_type.name == 'BAN':
                target_user = vote.target_user
                target_user.is_active = False
                target_user.save(update_fields=['is_active'])
                if target_user.last_known_ip:
                    ip_to_ban = target_user.last_known_ip
                    _, created = BlacklistedIP.objects.get_or_create(
                        ip_address=ip_to_ban,
                        defaults={'reason': f'Banned by vote {vote.id}'}
                    )
                    if created:
                        print(f"IP {ip_to_ban} added to blacklist.")
                print(f"user {vote.target_user.username} was baned by voting {vote.id}. Total vote cast {total_votes_cast}") # add logging

            elif vote.vote_type.name == 'PROMOTE_SILVER':
                target_user.role = Role.SILVER
                target_user.role_assigned_at = now
                target_user.save(update_fields=['role', 'role_assigned_at'])
            elif vote.vote_type.name == 'PROMOTE_GOLDEN':
                target_user.role = Role.GOLDEN
                target_user.role_assigned_at = now
                target_user.save(update_fields=['role', 'role_assigned_at'])
            elif vote.vote_type.name == 'PROMOTE_ARCHITECT':
                target_user.role = Role.ARCHITECT
                target_user.role_assigned_at = now
                target_user.save(update_fields=['role', 'role_assigned_at'])

            return Response({"message": f"voting {vote.id} over. Results: {vote.outcome}"}, status=status.HTTP_200_OK)

        return Response({"message": f"voting {vote.id} over. Results: {vote.outcome}"}, status=status.HTTP_200_OK)

class RetireArchitectView(generics.GenericAPIView):
    """
    Scheduler job finds an architect older than 42 days old and retires them.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer

    def post(self, request, *args, **kwargs):
        now = timezone.now()
        retirement_days = 42

        architects_to_retire = CustomUser.objects.filter(
            role=Role.ARCHITECT,
            is_active=True,
            role_assigned_at__lt=now - timedelta(days=retirement_days)
        )

        retired_count = 0
        for user in architects_to_retire:
            user.is_active = False
            user.save(update_fields=['is_active'])

            if user.last_known_ip:
                BlacklistedIP.objects.get_or_create(
                    ip_address=user.last_known_ip,
                    defaults={'reason': 'Retired Architect'}
                )

            print(f"Architect {user.username} has been retired and banned.")
            retired_count += 1

        return Response({"message": f"Successfully retired {retired_count} architects."})
