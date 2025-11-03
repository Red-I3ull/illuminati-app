from django.urls import path, include
from .vote_api import(
    VoteViewSet, UserListView, NominateForBanView,
    SelectInquisitorView, EndVoteView,
    StartPromotionVoteView, RetireArchitectView
)
from .map_api import MarkerView
from .backup_api import BackupViewSet
from .compromised_api import CompromisedViewSet
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterViewset, LoginViewset, VerifyEntryPasswordViewset,
)

router = DefaultRouter()
router.register('verify-entry-password', VerifyEntryPasswordViewset, basename='verify-entry-password')
router.register('register', RegisterViewset, basename='register')
router.register('login', LoginViewset, basename='login')
router.register('markers', MarkerView, basename='markers')
router.register('votes', VoteViewSet, basename='vote')
router.register('backup', BackupViewSet, basename='backup')
router.register('compromised', CompromisedViewSet, basename='compromised')
urlpatterns = [
    path('users/', UserListView.as_view(), name='user-list'),
    path('votes/nominate-ban/', NominateForBanView.as_view(), name='nominate-ban'),
    path('votes/promote/', StartPromotionVoteView.as_view(), name='start-promotion'),
    path('scheduler/retire-architects/', RetireArchitectView.as_view(), name='scheduler-retire-architects'),
    path('scheduler/select-inquisitor/', SelectInquisitorView.as_view(), name='scheduler-select-inquisitor'),
    path('scheduler/end-vote/<int:vote_id>/', EndVoteView.as_view(), name='scheduler-end-vote'),
    path('', include(router.urls)),
]
