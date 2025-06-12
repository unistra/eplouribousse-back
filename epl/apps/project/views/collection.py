from rest_framework import mixins, parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from epl.apps.project.models import Collection
from epl.apps.project.serializers.collection import CollectionSerializer, ImportSerializer


class CollectionViewSet(mixins.ListModelMixin, GenericViewSet):
    """
    View for listing and importing a collection from a CSV file.
    """

    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer
    # add permission classes if needed
    # Pagination classes ?
    # permission_classes = [IsAuthenticated]

    @action(
        methods=["post"],
        detail=False,
        url_path="import-csv",
        url_name="import_csv",
        parser_classes=[parsers.MultiPartParser],
    )
    def import_csv(self, request, *args, **kwargs):
        """
        Handle the POST request to import a collection from a CSV file.
        The request should look like this:
        r = requests.post(url, files='csv_file')
        The library and project IDs should be passed in the request data.
        """
        serializer = ImportSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
