from datetime import timedelta
from os import environ
from pathlib import Path

from .base import *

#######################
# Debug configuration #
#######################

DEBUG = True


##########################
# Database configuration #
##########################

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": environ.get("DEFAULT_DB_TEST_NAME", "epl"),
        "USER": environ.get("DEFAULT_DB_TEST_USER", "epl"),
        "PASSWORD": environ.get("DEFAULT_DB_TEST_PASSWORD", "epl"),
        "HOST": environ.get("DEFAULT_DB_TEST_HOST", "localhost"),
        "PORT": environ.get("DEFAULT_DB_TEST_PORT", ""),
    }
}

############################
# Allowed hosts & Security #
############################

ALLOWED_HOSTS = ["*"]

#####################
# Log configuration #
#####################

LOGGING["handlers"]["file"]["filename"] = environ.get(
    "LOG_DIR",
    Path("/tmp").resolve(strict=True) / f"test_{SITE_NAME}.log",
)
LOGGING["handlers"]["file"]["level"] = "DEBUG"

for logger in LOGGING["loggers"]:
    LOGGING["loggers"][logger]["level"] = "DEBUG"

TEST_RUNNER = "django.test.runner.DiscoverRunner"

SIMPLE_JWT.update(
    {
        "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
        "ALGORITHM": "HS256",
        "SIGNING_KEY": SECRET_KEY,
        "VERIFYING_KEY": SECRET_KEY,
    }
)


REST_FRAMEWORK.update(
    {
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ],
    }
)


#########################
# General configuration #
#########################

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-US"
