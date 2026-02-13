from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import ConsortiumSerializer


@extend_schema(
    summary="Consortium Information",
    description="Retrieve information about the consortium.",
    tags=["Tenant"],
    responses={
        status.HTTP_200_OK: ConsortiumSerializer,
        status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
    },
)
@api_view(["GET"])
def consortium_info(request):
    """
    Display consortium information.
    """
    consortium = request.tenant
    serializer = ConsortiumSerializer(consortium)
    return Response(serializer.data, status=status.HTTP_200_OK)
