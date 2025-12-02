from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from rest_framework import serializers

from epl.validators import IssnValidator, JSONSchemaValidator


class JSONSchemaValidatorTest(TestCase):
    def test_validator_needs_existing_schema(self):
        with self.assertRaises(ImproperlyConfigured):
            JSONSchemaValidator("does_not_exist.json")

    def test_validate_valid_json(self):
        value = {
            "theme": "light",
            "locale": "en",
        }
        validated_value = JSONSchemaValidator("user_settings.schema.json")(value)
        self.assertDictEqual(value, validated_value)

    def test_validate_partial_value(self):
        value = {
            "theme": "light",
        }
        validated_value = JSONSchemaValidator("user_settings.schema.json")(value)
        self.assertDictEqual(value, validated_value)

    def test_validate_invalid_entry(self):
        value = {
            "theme": "light",
            "locale": "invalid",
        }
        with self.assertRaises(serializers.ValidationError):
            JSONSchemaValidator("user_settings.schema.json")(value)

    def test_additional_properties_are_not_allowed(self):
        value = {
            "theme": "light",
            "locale": "en",
            "foo": "bar",
        }
        with self.assertRaises(serializers.ValidationError):
            JSONSchemaValidator("user_settings.schema.json")(value)


class IssnValidatorTest(TestCase):
    def test_validate_valid_issn(self):
        validated_value = IssnValidator()("1050-124X")
        self.assertEqual(validated_value, "1050-124X")

    def test_invalid_issn_raises_validation_error(self):
        with self.assertRaises(serializers.ValidationError):
            IssnValidator()("1234-5678")

    def test_issn_must_be_8_chars(self):
        with self.assertRaises(serializers.ValidationError):
            IssnValidator()("123")

    def test_return_value_is_formated_with_hyphen(self):
        validated_value = IssnValidator()("1050124X")
        self.assertEqual(validated_value, "1050-124X")

    def test_returned_value_is_uppercased(self):
        validated_value = IssnValidator()("1050-124x")
        self.assertEqual(validated_value, "1050-124X")


class JSONSchemaWithRefValidatorTest(TestCase):
    def test_project_settings_schema_with_ref_resolution(self):
        """
        Test that references $ref in project_settings.schema.json work correctly.
        """
        # Data used with $ref resolution in project_settings.schema.json
        project_data = {
            "exclusion_reasons": ["reason1", "reason2"],  # not validated here
            "alerts": {  # validated here
                "positioning": True,
                "arbitration": False,
                "instruction": True,
                "control": True,
                "edition": False,
                "preservation": True,
                "transfer": False,
            },
        }

        validator = JSONSchemaValidator("project_settings.schema.json")

        # Should succeed with $ref resolved (used to fail with "Unresolvable: project_alert_settings.schema.json")
        validated_value = validator(project_data)
        self.assertDictEqual(project_data, validated_value)

    def test_invalid_alert_settings_should_fail(self):
        """
        Tests that validation fails correctly for invalid alert settings
        """
        invalid_data = {
            "exclusion_reasons": ["reason1"],
            "alerts": {
                "positioning": "not_a_boolean",
                "arbitration": False,
                "instruction": True,
                "control": True,
                "edition": False,
                "preservation": True,
                "transfer": False,
            },
        }

        validator = JSONSchemaValidator("project_settings.schema.json")

        with self.assertRaises(serializers.ValidationError) as cm:
            validator(invalid_data)

        error_message = str(cm.exception)
        self.assertIn("not of type 'boolean'", error_message)

    def test_missing_required_alert_field_should_fail(self):
        """
        Test que la validation échoue si un champ requis manque dans alerts
        """
        incomplete_data = {
            "exclusion_reasons": ["reason1"],
            "alerts": {
                "positioning": True,
                "arbitration": False,
                # "instruction" missing
                "control": True,
                "edition": False,
                "preservation": True,
                "transfer": False,
            },
        }

        validator = JSONSchemaValidator("project_settings.schema.json")

        with self.assertRaises(serializers.ValidationError) as cm:
            validator(incomplete_data)

        error_message = str(cm.exception)
        self.assertIn("'instruction' is a required property", error_message)
