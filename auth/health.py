from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"])
def health(request):
    """Health check view that returns 'OK'."""
    return HttpResponse("OK", status=200)
