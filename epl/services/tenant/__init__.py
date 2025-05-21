from django.http import HttpRequest
from rest_framework.request import Request


def get_front_domain(request: HttpRequest | Request, port: str = None) -> str:
    tenant = request.tenant
    if port is None and request.scheme == "http":
        port = "5173"
    return f"{request.scheme}://{tenant.get_primary_domain().front_domain}{':' + port if port else ''}"
