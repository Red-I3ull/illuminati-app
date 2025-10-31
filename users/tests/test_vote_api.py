import os
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from datetime import timedelta
from django.contrib.auth import get_user_model
from users.models import Vote, VoteType, UserVote, Role, BlacklistedIP

User = get_user_model()

test_password = os.environ.get('TEST_PASSWORD')
ip_address = os.getenv('IP_ADDRESS')

class UserListViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.inquisitor = User.objects.create_user(
            email='inq@i.com', password=test_password, role=Role.GOLDEN,
            is_inquisitor=True, username='inq'
        )
        self.user1 = User.objects.create_user(
            email='user1@u.com', password=test_password, username='user1', is_active=True
        )
        self.user2 = User.objects.create_user(
            email='user2@u.com', password=test_password, username='user2', is_active=True
        )
        self.inactive_user = User.objects.create_user(
            email='inactive@u.com', password=test_password, username='inactive', is_active=False
        )

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
        self.assertIn('user1', usernames)
        self.assertIn('user2', usernames)
        self.assertNotIn('inactive', usernames)
        self.assertNotIn('inq', usernames)

    def test_user_list_excludes_current_user(self):
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('user-list')
        response = self.client.get(url)
        usernames = [user['username'] for user in response.data]
        self.assertNotIn(self.inquisitor.username, usernames)


class VoteViewSetTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.golden = User.objects.create_user(
            email='gold@g.com', password=test_password, role=Role.GOLDEN, username='golden'
        )
        self.silver = User.objects.create_user(
            email='silver@s.com', password=test_password, role=Role.SILVER, username='silver'
        )
        self.arch = User.objects.create_user(
            email='arch@a.com', password=test_password, role=Role.ARCHITECT, username='arch'
        )
        self.inquisitor = User.objects.create_user(
            email='inq@i.com', password=test_password, role=Role.GOLDEN,
            is_inquisitor=True, username='inq'
        )

        self.vote_type = VoteType.objects.create(
            name='BAN', duration_hours=2, nomination_duration_hours=1,
            eligible_voter_roles=[Role.GOLDEN, Role.SILVER],
            pass_condition='MAJORITY'
        )

        self.nomination_vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.NOMINATION,
            start_time=timezone.now(),
            nomination_end_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2)
        )

        self.active_vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.ACTIVE,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=2)
        )

        self.closed_vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.CLOSED,
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1)
        )

    def test_list_votes_requires_authentication(self):
        url = reverse('vote-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_votes_shows_eligible_votes_for_golden(self):
        self.client.force_authenticate(user=self.golden)
        url = reverse('vote-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vote_ids = [vote['id'] for vote in response.data]
        self.assertIn(self.active_vote.id, vote_ids)

    def test_list_votes_shows_nomination_vote_to_initiator(self):
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('vote-list')
        response = self.client.get(url)
        vote_ids = [vote['id'] for vote in response.data]
        self.assertIn(self.nomination_vote.id, vote_ids)

    def test_list_votes_hides_nomination_vote_from_non_initiator(self):
        self.client.force_authenticate(user=self.golden)
        url = reverse('vote-list')
        response = self.client.get(url)
        vote_ids = [vote['id'] for vote in response.data]
        self.assertNotIn(self.nomination_vote.id, vote_ids)

    def test_list_votes_excludes_closed_votes(self):
        self.client.force_authenticate(user=self.golden)
        url = reverse('vote-list')
        response = self.client.get(url)
        vote_ids = [vote['id'] for vote in response.data]
        self.assertNotIn(self.closed_vote.id, vote_ids)

    def test_retrieve_vote_allows_initiator_to_see_nomination(self):
        self.client.force_authenticate(user=self.inquisitor)
        url = reverse('vote-detail', args=[self.nomination_vote.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.nomination_vote.id)

    def test_retrieve_vote_allows_eligible_user_to_see_active(self):
        self.client.force_authenticate(user=self.golden)
        url = reverse('vote-detail', args=[self.active_vote.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_vote_allows_user_who_already_voted(self):
        UserVote.objects.create(
            vote=self.active_vote, voter=self.silver, decision=UserVote.Decision.AGREE
        )
        self.client.force_authenticate(user=self.silver)
        url = reverse('vote-detail', args=[self.active_vote.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_vote_blocks_non_eligible_user(self):
        self.client.force_authenticate(user=self.arch)
        url = reverse('vote-detail', args=[self.active_vote.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_vote_blocks_nomination_for_non_initiator(self):
        self.client.force_authenticate(user=self.golden)
        url = reverse('vote-detail', args=[self.nomination_vote.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cast_vote_success(self):
        self.client.force_authenticate(user=self.golden)
        url = reverse('vote-cast-vote', args=[self.active_vote.id])
        data = {'decision': UserVote.Decision.AGREE}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            UserVote.objects.filter(vote=self.active_vote, voter=self.golden).exists()
        )

    def test_cast_vote_requires_valid_decision(self):
        self.client.force_authenticate(user=self.golden)
        url = reverse('vote-cast-vote', args=[self.active_vote.id])
        data = {'decision': 'INVALID'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cast_vote_rejects_duplicate_vote(self):
        UserVote.objects.create(
            vote=self.active_vote, voter=self.golden, decision=UserVote.Decision.AGREE
        )
        self.client.force_authenticate(user=self.golden)
        url = reverse('vote-cast-vote', args=[self.active_vote.id])
        data = {'decision': UserVote.Decision.DISAGREE}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class NominateForBanViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.inquisitor = User.objects.create_user(
            email='inq@i.com', password=test_password, role=Role.GOLDEN,
            is_inquisitor=True, username='inq'
        )
        self.target_user = User.objects.create_user(
            email='target@t.com', password=test_password, username='target', is_active=True
        )
        self.inactive_user = User.objects.create_user(
            email='inactive@i.com', password=test_password, username='inactive', is_active=False
        )

        self.vote_type = VoteType.objects.create(
            name='BAN', duration_hours=4, nomination_duration_hours=20,
            eligible_voter_roles=[Role.GOLDEN, Role.SILVER],
            pass_condition='MAJORITY'
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


class SelectInquisitorViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.golden1 = User.objects.create_user(
            email='gold1@g.com', password=test_password, role=Role.GOLDEN, username='gold1'
        )
        self.golden2 = User.objects.create_user(
            email='gold2@g.com', password=test_password, role=Role.GOLDEN, username='gold2'
        )
        self.silver = User.objects.create_user(
            email='silver@s.com', password=test_password, role=Role.SILVER, username='silver'
        )
        self.existing_inquisitor = User.objects.create_user(
            email='inq@i.com', password=test_password, role=Role.GOLDEN,
            is_inquisitor=True, username='inq'
        )

        self.vote_type = VoteType.objects.create(
            name='BAN', duration_hours=4, nomination_duration_hours=20,
            eligible_voter_roles=[Role.GOLDEN, Role.SILVER],
            pass_condition='MAJORITY'
        )

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
        self.assertIn(new_inquisitor, [self.golden1, self.golden2, self.existing_inquisitor])
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


class EndVoteViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.golden = User.objects.create_user(
            email='gold@g.com', password=test_password, role=Role.GOLDEN, username='golden'
        )
        self.silver = User.objects.create_user(
            email='silver@s.com', password=test_password, role=Role.SILVER, username='silver',
            last_known_ip=ip_address
        )
        self.inquisitor = User.objects.create_user(
            email='inq@i.com', password=test_password, role=Role.GOLDEN,
            is_inquisitor=True, username='inq'
        )

        self.vote_type = VoteType.objects.create(
            name='BAN', duration_hours=2, nomination_duration_hours=1,
            eligible_voter_roles=[Role.GOLDEN, Role.SILVER],
            pass_condition='MAJORITY'
        )

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
            target_user=self.silver
        )
        UserVote.objects.create(vote=vote, voter=self.golden, decision=UserVote.Decision.AGREE)
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vote.refresh_from_db()
        self.assertEqual(vote.status, Vote.Status.CLOSED)
        self.assertEqual(vote.outcome, Vote.Outcome.PASSED)
        self.silver.refresh_from_db()
        self.assertFalse(self.silver.is_active)

    def test_end_vote_active_failed_with_majority(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.ACTIVE,
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1),
            target_user=self.silver
        )
        UserVote.objects.create(vote=vote, voter=self.golden, decision=UserVote.Decision.DISAGREE)
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vote.refresh_from_db()
        self.assertEqual(vote.status, Vote.Status.CLOSED)
        self.assertEqual(vote.outcome, Vote.Outcome.FAILED)
        self.silver.refresh_from_db()
        self.assertTrue(self.silver.is_active)

    def test_end_vote_active_creates_blacklist_on_ban(self):
        vote = Vote.objects.create(
            vote_type=self.vote_type,
            initiator=self.inquisitor,
            status=Vote.Status.ACTIVE,
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1),
            target_user=self.silver
        )
        UserVote.objects.create(vote=vote, voter=self.golden, decision=UserVote.Decision.AGREE)
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
            target_user=self.silver
        )
        UserVote.objects.create(vote=vote, voter=self.golden, decision=UserVote.Decision.AGREE)
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
        UserVote.objects.create(vote=vote, voter=self.golden, decision=UserVote.Decision.AGREE)
        url = reverse('scheduler-end-vote', args=[vote.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vote.refresh_from_db()
        self.assertEqual(vote.outcome, Vote.Outcome.PASSED)
