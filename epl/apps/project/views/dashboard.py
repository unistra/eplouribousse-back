from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.response import Response

from epl.apps.project.models import Project
from epl.apps.project.serializers.dashboard import (
    ExclusionInformationSerializer,
    InitialDataSerializer,
    PositioningInformationSerializer,
)


class ProjectDashboardViewSet(viewsets.GenericViewSet):
    """
    ViewSet to retrieve dashboard data for a specific project.
    The data returned depends on the 'board' query parameter.
    """

    queryset = Project.objects.all()
    pagination_class = None

    def get_serializer_class(self):
        """Return the serializer class based on the 'board' query param."""
        board = self.request.query_params.get("board", "initial-data")
        serializer_map = {
            "initial-data": InitialDataSerializer,
            "positioning-information": PositioningInformationSerializer,
            "exclusion-information": ExclusionInformationSerializer,
        }
        return serializer_map.get(board, InitialDataSerializer)

    @extend_schema(
        tags=["project", "dashboard"],
        summary="Get dashboard data for a project",
        parameters=[
            OpenApiParameter(
                name="board",
                type=str,
                location=OpenApiParameter.QUERY,
                description="The dashboard section to retrieve.",
                enum=["initial-data", "positioning-information", "exclusion-information"],
                default="initial-data",
            )
        ],
        responses={200: InitialDataSerializer},
    )
    def list(self, request, project_pk=None):
        """
        Retrieve dashboard data for the given project.
        The specific data is determined by the 'board' query parameter.
        """
        project = self.get_queryset().get(pk=project_pk)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(instance=project)
        return Response(serializer.data)
