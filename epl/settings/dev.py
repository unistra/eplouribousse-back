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

# In your virtualenv, edit the file $VIRTUAL_ENV/bin/postactivate and set
# properly the environnement variable defined in this file (ie: os.environ[KEY])
# ex: export DEFAULT_DB_NAME='project_name'

# Default values for default database are :
# engine : sqlite3
# name : PROJECT_ROOT_DIR/default.db


DATABASES = {
    "default": {
        "ENGINE": environ.get("DEFAULT_DB_ENGINE", "django_tenants.postgresql_backend"),
        "NAME": environ.get("DEFAULT_DB_NAME", "epl"),
        "USER": environ.get("DEFAULT_DB_USER", "epl"),
        "PASSWORD": environ.get("DEFAULT_DB_PASSWORD", "epl"),
        "HOST": environ.get("DEFAULT_DB_HOST", "localhost"),
        "PORT": environ.get("DEFAULT_DB_PORT", "5432"),
    }
}


############################
# Allowed hosts & Security #
############################

ALLOWED_HOSTS = ["*"]

######################
# CAS authentication #
######################

CAS_SERVER_URL = "https://cas-dev.unistra.fr/cas/"


#####################
# Log configuration #
#####################

LOGGING["handlers"]["file"]["filename"] = environ.get(
    "LOG_DIR",
    Path("/tmp").resolve(strict=True) / f"{SITE_NAME}.log",
)
LOGGING["handlers"]["file"]["level"] = "DEBUG"

for logger in LOGGING["loggers"]:
    LOGGING["loggers"][logger]["level"] = "DEBUG"


###########################
# Unit test configuration #
###########################

INSTALLED_APPS += [
    "coverage",
    "debug_toolbar",
    "django_watchfiles",
]


############
# Dipstrap #
############

DIPSTRAP_VERSION = environ.get("DIPSTRAP_VERSION", "latest")
DIPSTRAP_STATIC_URL += "%s/" % DIPSTRAP_VERSION


#################
# Debug toolbar #
#################

DEBUG_TOOLBAR_PATCH_SETTINGS = False
MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]
INTERNAL_IPS = ["127.0.0.1", "0.0.0.0"]

SIMPLE_JWT.update(
    {
        "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    }
)

SAML_TENANT_CONFIG = {
    "sxb": {
        "entityid": "http://sxb.epl-api.localhost:8000/saml2/metadata/",
        "service": {
            "sp": {
                "default_idp": "",
                "endpoints": {
                    "assertion_consumer_service": [
                        ("http://sxb.epl-api.localhost/saml2/acs/", saml2.BINDING_HTTP_POST),
                    ],
                    "single_logout_service": [
                        ("http://sxb.epl-api.localhost/saml2/ls/", saml2.BINDING_HTTP_REDIRECT),
                        ("http://sxb.epl-api.localhost/saml2/ls/post", saml2.BINDING_HTTP_POST),
                    ],
                },
            },
        },
    },
    "tenant2": {
        "entityid": "http://tenant2.epl-api.localhost:8000/saml2/metadata/",
        "service": {
            "sp": {
                "default_idp": "",
                "endpoints": {
                    "assertion_consumer_service": [
                        ("http://tenant2.epl-api.localhost:8000/saml2/acs/", saml2.BINDING_HTTP_POST),
                    ],
                    "single_logout_service": [
                        ("http://tenant2.epl-api.localhost:8000/saml2/ls/", saml2.BINDING_HTTP_REDIRECT),
                        ("http://tenant2.epl-api.localhost:8000/saml2/ls/post", saml2.BINDING_HTTP_POST),
                    ],
                },
            },
        },
    },
}


##########
# Emails #
##########

EMAIL_HOST = "localhost"
EMAIL_PORT = 1025
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_USE_TLS = False


#########################
# General configuration #
#########################

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-US"
