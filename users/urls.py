from django.contrib import admin
from django.urls import path
from .map_api import MarkerView
from rest_framework.routers import DefaultRouter
from .views import * 

router = DefaultRouter()
router.register('register', RegisterViewset, basename='register')
router.register('login', LoginViewset, basename='login')
router.register('markers', MarkerView, basename='markers')
urlpatterns = router.urls