from django.contrib import admin
from django.urls import path
from .map_api import MarkerView
from .backup_api import BackupViewSet
from rest_framework.routers import DefaultRouter
from .views import RegisterViewset, LoginViewset, VerifyEntryPasswordViewset

router = DefaultRouter()
router.register('verify-entry-password', VerifyEntryPasswordViewset, basename='verify-entry-password')
router.register('register', RegisterViewset, basename='register')
router.register('login', LoginViewset, basename='login')
router.register('markers', MarkerView, basename='markers')
router.register('backup', BackupViewSet, basename='backup')
urlpatterns = router.urls