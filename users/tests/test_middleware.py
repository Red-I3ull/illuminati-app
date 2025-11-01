import os
from dotenv import load_dotenv
from django.test import TestCase, RequestFactory
from django.http import JsonResponse, HttpResponseRedirect
from users.models import BlacklistedIP
from users.middleware import IPBlacklistMiddleware

load_dotenv()

ip_address = os.getenv('IP_ADDRESS')
banned_ip = os.getenv('BANNED_IP')

class IPBlacklistMiddlewareTests(TestCase):
    """tests IPBlacklistMiddleware"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = IPBlacklistMiddleware(lambda request: 'OK')

        self.banned_ip = banned_ip
        self.allowed_ip = ip_address
        BlacklistedIP.objects.create(
            ip_address=self.banned_ip,
            reason='Test ban'
        )

        self.middleware.update_blacklist()

    def test_allowed_ip_passes_through(self):
        """tests allowed ip go through middleware"""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = self.allowed_ip
        response = self.middleware(request)
        self.assertEqual(response, 'OK')

    def test_banned_ip_redirects_browser(self):
        """test redirect"""
        with self.settings(BLACKLIST_REDIRECT_URL='/banned/'):
            middleware = IPBlacklistMiddleware(lambda request: 'OK')
            middleware.update_blacklist()
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = self.banned_ip
            request.headers = {}
            response = middleware(request)
            self.assertIsInstance(response, HttpResponseRedirect)
            self.assertEqual(response.url, '/banned/')

    def test_banned_ip_returns_json_for_api(self):
        """test blocked api return json """
        with self.settings(BLACKLIST_REDIRECT_URL='/banned/'):
            middleware = IPBlacklistMiddleware(lambda request: 'OK')
            middleware.update_blacklist()
            request = self.factory.get('/api/votes/')
            request.META['REMOTE_ADDR'] = self.banned_ip
            request.headers = {'Accept': 'application/json'}
            response = middleware(request)
            self.assertIsInstance(response, JsonResponse)
            self.assertEqual(response.status_code, 403)

            import json
            data = json.loads(response.content)
            self.assertIn('error', data)
            self.assertIn('redirect_url', data)

    def test_no_redirect_url_allows_access(self):
        """test access without BLACKLIST_REDIRECT_URL """
        with self.settings(BLACKLIST_REDIRECT_URL=None):
            middleware = IPBlacklistMiddleware(lambda request: 'OK')
            middleware.update_blacklist()
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = self.banned_ip
            response = middleware(request)
            self.assertEqual(response, 'OK')

    def test_no_remote_addr_allows_access(self):
        """test access without REMOTE_ADDR"""
        request = self.factory.get('/')
        if 'REMOTE_ADDR' in request.META:
            del request.META['REMOTE_ADDR']
        response = self.middleware(request)
        self.assertEqual(response, 'OK')

    def test_does_not_redirect_if_already_on_redirect_url(self):
        """test redirect if already on redirect url"""
        with self.settings(BLACKLIST_REDIRECT_URL='/banned/'):
            middleware = IPBlacklistMiddleware(lambda request: 'OK')
            middleware.update_blacklist()
            request = self.factory.get('/banned/')
            request.META['REMOTE_ADDR'] = self.banned_ip
            request.headers = {}
            response = middleware(request)
            self.assertEqual(response, 'OK')

    def test_update_blacklist_refreshes_list(self):
        """test update blacklist"""
        new_ip = ip_address
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = new_ip
        response = self.middleware(request)
        self.assertEqual(response, 'OK')

        BlacklistedIP.objects.create(
            ip_address=new_ip,
            reason='New ban'
        )

        self.middleware.update_blacklist()

        with self.settings(BLACKLIST_REDIRECT_URL='/banned/'):
            middleware = IPBlacklistMiddleware(lambda request: 'OK')
            middleware.update_blacklist()
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = new_ip
            request.headers = {}
            response = middleware(request)
            self.assertIsInstance(response, HttpResponseRedirect)
