from django.http import HttpRequest
from rest_framework.request import Request


def get_front_domain(request: HttpRequest | Request, port: str = None) -> str:
    tenant = request.tenant

    if "localhost" in tenant.get_primary_domain().domain:
        port = "5173"
        scheme = "http"
    else:
        scheme = "https"

    return f"{scheme}://{tenant.get_primary_domain().front_domain}{':' + port if port else ''}"
