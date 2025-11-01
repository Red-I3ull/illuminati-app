from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields ):
        if not email:
            raise ValueError('Email is a required field')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self,email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class Role(models.TextChoices):
    GOLDEN = 'GOLDEN', 'Golden'
    SILVER = 'SILVER', 'Silver'
    ARCHITECT = 'ARCHITECT', 'Architect'
    MASON = 'MASON', 'Mason'

class CustomUser(AbstractUser):
    email = models.EmailField(max_length=200, unique=True)
    birthday = models.DateField(null=True, blank=True)
    username = models.CharField(max_length=200, null=True, blank=True)

    objects = CustomUserManager()

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MASON,
        help_text="The role of the user in the system"
    )
    is_inquisitor = models.BooleanField(default=False, help_text="Designates if this user is the current inquisitor")
    last_promotion_attempt = models.DateTimeField(null=True, blank=True)
    last_known_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="Last Known IP")
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

class BlacklistedIP(models.Model):
    """Stores IP addresses that are banned from the site."""
    ip_address = models.GenericIPAddressField(unique=True, verbose_name="Banned IP Address")
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blacklisted_ips'
        verbose_name = 'Blacklisted IP'
        verbose_name_plural = 'Blacklisted IPs'

    def __str__(self):
        return self.ip_address

#Marker model
class Marker(models.Model):
    name = models.CharField(max_length=250)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    image = models.ImageField(upload_to='marker_photos/', null=True, blank=True)
    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False
    )

    class Meta:# pylint: disable=too-few-public-methods
        db_table = 'markers'

    def __str__(self):
        return str(self.name)

class EntryPassword(models.Model):
    """Model for entry password."""
    password = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'entry_password'
        verbose_name = 'entry Password'
        verbose_name_plural = 'entry Passwords'

    def __str__(self):
        return f"entry Password (Active: {self.is_active})"

class Invite(models.Model):
    email = models.EmailField(unique=True)
    invited_by = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        related_name='sent_invites'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)
    
class VoteType(models.Model):
    """chooses the rules of votes."""
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="unique name for the vote type"
    )
    description = models.TextField(blank=True)
    nomination_duration_hours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Duration of the nomination in hours"
    )
    duration_hours = models.PositiveIntegerField(
        help_text="Duration of the vote in hours"
    )
    eligible_voter_roles = models.JSONField(default=list)
    pass_condition = models.CharField(
        max_length=50,
        choices=[('MAJORITY', 'Majority'), ('UNANIMOUS_TARGET', 'Unanimous Target Role'),
                 ('UNANIMOUS_ALL_VOTED', 'Unanimous Voted')],
        help_text="Is voting successful"
    )
    inquisitor_can_initiate = models.BooleanField(default=False)

    class Meta:
        db_table = 'vote_types'
        verbose_name = 'Vote Type'
        verbose_name_plural = 'Vote Types'

    def __str__(self):
        return self.name

class Vote(models.Model):
    """Represents an instance of a vote."""

    class Status(models.TextChoices):
        NOMINATION = 'NOMINATION', 'Nomination Phase'
        ACTIVE = 'ACTIVE', 'Active Voting'
        CLOSED = 'CLOSED', 'Closed'

    class Outcome(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PASSED = 'PASSED', 'Passed'
        FAILED = 'FAILED', 'Failed'
        EXPIRED = 'EXPIRED', 'Expired (No Nomination)'

    vote_type = models.ForeignKey(VoteType, on_delete=models.CASCADE, related_name='votes')
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='initiated_votes',
        on_delete=models.SET_NULL,
        null=True
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='targeted_in_votes',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User against whom the vote is targeted"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    nomination_end_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOMINATION
    )
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        default=Outcome.PENDING,
        blank=True
    )

    class Meta:
        db_table = 'votes'
        ordering = ['-start_time']

    def __str__(self):
        target = f" on {self.target_user}" if self.target_user else " (Pending Nomination)"
        return f"{self.vote_type.name} vote ({self.status}) initiated by {self.initiator}{target}"

class UserVote(models.Model):
    """Write a decision for a vote."""

    class Decision(models.TextChoices):
        AGREE = 'AGREE', 'Agree'
        DISAGREE = 'DISAGREE', 'Disagree'

    vote = models.ForeignKey(Vote, on_delete=models.CASCADE, related_name='user_votes')
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cast_votes')
    decision = models.CharField(max_length=10, choices=Decision.choices)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_votes'
        unique_together = ('vote', 'voter')
        ordering = ['voted_at']

    def __str__(self):
        return f"{self.voter} voted {self.decision} on vote {self.vote.id}"
