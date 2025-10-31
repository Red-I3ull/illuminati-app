from django.contrib import admin
from django.urls import path, include
from .map_api import MarkerView
from .backup_api import BackupViewSet
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterViewset, LoginViewset, VerifyEntryPasswordViewset,
    VoteViewSet,
    UserListView, NominateForBanView,
    SelectInquisitorView, EndVoteView
)
from .map_api import MarkerView

router = DefaultRouter()
router.register('verify-entry-password', VerifyEntryPasswordViewset, basename='verify-entry-password')
router.register('register', RegisterViewset, basename='register')
router.register('login', LoginViewset, basename='login')
router.register('markers', MarkerView, basename='markers')
router.register('votes', VoteViewSet, basename='vote')
urlpatterns = [
    path('users/', UserListView.as_view(), name='user-list'),
    path('votes/nominate-ban/', NominateForBanView.as_view(), name='nominate-ban'),
    path('scheduler/select-inquisitor/', SelectInquisitorView.as_view(), name='scheduler-select-inquisitor'),
    path('scheduler/end-vote/<int:vote_id>/', EndVoteView.as_view(), name='scheduler-end-vote'),
    path('', include(router.urls)),
]
router.register('backup', BackupViewSet, basename='backup')
urlpatterns = router.urls