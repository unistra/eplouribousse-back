from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django_smart_ratelimit import rate_limit
from drf_spectacular.utils import extend_schema
from ipware import get_client_ip
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from epl.apps.project.serializers.contact import ContactSupportSerializer


def ratelimit_key(_request, *args, **kwargs) -> str:
    ip, _ = get_client_ip(_request)
    if _request.tenant:
        return f"epl-rl:contact:{_request.tenant.id}-{ip}"
    return ip


@extend_schema(
    request=ContactSupportSerializer,
    responses={
        status.HTTP_201_CREATED: None,
    },
    description=_("Submit a support contact request"),
)
@rate_limit(key=ratelimit_key, rate=settings.CONTACT_FORM_RATELIMIT, block=True)
@api_view(["POST"])
def support(request):
    if request.method != "POST":
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    serializer = ContactSupportSerializer(
        data=request.data,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response(status=status.HTTP_201_CREATED)
