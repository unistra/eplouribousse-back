from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from rest_framework import serializers

from epl.validators import JSONSchemaValidator


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
