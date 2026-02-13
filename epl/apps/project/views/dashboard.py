from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from epl.apps.project.models import Project
from epl.apps.project.serializers.dashboard import (
    AchievementsInformationSerializer,
    AnomaliesInformationSerializer,
    ArbitrationInformationSerializer,
    CollectionOccurrencesChartSerializer,
    ControlsInformationSerializer,
    ExclusionInformationSerializer,
    InitialDataSerializer,
    InstructionCandidatesInformationSerializer,
    InstructionsInformationSerializer,
    PositioningInformationSerializer,
    RealizedPositioningChartSerializer,
    ResourcesToInstructChartSerializer,
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
        board = (self.request.query_params.get("board", "initial-data") or "initial-data").strip().lower()
        serializer_map = {
            "initial-data": InitialDataSerializer,
            "positioning-information": PositioningInformationSerializer,
            "exclusion-information": ExclusionInformationSerializer,
            "arbitration-information": ArbitrationInformationSerializer,
            "instruction-candidates-information": InstructionCandidatesInformationSerializer,
            "instructions-information": InstructionsInformationSerializer,
            "controls-information": ControlsInformationSerializer,
            "anomalies-information": AnomaliesInformationSerializer,
            "achievements-information": AchievementsInformationSerializer,
            "realized-positioning-per-library": RealizedPositioningChartSerializer,
            "resources-to-instruct-per-library": ResourcesToInstructChartSerializer,
            "collection-occurrences-per-library": CollectionOccurrencesChartSerializer,
        }
        if board in serializer_map:
            return serializer_map[board]
        raise NotFound(detail=f"Board '{board}' not found")

    @extend_schema(
        tags=["project", "dashboard"],
        summary="Get dashboard data for a project",
        parameters=[
            OpenApiParameter(
                name="board",
                type=str,
                location=OpenApiParameter.QUERY,
                description="The dashboard section to retrieve.",
                enum=[
                    "initial-data",
                    "positioning-information",
                    "exclusion-information",
                    "arbitration-information",
                    "instruction-candidates-information",
                    "instructions-information",
                    "controls-information",
                    "anomalies-information",
                    "achievements-information",
                    "realized-positioning-per-library",
                    "resources-to-instruct-per-library",
                    "collection-occurrences-per-library",
                ],
                default="initial-data",
            ),
            OpenApiParameter(
                name="project_pk",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description="The UUID of the project for which to retrieve dashboard data.",
            ),
        ],
        responses={200: InitialDataSerializer},
    )
    def list(self, request, project_pk=None):
        """
        Retrieve dashboard data for the given project.
        The specific data is determined by the 'board' query parameter.
        """
        project = get_object_or_404(self.get_queryset(), pk=project_pk)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(instance=project, context={"request": request})
        return Response(serializer.data)
