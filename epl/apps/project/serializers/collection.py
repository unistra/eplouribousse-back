import csv
import io
import logging
from collections import Counter

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Library, Project
from epl.apps.project.models.collection import Collection
from epl.libs.csv_import import handle_import

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
                delimiter="\t",
            )

        return self.csv_reader

    @transaction.atomic
    def save(self):
        csv_file = self.validated_data["csv_file"]
        csv_reader = self.get_file_reader(csv_file)
        loaded_collections = {}

        user = self.context.get("request").user
        library = self.validated_data.get("library")
        project = self.validated_data.get("project")

        collections, errors = handle_import(csv_reader, library.id, project.id, user.id)

        if errors:
            raise serializers.ValidationError({"csv_file": [{"row": row, "errors": errs} for row, errs in errors]})
        else:
            Collection.objects.bulk_create({Collection(**col.model_dump()) for col in collections})

        for collection in collections:
            loaded_collections[collection.code] = loaded_collections.get(collection.code, 0) + 1

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
