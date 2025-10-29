from django.contrib.postgres.aggregates import StringAgg
from django.db import models
from django.http import HttpResponse
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _
from django_weasyprint import WeasyTemplateResponse
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from epl.apps.project.filters.resource import ResourceFilter
from epl.apps.project.models import Collection, Resource, ResourceStatus
from epl.apps.project.permissions.resource import ResourcePermission
from epl.apps.project.serializers.common import StatusListSerializer
from epl.apps.project.serializers.resource import (
    ReassignInstructionTurnSerializer,
    ReportAnomaliesSerializer,
    ResetInstructionSerializer,
    ResourceSerializer,
    ResourceWithCollectionsSerializer,
    ValidateControlSerializer,
)
from epl.libs.language import get_user_language
from epl.libs.pagination import PageNumberPagination
from epl.schema_serializers import UnauthorizedSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["collection", "resource"],
        responses={200: ResourceSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["collection", "resource"],
        responses={200: ResourceSerializer()},
    ),
    update=extend_schema(
        tags=["collection", "resource"],
        responses={200: ResourceSerializer()},
    ),
    partial_update=extend_schema(
        tags=["collection", "resource"],
        responses={200: ResourceSerializer()},
    ),
)
class ResourceViewSet(ListModelMixin, UpdateModelMixin, RetrieveModelMixin, GenericViewSet):
    queryset = Resource.objects.prefetch_related("collections").all()
    serializer_class = ResourceSerializer
    permission_classes = [ResourcePermission]
    pagination_class = PageNumberPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, ResourceFilter]
    search_fields = ["title", "=code"]
    ordering_fields = ["title", "count", "status"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "list":
            context.update({"library": self.request.query_params.get("library")})
        if self.action == "collections":
            # The resources won't have anomalies counts, only the collections will have them
            context.update({"hide_anomalies": True})

        return context

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == "list":
            # Annotate with count of collections and aggregated call numbers within the specified project
            project = self.request.query_params.get("project")
            queryset = queryset.annotate(
                count=models.Count(
                    "collections",
                    filter=models.Q(collections__resource__project=project),
                    distinct=True,
                ),
                call_numbers=StringAgg(
                    "collections__call_number",
                    delimiter=", ",
                    filter=models.Q(collections__call_number__isnull=False) & ~models.Q(collections__call_number=""),
                    output_field=models.CharField(),
                ),
                fixed_anomalies=models.Count(
                    "collections__segments__anomalies",
                    filter=models.Q(
                        collections__segments__anomalies__fixed=True,
                    ),
                ),
                unfixed_anomalies=models.Count(
                    "collections__segments__anomalies",
                    filter=models.Q(
                        collections__segments__anomalies__fixed=False,
                    ),
                ),
            )
            queryset = queryset.filter(count__gt=1)
        return queryset

    @extend_schema(
        tags=["collection", "resource"],
        request=None,
        responses={200: StatusListSerializer(many=True)},
        description="List all possible resource statuses.",
        summary="List Resource Statuses",
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="status",
        permission_classes=[AllowAny],
        pagination_class=None,
        filter_backends=[],
    )
    def list_statuses(self, request, pk=None):
        statuses = [{"status": _s[0], "label": _s[1]} for _s in ResourceStatus.choices]
        serializer = StatusListSerializer(statuses, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Retrieve collections for a specific resource",
        description="Returns all collections associated with a specific resource within the same project. ",
        responses=ResourceWithCollectionsSerializer,
        tags=["collection", "resource"],
    )
    @action(detail=True, methods=["get"], url_path="collections")
    def collections(self, request, pk=None):
        resource = self.get_object()
        collections = resource.collections.annotate(
            fixed_anomalies=models.Count(
                "segments__anomalies",
                filter=models.Q(
                    segments__anomalies__fixed=True,
                ),
            ),
            unfixed_anomalies=models.Count(
                "segments__anomalies",
                filter=models.Q(
                    segments__anomalies__fixed=False,
                ),
            ),
        ).all()
        serializer = ResourceWithCollectionsSerializer(
            {
                "resource": resource,
                "collections": collections,
            },
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @extend_schema(
        summary=_("Controller validates the instruction of the resource"),
        request=ValidateControlSerializer(),
        responses={
            status.HTTP_200_OK: ValidateControlSerializer(),
        },
        tags=["instruction", "resource"],
    )
    @action(detail=True, methods=["post"], url_path="control")
    def validate_control(self, request, pk=None):
        """
        Controller validates the current instruction phase (bound copies or unbound copies)
        for the resource
        """
        resource = self.get_object()
        serializer = ValidateControlSerializer(resource, data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        summary=_("Report anomalies"),
        request=None,
        responses={
            status.HTTP_200_OK: ReportAnomaliesSerializer,
        },
        tags=["resource", "anomaly", "instruction"],
    )
    @action(detail=True, methods=["PATCH"], url_path="report-anomalies")
    def report_anomalies(self, request, pk) -> Response:
        """
        Allows controllers or instructors to report anomalies for a specific resource.
        This closes the anomaly creation, sends the notifications and updates the resource status if needed.
        """
        resource = self.get_object()
        serializer = ReportAnomaliesSerializer(
            instance=resource,
            context=self.get_serializer_context(),
            partial=True,
        )
        serializer.report()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary=_("Reset instruction"),
        tags=["resource", "instruction", "anomaly"],
        request=None,
        responses={
            status.HTTP_200_OK: ResetInstructionSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: None,
        },
    )
    @action(detail=True, methods=["PATCH"], url_path="reset")
    def reset_instruction(self, request, pk) -> Response:
        """
        Allows admins to reset the instruction of a resource.
        """
        resource = self.get_object()
        serializer = ResetInstructionSerializer(
            resource,
            context=self.get_serializer_context(),
            partial=True,
        )
        serializer.reset()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary=_("Reassign instruction turns"),
        tags=["resource", "instruction", "anomaly"],
        request=ReassignInstructionTurnSerializer,
        responses={
            status.HTTP_200_OK: ReassignInstructionTurnSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: None,
        },
    )
    @action(detail=True, methods=["PATCH"], url_path="reassign-turn")
    def reassign_instruction_turn(self, request, pk) -> Response:
        resource = self.get_object()
        serializer = ReassignInstructionTurnSerializer(
            resource,
            data=request.data,
            context=self.get_serializer_context(),
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.reassign()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary=_("Get resultant report in PDF format"),
        tags=["resource"],
        request=None,
        responses={
            status.HTTP_200_OK: {"type": "object", "properties": {"report": {"type": "string"}}},
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: None,
        },
    )
    @action(detail=True, methods=["GET"], url_path="resultant-report")
    def resultant_report(self, request, pk) -> HttpResponse:
        collection_id = request.query_params.get("collection", None)
        resource = self.get_object()
        if resource.status < ResourceStatus.EDITION:
            return Response(
                {"detail": _("Resultant report is only available for resources in EDITION status or beyond.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            collection = resource.collections.get(id=collection_id)
        except Collection.DoesNotExist:
            return Response(
                {"detail": _("A valid collection ID must be provided to generate the resultant report.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        language_code = request.query_params.get("lang") or get_user_language(request.user, resource.project)
        context = {
            "now": timezone.now(),
            "resource": resource,
            "collection": collection,
            "main_collection": resource.collections.order_by("position").first(),
            "participating_collections": resource.collections.exclude(id=collection.id, position=0)
            .order_by("position")
            .all(),
            "excluded_collections": resource.collections.filter(position=0).all(),
            "segments": resource.segments.order_by("order").all(),
            "language_code": language_code,
        }
        filename = f"resultant-report-{resource.code}-{collection.library.code}.pdf"
        with translation.override(language_code):
            if request.query_params.get("preview") == "true":
                from django.shortcuts import render

                return render(request, "pdf/resulting-report.html", context)
            else:
                return WeasyTemplateResponse(
                    request,
                    "pdf/resulting-report.html",
                    context=context,
                    attachment=True,
                    filename=filename,
                )
