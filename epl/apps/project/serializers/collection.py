import csv
import io
from collections import Counter

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Library, Project
from epl.apps.project.models.collection import Collection

FIELD_MAPPING = {
    "Titre": "title",
    "PPN": "code",
    "Issn": "issn",
    "Cote": "call_number",
    "Etat de collection": "hold_statement",
    "Lacunes": "missing",
}

REQUIRED_FIELDS = (
    "title",
    "code",
)

FIELD_CLEANERS = {
    "title": lambda x: x.strip(),
    "code": lambda x: x.strip(),
    "issn": lambda x: x.replace(" ", "").upper(),
    "call_number": lambda x: x.strip(),
    "hold_statement": lambda x: x.strip(),
    "missing": lambda x: x.strip(),
}


class CollectionSerializer:
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
    csv_file = serializers.FileField(required=True, help_text=_("CSV file to be imported."))
    library_id = serializers.UUIDField(required=True, help_text=_("Library ID to which the collection belongs."))
    project_id = serializers.UUIDField(required=True, help_text=_("Project ID to which the collection belongs."))

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

        missing_required_fields = []
        loaded_collections = {}
        current_row = 0
        for row in csv_reader:
            current_row += 1
            # map the fields to the model fields
            data = {FIELD_MAPPING.get(key): value for key, value in row.items() if key in FIELD_MAPPING}
            for name, cleaner in FIELD_CLEANERS.items():
                data[name] = cleaner(data[name])
            data["library"] = self.validated_data["library_id"]
            data["project"] = self.validated_data["project_id"]

            try:
                Collection.objects.create(**data)
                loaded_collections[data["code"]] = loaded_collections.get(data["code"], 0) + 1
            except ModelValidationError:
                missing_required_fields.append((current_row, [field for field in REQUIRED_FIELDS if not data[field]]))

        if missing_required_fields:
            raise serializers.ValidationError({"csv_file": _("Missing required fields in the CSV file.")})

        return Counter(loaded_collections.values())

    def validate_csv_file(self, value):
        csv_reader = self.get_file_reader(value)
        if missing_field := [field for field in REQUIRED_FIELDS if field not in csv_reader.fieldnames]:
            raise serializers.ValidationError(
                _("Column(s) %(column)s missing in the CSV file.") % {"column": ", ".join(missing_field)}
            )

        return value

    def validate_library_id(self, value):
        try:
            library = Library.objects.get(pk=value)
        except Library.DoesNotExist:
            raise serializers.ValidationError(_("Library with ID %(id)s does not exist.") % {"id": value})
        return library.id

    def validate_project_id(self, value):
        try:
            project = Project.objects.get(pk=value)
        except Project.DoesNotExist:
            raise serializers.ValidationError(_("Project with ID %(id)s does not exist.") % {"id": value})
        return project.id
