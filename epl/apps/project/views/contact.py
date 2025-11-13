from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from epl.apps.project.serializers.contact import ContactSupportSerializer


@extend_schema(
    request=ContactSupportSerializer,
    responses={
        status.HTTP_201_CREATED: None,
    },
    description=_("Submit a support contact request"),
)
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
