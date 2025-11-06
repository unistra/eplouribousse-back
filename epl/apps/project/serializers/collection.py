import csv
import io
import logging
from collections import Counter

from django.db import transaction
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from sentry_sdk import set_tag

from epl.apps.project.models import ActionLog, Collection, Library, Project, Resource, ResourceStatus
from epl.apps.project.models.collection import Arbitration, TurnType
from epl.apps.project.models.comment import Comment
from epl.apps.project.permissions.collection import CollectionPermission
from epl.apps.project.serializers.mixins import ResourceInstructionMixin
from epl.libs.csv_import import handle_import
from epl.services.permissions.serializers import AclField, AclSerializerMixin
from epl.services.project.notifications import (
    notify_controllers_of_control,
    notify_instructors_of_arbitration,
    notify_instructors_of_instruction_turn,
    notify_other_instructors_of_positioning,
)

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
            "call_number",
            "hold_statement",
            "missing",
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
        # resources_in_database = Resource.objects.filter(project_id=project.id).only("id", "code")
        existing_resources = {
            _res.code: _res.id for _res in Resource.objects.filter(project_id=project.id).only("id", "code")
        }
        resources_to_create = []
        collections_to_create = []

        if errors:
            raise serializers.ValidationError({"csv_file": [{"row": row, "errors": errs} for row, errs in errors]})
        else:
            # Resource may already be imported for a project, we need to check
            for resource in resources:
                if resource.code in existing_resources:
                    # Resource already exists, reuse its ID
                    resource_ids_to_replace[resource.id] = existing_resources[resource.code]
                else:
                    # Create the resource
                    resources_to_create.append(
                        Resource(
                            project_id=project.id,
                            code=resource.code,
                            issn=resource.issn,
                            publication_history=resource.publication_history,
                            numbering=resource.numbering,
                            title=resource.title,
                            id=resource.id,
                        )
                    )

            BATCH_SIZE = 500
            for i in range(0, len(resources_to_create), BATCH_SIZE):
                batch = resources_to_create[i : i + BATCH_SIZE]
                Resource.objects.bulk_create(batch)

            for collection in collections:
                collections_to_create.append(
                    Collection(
                        call_number=collection.call_number,
                        hold_statement=collection.hold_statement,
                        missing=collection.missing,
                        # replace with existing resource ID if it existed, else use the new one
                        resource_id=resource_ids_to_replace.get(collection.resource_id) or collection.resource_id,
                        created_by_id=collection.created_by_id,
                        project_id=collection.project_id,
                        library_id=collection.library_id,
                    )
                )

            for i in range(0, len(collections_to_create), BATCH_SIZE):
                batch = collections_to_create[i : i + BATCH_SIZE]
                Collection.objects.bulk_create(batch)

        loaded_collections = {_code: _data["count"] for _code, _data in codes.items()}
        ActionLog.log(
            f"Imported {len(collections_to_create)} collections in {library.name}",
            actor=user,
            obj=project,
            request=self.context.get("request"),
        )

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
            turns: list[TurnType] = resource.calculate_turns()
            resource.instruction_turns["bound_copies"]["turns"] = turns.copy()
            resource.instruction_turns["unbound_copies"]["turns"] = turns.copy()
            resource.instruction_turns["turns"] = turns.copy()  # Save turns in case of reset or later reassignment
            resource.save(update_fields=["status", "instruction_turns"])
            ActionLog.log(
                f"Resource status moved to {ResourceStatus(resource.status).name}",
                actor=self.context["request"].user,
                obj=resource,
                request=self.context["request"],
            )

            # Send email to instructors of the first collection to be instructed
            if turns:
                library_to_instruct = Library.objects.get(pk=turns[0]["library"])
                notify_instructors_of_instruction_turn(resource, library_to_instruct, self.context["request"])


class PositionSerializer(MoveToInstructionMixin, ResourceInstructionMixin, serializers.ModelSerializer):
    position = serializers.IntegerField(min_value=1, max_value=4, help_text=_("Position (rank) between 1 and 4"))
    arbitration = serializers.ChoiceField(Arbitration, read_only=True, source="resource.arbitration")
    status = serializers.ChoiceField(ResourceStatus, read_only=True, source="resource.status")
    should_instruct = serializers.SerializerMethodField()
    should_position = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = ["position", "arbitration", "status", "should_instruct", "should_position"]

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
            ActionLog.log(
                f"Resource in Arbitration {Arbitration(resource.arbitration).name}",
                actor=self.context["request"].user,
                obj=resource,
                request=self.context["request"],
            )

        # si au moins une autre collection n'a pas encore été positionnée, on envoie le message de positionnement
        if any(c.position is None for c in collections):
            notify_other_instructors_of_positioning(
                resource=resource, request=self.context["request"], positioned_collection=collection
            )

        self.move_to_instruction_if_possible(collections, resource)

        return collection


class ExclusionSerializer(MoveToInstructionMixin, ResourceInstructionMixin, serializers.ModelSerializer):
    exclusion_reason = serializers.CharField(
        max_length=255,
        required=True,
        allow_blank=False,
        help_text=_("Reason for excluding the collection from deduplication"),
    )
    arbitration = serializers.ChoiceField(Arbitration, read_only=True, source="resource.arbitration")
    status = serializers.ChoiceField(ResourceStatus, read_only=True, source="resource.status")
    should_instruct = serializers.SerializerMethodField()
    should_position = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = ["exclusion_reason", "arbitration", "status", "should_instruct", "should_position"]

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

        if resource.arbitration == Arbitration.ZERO:
            notify_instructors_of_arbitration(resource, self.context["request"])

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
    anomalies = serializers.SerializerMethodField()

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
            "anomalies",
            "acl",
        ]

    @extend_schema_field(PositioningCommentSerializer(many=True))
    def get_comment_positioning(self, obj):
        comment = obj.comments.filter(subject=_("Positioning comment")).order_by("-created_at").first()
        if comment:
            return PositioningCommentSerializer(comment).data
        return None

    @extend_schema_field(
        inline_serializer(
            "NestedAnomaliesSerializer",
            fields={
                "fixed": serializers.IntegerField(help_text=_("Number of fixed anomalies")),
                "unfixed": serializers.IntegerField(help_text=_("Number of unfixed anomalies")),
            },
        )
    )
    def get_anomalies(self, obj) -> dict[str, int]:
        return {
            "fixed": obj.fixed_anomalies,
            "unfixed": obj.unfixed_anomalies,
        }


class FinishInstructionTurnSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = [
            "id",
        ]

    def save(self):
        collection = self.instance
        resource = collection.resource
        library_id = collection.library_id

        if resource.status == ResourceStatus.INSTRUCTION_BOUND:
            cycle = "bound_copies"
        elif resource.status == ResourceStatus.INSTRUCTION_UNBOUND:
            cycle = "unbound_copies"
        else:
            raise serializers.ValidationError(_("Resource is not in an instruction phase"))

        turns = resource.instruction_turns.get(cycle, [])
        try:
            turn = turns["turns"].pop(0)
        except (IndexError, AttributeError):
            set_tag("project", str(resource.project.id))
            set_tag("collection", str(collection.id))
            set_tag("resource", str(resource.id))
            logger.error("No more turns left but finish_instruction_turn was called")
            turn = None

        if not isinstance(turn, dict):
            set_tag("project", str(resource.project.id))
            set_tag("collection", str(collection.id))
            set_tag("resource", str(resource.id))
            logger.error("Instruction turn should be a dict, got: %s", type(turn))
            raise serializers.ValidationError(_("Invalid turn data"))

        if str(turn.get("library", "")) != str(library_id) or turn["collection"] != str(collection.id):
            raise PermissionDenied()

        # All seems OK
        if len(turns["turns"]):
            # There is a next turn
            resource.instruction_turns[cycle] = turns.copy()
            resource.save(update_fields=["instruction_turns"])

            next_library_id = turns["turns"][0]["library"]
            next_library = Library.objects.get(pk=next_library_id)
            notify_instructors_of_instruction_turn(resource, next_library, self.context["request"])

        else:
            # No next turn, move to control
            resource.status = (
                ResourceStatus.CONTROL_BOUND if cycle == "bound_copies" else ResourceStatus.CONTROL_UNBOUND
            )
            resource.instruction_turns[cycle]["turns"] = []
            resource.save(update_fields=["instruction_turns", "status"])
            notify_controllers_of_control(resource, self.context["request"], cycle)
            ActionLog.log(
                f"Resource status moved to {ResourceStatus(resource.status).name}",
                actor=self.context["request"].user,
                obj=resource,
                request=self.context["request"],
            )

        return collection
