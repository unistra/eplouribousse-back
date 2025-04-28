from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import ConsortiumSerializer


@api_view(["GET"])
def consortium_info(request):
    """
    Display consortium information.
    """
    consortium = request.tenant
    serializer = ConsortiumSerializer(consortium)
    return Response(serializer.data, status=status.HTTP_200_OK)
