import os
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from datetime import timedelta
from django.contrib.auth import get_user_model
from users.models import Vote, VoteType, UserVote, Role, BlacklistedIP, CustomUser

User = get_user_model()

test_password = os.environ.get('TEST_PASSWORD')
ip_address = os.getenv('IP_ADDRESS')

class BaseVoteTestCase(APITestCase):
    """
    Sets up common users and vote types for all test cases.
    """

    @classmethod
    def setUpTestData(cls):
        cls.client = APIClient()
        cls.now = timezone.now()

        cls.mason = User.objects.create_user(
            email='mason@test.com', password=test_password, role=Role.MASON, username='test_mason',
            last_known_ip=ip_address, role_assigned_at=cls.now - timedelta(days=100)
        )
        cls.silver1 = User.objects.create_user(
            email='silver1@test.com', password=test_password, role=Role.SILVER, username='test_silver1',
            last_known_ip=ip_address, role_assigned_at=cls.now - timedelta(days=100)
        )
        cls.silver2 = User.objects.create_user(
            email='silver2@test.com', password=test_password, role=Role.SILVER, username='test_silver2',
            last_known_ip=ip_address, role_assigned_at=cls.now - timedelta(days=100)
        )
        cls.golden1 = User.objects.create_user(
            email='golden1@test.com', password=test_password, role=Role.GOLDEN, username='test_golden1',
            last_known_ip=ip_address, role_assigned_at=cls.now - timedelta(days=100)
        )
        cls.golden2 = User.objects.create_user(
            email='golden2@test.com', password=test_password, role=Role.GOLDEN, username='test_golden2',
            last_known_ip=ip_address, role_assigned_at=cls.now - timedelta(days=100)
        )
        cls.architect = User.objects.create_user(
            email='arch@test.com', password=test_password, role=Role.ARCHITECT, username='test_architect',
            last_known_ip=ip_address, role_assigned_at=cls.now - timedelta(days=100)
        )
        cls.inquisitor = User.objects.create_user(
            email='inq@i.com', password=test_password, role=Role.GOLDEN,
            is_inquisitor=True, username='inq',
            last_known_ip=ip_address, role_assigned_at=cls.now - timedelta(days=100)
        )

        cls.ban_vote_type = VoteType.objects.create(
            name='BAN',
            nomination_duration_hours=20,
            duration_hours=4,
            eligible_voter_roles=["ALL"],
            pass_condition='MAJORITY'
        )
        cls.promote_silver_type = VoteType.objects.create(
            name='PROMOTE_SILVER',
            duration_hours=24,
            eligible_voter_roles=[Role.SILVER],
            pass_condition='UNANIMOUS_AGREE'
        )
        cls.promote_golden_type = VoteType.objects.create(
            name='PROMOTE_GOLDEN',
            duration_hours=24,
            eligible_voter_roles=[Role.GOLDEN],
            pass_condition='UNANIMOUS_AGREE'
        )
        cls.promote_architect_type = VoteType.objects.create(
            name='PROMOTE_ARCHITECT',
            duration_hours=24,
            eligible_voter_roles=["ALL"],
            pass_condition='UNANIMOUS_AGREE'
        )

class UserListViewTests(BaseVoteTestCase):
    def setUp(self):
        self.vote_type = self.ban_vote_type
        self.target_user = self.mason

    def test_user_list_requires_authentication(self):
        url = reverse('user-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_list_requires_inquisitor(self):
        regular_user = User.objects.create_user(
            email='regular@r.com', password=test_password, username='regular'
        )
        self.client.force_authenticate(user=regular_user)
        url = reverse('user-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_list_returns_only_active_users(self):
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('user-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [user['username'] for user in response.data]
        self.assertIn('test_silver1', usernames)
        self.assertIn('test_silver2', usernames)
        self.assertNotIn('inactive', usernames)
        self.assertNotIn('inq', usernames)

    def test_user_list_excludes_current_user(self):
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('user-list')
        response = self.client.get(url)
        usernames = [user['username'] for user in response.data]
        self.assertNotIn(self.inquisitor.username, usernames)


class VoteViewSetTests(BaseVoteTestCase):

    def test_target_user_cannot_vote_on_own_promotion_vote(self):
        promotion_vote = Vote.objects.create(
            vote_type=self.promote_silver_type,
            initiator=self.mason,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            start_time=self.now,
            end_time=self.now + timedelta(hours=24)
        )

        self.client.force_authenticate(user=self.mason)
        url = reverse('vote-cast-vote', args=[promotion_vote.id])

        response = self.client.post(url, {"decision": "AGREE"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(UserVote.objects.count(), 0)

    def test_eligible_voter_can_see_promotion_vote(self):
        promotion_vote = Vote.objects.create(
            vote_type=self.promote_silver_type,
            initiator=self.mason,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            start_time=self.now,
            end_time=self.now + timedelta(hours=24)
        )

        self.client.force_authenticate(user=self.silver1)
        url = reverse('vote-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], promotion_vote.id)

    def test_list_votes_requires_authentication(self):
        url = reverse('vote-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_votes_shows_eligible_votes_for_golden(self):
        active_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            start_time=self.now,
            end_time=self.now + timedelta(hours=4)
        )

        self.client.force_authenticate(user=self.golden1)
        url = reverse('vote-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vote_ids = [vote['id'] for vote in response.data]
        self.assertIn(active_vote.id, vote_ids)

    def test_list_votes_shows_nomination_vote_to_initiator(self):
        nomination_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.NOMINATION,
            start_time=self.now,
            nomination_end_time=self.now + timedelta(hours=20)
        )

        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('vote-list')
        response = self.client.get(url)
        vote_ids = [vote['id'] for vote in response.data]
        self.assertIn(nomination_vote.id, vote_ids)

    def test_list_votes_hides_nomination_vote_from_non_initiator(self):
        nomination_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.NOMINATION,
            start_time=self.now,
            nomination_end_time=self.now + timedelta(hours=20)
        )

        self.client.force_authenticate(user=self.golden1)
        url = reverse('vote-list')
        response = self.client.get(url)
        vote_ids = [vote['id'] for vote in response.data]
        self.assertNotIn(nomination_vote.id, vote_ids)

    def test_list_votes_excludes_closed_votes(self):
        closed_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            target_user=self.mason,
            status=Vote.Status.CLOSED,
            end_time=self.now - timedelta(hours=1)
        )

        self.client.force_authenticate(user=self.golden1)
        url = reverse('vote-list')
        response = self.client.get(url)
        vote_ids = [vote['id'] for vote in response.data]
        self.assertNotIn(closed_vote.id, vote_ids)

    def test_retrieve_vote_allows_initiator_to_see_nomination(self):
        nomination_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.NOMINATION,
            start_time=self.now,
            nomination_end_time=self.now + timedelta(hours=20)
        )

        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('vote-detail', args=[nomination_vote.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], nomination_vote.id)

    def test_retrieve_vote_allows_eligible_user_to_see_active(self):
        active_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            start_time=self.now,
            end_time=self.now + timedelta(hours=4)
        )

        self.client.force_authenticate(user=self.golden1)
        url = reverse('vote-detail', args=[active_vote.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_vote_allows_user_who_already_voted(self):
        active_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            start_time=self.now,
            end_time=self.now + timedelta(hours=4)
        )

        UserVote.objects.create(
            vote=active_vote, voter=self.silver1, decision=UserVote.Decision.AGREE
        )
        self.client.force_authenticate(user=self.silver1)
        url = reverse('vote-detail', args=[active_vote.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_vote_blocks_non_eligible_user(self):
        promotion_vote = Vote.objects.create(
            vote_type=self.promote_golden_type,
            initiator=self.silver1,
            target_user=self.silver1,
            status=Vote.Status.ACTIVE,
            start_time=self.now,
            end_time=self.now + timedelta(hours=24)
        )

        self.client.force_authenticate(user=self.mason)
        url = reverse('vote-detail', args=[promotion_vote.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_vote_blocks_nomination_for_non_initiator(self):
        nomination_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.NOMINATION,
            start_time=self.now,
            nomination_end_time=self.now + timedelta(hours=20)
        )

        self.client.force_authenticate(user=self.golden1)
        url = reverse('vote-detail', args=[nomination_vote.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cast_vote_success(self):
        active_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            start_time=self.now,
            end_time=self.now + timedelta(hours=4)
        )

        self.client.force_authenticate(user=self.golden1)
        url = reverse('vote-cast-vote', args=[active_vote.id])
        data = {'decision': UserVote.Decision.AGREE}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            UserVote.objects.filter(vote=active_vote, voter=self.golden1).exists()
        )

    def test_cast_vote_requires_valid_decision(self):
        active_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            start_time=self.now,
            end_time=self.now + timedelta(hours=4)
        )

        self.client.force_authenticate(user=self.golden1)
        url = reverse('vote-cast-vote', args=[active_vote.id])
        data = {'decision': 'INVALID'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cast_vote_rejects_duplicate_vote(self):
        active_vote = Vote.objects.create(
            vote_type=self.ban_vote_type,
            initiator=self.inquisitor,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            start_time=self.now,
            end_time=self.now + timedelta(hours=4)
        )

        UserVote.objects.create(
            vote=active_vote, voter=self.golden1, decision=UserVote.Decision.AGREE
        )
        self.client.force_authenticate(user=self.golden1)
        url = reverse('vote-cast-vote', args=[active_vote.id])
        data = {'decision': UserVote.Decision.DISAGREE}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class StartPromotionVoteViewTests(BaseVoteTestCase):
    def setUp(self):
        self.url = reverse('start-promotion')

    def test_mason_can_start_promotion(self):
        self.client.force_authenticate(user=self.mason)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.mason.refresh_from_db()
        self.assertTrue(Vote.objects.filter(initiator=self.mason, vote_type=self.promote_silver_type).exists())
        self.assertIsNotNone(self.mason.last_promotion_attempt)

    def test_promotion_fails_if_on_cooldown(self):
        self.mason.last_promotion_attempt = timezone.now() - timedelta(days=10)
        self.mason.save()

        self.client.force_authenticate(user=self.mason)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("once every 42 days", response.data['detail'])

    def test_golden_can_start_architect_vote(self):
        self.architect.delete()
        self.golden1.role_assigned_at = timezone.now() - timedelta(days=50)
        self.golden1.save()

        self.client.force_authenticate(user=self.golden1)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Vote.objects.filter(initiator=self.golden1, vote_type=self.promote_architect_type).exists())

    def test_golden_fails_if_architect_exists(self):
        self.golden1.role_assigned_at = timezone.now() - timedelta(days=50)
        self.golden1.save()

        self.client.force_authenticate(user=self.golden1)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("An Architect already exists", response.data['detail'])

    def test_golden_fails_if_not_in_role_42_days(self):
        self.architect.delete()
        self.golden1.role_assigned_at = timezone.now() - timedelta(days=10)
        self.golden1.save()

        self.client.force_authenticate(user=self.golden1)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("must be a Golden Mason for at least 42 days", response.data['detail'])

    def test_architect_cannot_start_promotion(self):
        self.client.force_authenticate(user=self.architect)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("role cannot be promoted", response.data['detail'])

class NominateForBanViewTests(BaseVoteTestCase):
    def setUp(self):
        self.vote_type = self.ban_vote_type
        self.target_user = self.mason
        self.inactive_user = User.objects.create_user(
            email='inactive@i.com', password=test_password, username='inactive', is_active=False
        )

        self.nomination_vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.NOMINATION,
            start_time=timezone.now(),
            nomination_end_time=timezone.now() + timedelta(hours=20),
            end_time=timezone.now() + timedelta(hours=24)
        )

    def test_nominate_requires_authentication(self):
        url = reverse('nominate-ban')
        response = self.client.post(url, {'target_user_id': self.target_user.id})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nominate_requires_inquisitor(self):
        regular_user = User.objects.create_user(
            email='regular@r.com', password=test_password, username='regular'
        )
        self.client.force_authenticate(user=regular_user)
        url = reverse('nominate-ban')
        response = self.client.post(url, {'target_user_id': self.target_user.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nominate_success(self):
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('nominate-ban')
        data = {'target_user_id': self.target_user.id}
        response = self.client.post(url, data)
        if response.status_code == status.HTTP_200_OK:
            self.nomination_vote.refresh_from_db()
            self.assertEqual(self.nomination_vote.status, Vote.Status.ACTIVE)
            self.assertEqual(self.nomination_vote.target_user, self.target_user)
            self.assertIsNone(self.nomination_vote.nomination_end_time)

    def test_nominate_rejects_invalid_user_id(self):
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('nominate-ban')
        data = {'target_user_id': 99999}
        response = self.client.post(url, data)
        self.assertIn(response.status_code,
                      [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_nominate_rejects_inactive_user(self):
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('nominate-ban')
        data = {'target_user_id': self.inactive_user.id}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nominate_rejects_self_nomination(self):
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('nominate-ban')
        data = {'target_user_id': self.inquisitor.id}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nominate_without_nomination_vote(self):
        Vote.objects.filter(id=self.nomination_vote.id).delete()
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('nominate-ban')
        data = {'target_user_id': self.target_user.id}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nominate_invalid_data(self):
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('nominate-ban')
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SelectInquisitorViewTests(BaseVoteTestCase):
    def setUp(self):
        self.vote_type = self.ban_vote_type
        self.target_user = self.mason

    def test_select_inquisitor_no_candidates(self):
        User.objects.filter(role=Role.GOLDEN).update(role=Role.SILVER)
        url = reverse('scheduler-select-inquisitor')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(is_inquisitor=True).exists())

    def test_select_inquisitor_success(self):
        url = reverse('scheduler-select-inquisitor')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(is_inquisitor=True).count(), 1)
        new_inquisitor = User.objects.get(is_inquisitor=True)
        self.assertIn(new_inquisitor, [self.golden1, self.golden2, self.inquisitor])
        self.assertTrue(
            Vote.objects.filter(
                vote_type=self.vote_type,
                initiator=new_inquisitor,
                status=Vote.Status.NOMINATION
            ).exists()
        )

    def test_select_inquisitor_creates_nomination_vote(self):
        url = reverse('scheduler-select-inquisitor')
        response = self.client.post(url)
        if response.status_code == status.HTTP_201_CREATED:
            new_inquisitor = User.objects.get(is_inquisitor=True)
            vote = Vote.objects.get(initiator=new_inquisitor, status=Vote.Status.NOMINATION)
            self.assertEqual(vote.vote_type, self.vote_type)
            self.assertIsNotNone(vote.nomination_end_time)
            self.assertIsNotNone(vote.end_time)

    def test_select_inquisitor_missing_vote_type(self):
        VoteType.objects.filter(name='BAN').delete()
        url = reverse('scheduler-select-inquisitor')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class EndVoteViewTests(BaseVoteTestCase):
    def setUp(self):
        self.vote_type = self.ban_vote_type
        self.target_user = self.mason

    def test_end_vote_closed_already(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.CLOSED,
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1)
        )
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_end_vote_nomination_expired(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.NOMINATION,
            start_time=timezone.now() - timedelta(hours=2),
            nomination_end_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1)
        )
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vote.refresh_from_db()
        self.assertEqual(vote.status, Vote.Status.CLOSED)
        self.assertEqual(vote.outcome, Vote.Outcome.EXPIRED)

    def test_end_vote_nomination_not_expired(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.NOMINATION,
            start_time=timezone.now(),
            nomination_end_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2)
        )
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vote.refresh_from_db()
        self.assertEqual(vote.status, Vote.Status.NOMINATION)

    def test_end_vote_active_not_yet_ended(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.ACTIVE,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_end_vote_active_passed_with_majority(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.ACTIVE,
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1),
            target_user=self.silver1
        )
        UserVote.objects.create(vote=vote, voter=self.golden1, decision=UserVote.Decision.AGREE)
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vote.refresh_from_db()
        self.assertEqual(vote.status, Vote.Status.CLOSED)
        self.assertEqual(vote.outcome, Vote.Outcome.PASSED)
        self.silver1.refresh_from_db()
        self.assertFalse(self.silver1.is_active)

    def test_end_vote_active_failed_with_majority(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.ACTIVE,
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1),
            target_user=self.silver1
        )
        UserVote.objects.create(vote=vote, voter=self.golden1, decision=UserVote.Decision.DISAGREE)
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vote.refresh_from_db()
        self.assertEqual(vote.status, Vote.Status.CLOSED)
        self.assertEqual(vote.outcome, Vote.Outcome.FAILED)
        self.silver1.refresh_from_db()
        self.assertTrue(self.silver1.is_active)

    def test_end_vote_active_creates_blacklist_on_ban(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.ACTIVE,
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1),
            target_user=self.silver1
        )
        UserVote.objects.create(vote=vote, voter=self.golden1, decision=UserVote.Decision.AGREE)
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            BlacklistedIP.objects.filter(ip_address=ip_address).exists()
        )

    def test_end_vote_active_tie_goes_to_failed(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.ACTIVE,
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1),
            target_user=self.silver1
        )
        UserVote.objects.create(vote=vote, voter=self.golden1, decision=UserVote.Decision.AGREE)
        another_golden = User.objects.create_user(
            email='gold2@g.com', password=test_password, role=Role.GOLDEN, username='gold2'
        )
        UserVote.objects.create(vote=vote, voter=another_golden,
                                decision=UserVote.Decision.DISAGREE)
        url = reverse('scheduler-end-vote', args=[vote.id])
        self.client.post(url)
        vote.refresh_from_db()
        self.assertEqual(vote.outcome, Vote.Outcome.FAILED)

    def test_end_vote_nonexistent_vote(self):
        url = reverse('scheduler-end-vote', args=[99999])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_end_vote_active_passed_no_target_user(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.ACTIVE,
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1)
        )
        UserVote.objects.create(vote=vote, voter=self.golden1, decision=UserVote.Decision.AGREE)
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vote.refresh_from_db()
        self.assertEqual(vote.outcome, Vote.Outcome.PASSED)

    def test_promotion_passes_unanimous_agree(self):
        self.mason.role_assigned_at = timezone.now() - timedelta(days=100)
        self.mason.save()

        vote = Vote.objects.create(
            vote_type=self.promote_silver_type,
            initiator=self.mason,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            end_time=timezone.now() - timedelta(hours=1)
        )

        UserVote.objects.create(vote=vote, voter=self.silver1, decision=UserVote.Decision.AGREE)

        url = reverse('scheduler-end-vote', args=[vote.id])
        self.client.post(url)

        vote.refresh_from_db()
        self.mason.refresh_from_db()

        self.assertEqual(vote.outcome, Vote.Outcome.PASSED)
        self.assertEqual(self.mason.role, Role.SILVER)
        self.assertGreater(self.mason.role_assigned_at,
                           timezone.now() - timedelta(minutes=1))

    def test_promotion_fails_one_disagree(self):
        vote = Vote.objects.create(
            vote_type=self.promote_silver_type,
            initiator=self.mason,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            end_time=timezone.now() - timedelta(hours=1)
        )

        UserVote.objects.create(vote=vote, voter=self.silver1, decision=UserVote.Decision.AGREE)
        UserVote.objects.create(vote=vote, voter=self.silver2, decision=UserVote.Decision.DISAGREE)

        url = reverse('scheduler-end-vote', args=[vote.id])
        self.client.post(url)

        vote.refresh_from_db()
        self.mason.refresh_from_db()

        self.assertEqual(vote.outcome, Vote.Outcome.FAILED)
        self.assertEqual(self.mason.role, Role.MASON)

    def test_promotion_fails_no_votes(self):
        vote = Vote.objects.create(
            vote_type=self.promote_silver_type,
            initiator=self.mason,
            target_user=self.mason,
            status=Vote.Status.ACTIVE,
            end_time=timezone.now() - timedelta(hours=1)
        )

        url = reverse('scheduler-end-vote', args=[vote.id])
        self.client.post(url)

        vote.refresh_from_db()
        self.mason.refresh_from_db()

        self.assertEqual(vote.outcome, Vote.Outcome.FAILED)
        self.assertEqual(self.mason.role, Role.MASON)


class RetireArchitectViewTests(BaseVoteTestCase):
    def setUp(self):
        self.url = reverse('scheduler-retire-architects')

    def test_retire_architect_after_42_days(self):
        self.architect.role_assigned_at = timezone.now() - timedelta(days=50)
        self.architect.is_active = True
        self.architect.save()

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], "Successfully retired 1 architects.")

        self.architect.refresh_from_db()
        self.assertFalse(self.architect.is_active)

    def test_do_not_retire_new_architect(self):
        self.architect.role_assigned_at = timezone.now() - timedelta(days=10)
        self.architect.is_active = True
        self.architect.save()

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], "Successfully retired 0 architects.")

        self.architect.refresh_from_db()
        self.assertTrue(self.architect.is_active)

    def test_retired_architect_ip_is_blacklisted(self):
        self.architect.role_assigned_at = timezone.now() - timedelta(days=50)
        self.architect.is_active = True
        self.architect.last_known_ip = ip_address
        self.architect.save()

        self.client.post(self.url)

        self.architect.refresh_from_db()
        self.assertFalse(self.architect.is_active)
        self.assertTrue(BlacklistedIP.objects.filter(ip_address=ip_address).exists())
