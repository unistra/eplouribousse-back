import csv
import io
import logging
from collections import Counter

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from epl.apps.project.models import Library, Project
from epl.apps.project.models.collection import Collection

logger = logging.getLogger(__name__)

FIELD_MAPPING = {
    "Titre": "title",
    "PPN": "code",
    "Issn": "issn",
    "Cote": "call_number",
    "Etat de collection": "hold_statement",
    "Lacunes": "missing",
}

REQUIRED_FIELDS = (
    "Titre",
    "PPN",
)


def stripper(val):
    return val.strip() if val and isinstance(val, str) else ""


FIELD_CLEANERS = {
    "title": stripper,
    "code": stripper,
    "issn": lambda x: stripper(x).upper(),
    "call_number": stripper,
    "hold_statement": stripper,
    "missing": stripper,
}


class CollectionSerializer(serializers.ModelSerializer):
    """
    Serializer for the Collection model.
    Used to import .csv files into the database.
    """

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
            self.csv_reader = csv.DictReader(io.StringIO(csv_file.read().decode("utf-8-sig")))

        return self.csv_reader

    @transaction.atomic
    def save(self):
        csv_file = self.validated_data["csv_file"]
        csv_reader = self.get_file_reader(csv_file)

        user = self.context.get("request").user

        # print(f"Importing collections for library: {library.name}, project: {project.name} by user: {user.username}")

        rows_with_errors = []
        loaded_collections = {}
        current_row = 0
        for row in csv_reader:
            current_row += 1
            # map the fields to the model fields
            data = {FIELD_MAPPING.get(key): value for key, value in row.items() if key in FIELD_MAPPING}
            for name, cleaner in FIELD_CLEANERS.items():
                data[name] = cleaner(data[name])
            data["library"] = self.validated_data["library"]
            data["project"] = self.validated_data["project"]
            data["created_by"] = user

            try:
                Collection.objects.create(**data)
                loaded_collections[data["code"]] = loaded_collections.get(data["code"], 0) + 1
            except (ModelValidationError, DRFValidationError):
                logger.error("Error creating collection from row %d: %s", current_row, data, exc_info=True)
                rows_with_errors.append(current_row)

        if rows_with_errors:
            raise serializers.ValidationError(
                {"csv_file": _("Error in rows(s) %(rows)s") % {"rows": ", ".join(str(row) for row in rows_with_errors)}}
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
