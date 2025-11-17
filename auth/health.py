from django.http import HttpResponse

def health(_):
    """Health check view that returns 'OK'."""
    return HttpResponse("OK", status=200)
