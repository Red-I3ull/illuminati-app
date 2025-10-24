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

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

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

    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False
    )

    class Meta:# pylint: disable=too-few-public-methods
        db_table = 'markers'

    def __str__(self):
        return str(self.name)
