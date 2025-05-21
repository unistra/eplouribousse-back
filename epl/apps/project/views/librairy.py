from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from epl.apps.project.models.library import Library
from epl.apps.project.serializers.library import LibrairySerializer
from epl.libs.pagination import PageNumberPagination


class LibraryViewset(viewsets.ModelViewSet):
    """
    ViewSet to handle all Librairy operations.
    """

    queryset = Library.objects.all()
    serializer_class = LibrairySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
