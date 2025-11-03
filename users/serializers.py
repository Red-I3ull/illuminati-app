from rest_framework import serializers
from .models import Marker, EntryPassword, CustomUser, Role, VoteType, Vote, UserVote
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class EntryPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(required=True, min_length=8)

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret.pop('password', None)
        return ret

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(validators=[])

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email not registered.")
        return value

    def create(self, validated_data):
        user = User.objects.get(email=validated_data['email'])
        user.username = validated_data.get('username', user.username)
        user.set_password(validated_data['password'])
        user.save()
        return user

class MarkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marker
        fields = [
            'id', 
            'name', 
            'lat', 
            'lng', 
            'user',
            'image',
            'created_at'
        ]

        extra_kwargs = {
            'user': {'write_only': True, 'required': False}
        }

class VoteTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoteType
        fields = '__all__'

class BasicUserSerializer(serializers.ModelSerializer):
     """for Users list view for example for inquisitor"""
     class Meta:
         model = User
         fields = ['id', 'username', 'email', 'role']

class UserVoteSerializer(serializers.ModelSerializer):
    voter_username = serializers.CharField(source='voter.username', read_only=True)

    class Meta:
        model = UserVote
        fields = ['id', 'vote', 'voter', 'voter_username', 'decision', 'voted_at']
        read_only_fields = ['voter', 'voted_at']

class CastVoteSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=UserVote.Decision.choices)

class NominateBanSerializer(serializers.Serializer):
    target_user_id = serializers.IntegerField(required=True)

class VoteSerializer(serializers.ModelSerializer):
    """full serialization of a vote detail."""
    vote_type = VoteTypeSerializer(read_only=True)
    initiator_username = serializers.CharField(source='initiator.username', read_only=True, allow_null=True)
    target_username = serializers.CharField(source='target_user.username', read_only=True, allow_null=True)
    user_votes = UserVoteSerializer(many=True, read_only=True) # all users vote for this vote (only when debugging)
    time_remaining_seconds = serializers.SerializerMethodField()
    current_user_vote = serializers.SerializerMethodField(read_only=True)
    vote_counts = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Vote
        fields = [
            'id', 'vote_type', 'initiator_username', 'target_username',
            'start_time', 'end_time', 'nomination_end_time', 'status', 'outcome',
            'time_remaining_seconds', 'current_user_vote', 'vote_counts',
            'user_votes'
        ]

    def get_time_remaining_seconds(self, obj):
        now = timezone.now()
        end_time = None
        if obj.status == Vote.Status.NOMINATION:
            end_time = obj.nomination_end_time
        elif obj.status == Vote.Status.ACTIVE:
            end_time = obj.end_time

        if obj.status == Vote.Status.CLOSED or not end_time or end_time <= now:
            return 0
        return int((end_time - now).total_seconds())

    def get_current_user_vote(self, obj):
        user = self.context.get('request').user
        if not user or not user.is_authenticated:
            return None
        try:
            user_vote = UserVote.objects.get(vote=obj, voter=user)
            return user_vote.decision
        except UserVote.DoesNotExist:
            return None

    def get_vote_counts(self, obj):
        """Count the number of votes yes/no for this vote."""
        if obj.status == Vote.Status.NOMINATION:
             return {'agree': 0, 'disagree': 0, 'total_cast': 0}

        votes_cast = obj.user_votes.all()
        agree_count = votes_cast.filter(decision=UserVote.Decision.AGREE).count()
        disagree_count = votes_cast.filter(decision=UserVote.Decision.DISAGREE).count()
        return {
            'agree': agree_count,
            'disagree': disagree_count,
            'total_cast': agree_count + disagree_count
        }

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email',
            'role', 'is_inquisitor', 'last_promotion_attempt',
            'role_assigned_at'
        ]
        read_only_fields = [
            'role', 'is_inquisitor',
            'last_promotion_attempt',
            'role_assigned_at'
        ]
