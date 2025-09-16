import csv
import io
import logging
from collections import Counter

from django.db import transaction
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Collection, Library, Project, Resource, ResourceStatus
from epl.apps.project.models.collection import Arbitration
from epl.apps.project.models.comment import Comment
from epl.apps.project.permissions.collection import CollectionPermission
from epl.libs.csv_import import handle_import
from epl.services.permissions.serializers import AclField, AclSerializerMixin
from epl.services.project.notifications import notify_instructors_of_arbitration

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = (
    "Titre",
    "PPN",
)


class CollectionSerializer(serializers.ModelSerializer):
    library = serializers.PrimaryKeyRelatedField(
        queryset=Library.objects.all(),
        help_text=_("Library to which the collection belongs"),
        required=True,
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),  # Verify that the project exists
        help_text=_("Project to which the collection belongs"),
        required=True,
    )
    code = serializers.CharField(read_only=True, source="resource.code")
    title = serializers.CharField(read_only=True, source="resource.title")

    class Meta:
        model = Collection
        fields = [
            "id",
            "title",
            "code",
            "library",
            "project",
            "issn",
            "call_number",
            "hold_statement",
            "missing",
            "publication_history",
            "numbering",
            "notes",
        ]
        read_only_fields = ["id"]


class ImportSerializer(serializers.Serializer):
    csv_file = serializers.FileField(required=True, help_text=_("CSV file to be imported."), write_only=True)
    library = serializers.UUIDField(required=True, help_text=_("Library ID to which the collection belongs."))
    project = serializers.UUIDField(required=True, help_text=_("Project ID to which the collection belongs."))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.csv_reader = None

    def get_file_reader(self, csv_file):
        if not self.csv_reader:
            self.csv_reader = csv.DictReader(
                io.StringIO(csv_file.read().decode("utf-8-sig")),
                delimiter=";",
            )

        return self.csv_reader

    @transaction.atomic
    def save(self):
        csv_file = self.validated_data["csv_file"]
        csv_reader = self.get_file_reader(csv_file)

        user = self.context.get("request").user
        library = self.validated_data.get("library")
        project = self.validated_data.get("project")
        resource_ids_to_replace = {}  # To track resources that were already in the database

        collections, resources, codes, errors = handle_import(csv_reader, library.id, project.id, user.id)

        if errors:
            raise serializers.ValidationError({"csv_file": [{"row": row, "errors": errs} for row, errs in errors]})
        else:
            # Resource may already be imported for a project, we need to check
            for resource in resources:
                resource_in_database, _created = Resource.objects.get_or_create(
                    project_id=project.id, code=resource.code, defaults={"id": resource.id, "title": resource.title}
                )
                if not _created:
                    # If the resource already existed, we need to reuse the existing resource ID when creating collections
                    resource_ids_to_replace[resource.id] = resource_in_database.id

            for collection in collections:
                Collection.objects.create(
                    issn=collection.issn,
                    call_number=collection.call_number,
                    hold_statement=collection.hold_statement,
                    missing=collection.missing,
                    # replace with existing resource ID if it existed, else use the new one
                    resource_id=resource_ids_to_replace.get(collection.resource_id) or collection.resource_id,
                    created_by_id=collection.created_by_id,
                    project_id=collection.project_id,
                    library_id=collection.library_id,
                )

        loaded_collections = {_code: _data["count"] for _code, _data in codes.items()}

        return Counter(loaded_collections.values())

    def validate_csv_file(self, value):
        csv_reader = self.get_file_reader(value)
        if missing_field := [field for field in REQUIRED_FIELDS if field not in csv_reader.fieldnames]:
            raise serializers.ValidationError(
                _("Column(s) %(column)s missing in the CSV file.") % {"column": ", ".join(missing_field)}
            )

        return value

    def validate_library(self, value):
        try:
            library = Library.objects.get(pk=value)
        except Library.DoesNotExist:
            raise serializers.ValidationError(_("Library with ID %(id)s does not exist.") % {"id": value})

        return library

    def validate_project(self, value):
        try:
            project = Project.objects.get(pk=value)
        except Project.DoesNotExist:
            raise serializers.ValidationError(_("Project with ID %(id)s does not exist.") % {"id": value})
        return project

    def validate(self, attrs):
        project = attrs.get("project")
        library = attrs.get("library")
        if project.projectlibrary_set.filter(library=library, is_alternative_storage_site=True).exists():
            raise serializers.ValidationError(_("An alternative storage site can't receive a collection"))

        return attrs


class MoveToInstructionMixin:
    def move_to_instruction_if_possible(self, collections: QuerySet[Collection], resource: Resource) -> None:
        if all(c.position is not None for c in collections) and resource.arbitration is Arbitration.NONE:
            # All libraries have positioned and no arbitration is needed: move to Instruction Bound and set turns
            resource.status = ResourceStatus.INSTRUCTION_BOUND
            turns: list[str] = [str(_collection.library_id) for _collection in collections.order_by("position")]
            resource.instruction_turns["bound_copies"]["turns"] = turns.copy()
            resource.instruction_turns["unbound_copies"]["turns"] = turns.copy()
            resource.save(update_fields=["status", "instruction_turns"])


class PositionSerializer(MoveToInstructionMixin, serializers.ModelSerializer):
    position = serializers.IntegerField(min_value=1, max_value=4, help_text=_("Position (rank) between 1 and 4"))
    arbitration = serializers.ChoiceField(Arbitration, read_only=True, source="resource.arbitration")
    status = serializers.ChoiceField(ResourceStatus, read_only=True, source="resource.status")

    class Meta:
        model = Collection
        fields = ["position", "arbitration", "status"]

    def save(self, **kwargs):
        position = self.validated_data["position"]
        collection = self.instance
        collection.position = position
        collection.exclusion_reason = ""
        collection.save(update_fields=["position", "exclusion_reason"])

        resource = collection.resource
        collections = resource.collections.all()
        is_other_first = collections.filter(position=1).exclude(pk=collection.pk).exists()

        arbitration: Arbitration = Arbitration.NONE

        if position == 1 and is_other_first:
            arbitration = Arbitration.ONE
        elif (
            (positions := list(collections.values_list("position", flat=True)))
            and 1 not in positions
            and all(c.position is not None or c.exclusion_reason for c in collections)
        ):
            arbitration = Arbitration.ZERO

        resource.arbitration = arbitration
        resource.save(update_fields=["arbitration"])

        if resource.arbitration in [Arbitration.ONE, Arbitration.ZERO]:
            notify_instructors_of_arbitration(resource, self.context["request"])

        self.move_to_instruction_if_possible(collections, resource)

        return collection


class ExclusionSerializer(MoveToInstructionMixin, serializers.ModelSerializer):
    exclusion_reason = serializers.CharField(
        max_length=255,
        required=True,
        allow_blank=False,
        help_text=_("Reason for excluding the collection from deduplication"),
    )
    arbitration = serializers.ChoiceField(Arbitration, read_only=True, source="resource.arbitration")
    status = serializers.ChoiceField(ResourceStatus, read_only=True, source="resource.status")

    class Meta:
        model = Collection
        fields = ["exclusion_reason", "arbitration", "status"]

    def validate_exclusion_reason(self, value):
        collection = self.instance
        project = collection.project
        if value not in project.exclusion_reasons:
            raise serializers.ValidationError(_("Invalid exclusion reason."))
        return value

    def update(self, instance: Collection, validated_data):
        instance.position = 0
        instance.exclusion_reason = validated_data["exclusion_reason"]
        instance.save()

        resource = instance.resource
        collections = resource.collections.all()

        if (
            (positions := list(collections.values_list("position", flat=True)))
            and 1 not in positions
            and all(c.position is not None or c.exclusion_reason for c in collections)
        ):
            arbitration = Arbitration.ZERO
        else:
            arbitration = Arbitration.NONE

        resource.arbitration = arbitration
        resource.save(update_fields=["arbitration"])

        self.move_to_instruction_if_possible(collections, resource)

        return instance


class PositioningCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["id", "content", "author", "created_at"]
        read_only_fields = ["id", "subject", "author", "created_at"]

    def create(self, validated_data):
        validated_data["subject"] = _("Positioning comment")  # Set a default subject for the comment
        validated_data["author"] = self.context["request"].user  # Set the author to the current user
        return super().create(validated_data)


class CollectionPositioningSerializer(AclSerializerMixin, serializers.ModelSerializer):
    """
    Used to serialize the collection's positioning information.
    Is used in the ResourceSerializer as nested serializer.
    """

    acl = AclField(permission_classes=[CollectionPermission])
    comment_positioning = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = [
            "id",
            "library",
            "call_number",
            "hold_statement",
            "position",
            "is_excluded",
            "exclusion_reason",
            "comment_positioning",
            "acl",
        ]

    def get_comment_positioning(self, obj):
        comment = obj.comments.filter(subject=_("Positioning comment")).order_by("-created_at").first()
        if comment:
            return PositioningCommentSerializer(comment).data
        return None
