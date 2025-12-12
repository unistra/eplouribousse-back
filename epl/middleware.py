class HealthzMiddleware:
    """
    Middleware to handle health check endpoint.

    It is meant to be inserted before django_tenant middleware and to respond
    even when no tenant is not found or configured

    It responds with "ok" for requests to /healthz/
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/healthz/":
            from django.http import HttpResponse

            return HttpResponse("ok", status=200)

        response = self.get_response(request)

        return response
