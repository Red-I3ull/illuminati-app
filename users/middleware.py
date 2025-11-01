from django.http import HttpResponseRedirect, JsonResponse
from django.conf import settings
from .models import BlacklistedIP

class IPBlacklistMiddleware:
    """
    Checks incoming requests against the IP blacklist.
    for browser navigation, sends a 302 redirect.
    for API requests (ajax/fetch), sends a 403 JSON response.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.blacklist = set(BlacklistedIP.objects.values_list('ip_address', flat=True))
        self.redirect_url = getattr(settings, 'BLACKLIST_REDIRECT_URL', None)

    def __call__(self, request):
        ip = request.META.get('REMOTE_ADDR')

        if ip and self.redirect_url and ip in self.blacklist:
            is_api_request = 'application/json' in request.headers.get('Accept', '')

            if is_api_request:
                return JsonResponse(
                    {'error': 'Access denied from this IP.', 'redirect_url': self.redirect_url},
                    status=403
                )
            else:
                if not request.path.startswith(self.redirect_url):
                    return HttpResponseRedirect(self.redirect_url)

        response = self.get_response(request)
        return response

    # I can call this later via signals to refresh the list
    # without restarting the server.
    def update_blacklist(self):
        self.blacklist = set(BlacklistedIP.objects.values_list('ip_address', flat=True))