from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from epl.apps.user.serializers import PasswordChangeSerializer
from epl.services.user.email import send_password_change_email


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def change_password(request: Request) -> Response:
    serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()

    send_password_change_email(request.user)
    return Response({"detail": _("Your password has been changed successfully.")}, status=status.HTTP_200_OK)
