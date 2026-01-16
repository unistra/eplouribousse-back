import os

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *

##########################
# Database configuration #
##########################

DATABASES["default"]["HOST"] = os.environ.get("DATABASE_HOST", "localhost")
DATABASES["default"]["USER"] = os.environ.get("DATABASE_USER", "epl")
DATABASES["default"]["PASSWORD"] = os.environ.get("DATABASE_PASSWORD", "epl")
DATABASES["default"]["NAME"] = os.environ.get("DATABASE_NAME", "epl")


############################
# Allowed hosts & Security #
############################

ALLOWED_HOSTS = [
    "*",
]
CSRF_TRUSTED_ORIGINS = [
    "https://*.eplouribousse.fr",
]

#######################
# Email configuration #
#######################

EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = os.environ.get("EMAIL_PORT", "25")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "False").lower() == "true"


#####################
# Log configuration #
#####################

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
    },
}

##############
# Secret key #
##############

SECRET_KEY = os.environ.get("SECRET_KEY")

#####################
# JWT configuration #
#####################
SIMPLE_JWT.update(
    {
        "SIGNING_KEY": os.environ.get("JWT_PRIVATE_KEY"),
        "VERIFYING_KEY": os.environ.get("JWT_PUBLIC_KEY"),
    }
)

#########################
# Static files settings #
#########################

DIPSTRAP_VERSION = "latest"
DIPSTRAP_STATIC_URL += "%s/" % DIPSTRAP_VERSION

MIDDLEWARE = list(MIDDLEWARE)
try:
    insert_pos = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
except ValueError:
    insert_pos = 0

MIDDLEWARE.insert(insert_pos, "whitenoise.middleware.WhiteNoiseMiddleware")
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
STATIC_URL = "/assets/"

##########
# Sentry #
##########

if SENTRY_DSN := os.environ.get("SENTRY_DSN"):
    from dotenv import load_dotenv

    load_dotenv(SITE_ROOT / "sentry-release.env")
    sentry_release = os.environ.get("SENTRY_RELEASE_VERSION", None)
    sentry_environment = os.environ.get("SENTRY_ENVIRONMENT", "prod")

    config = {
        "dsn": SENTRY_DSN,
        "environment": sentry_environment,
        "traces_sample_rate": 1.0,
        "send_default_pii": True,
        "integrations": [DjangoIntegration()],
    }
    if sentry_release:
        config["release"] = sentry_release

    sentry_sdk.init(
        **config,
        integrations=[DjangoIntegration()],
    )

#########
# Cache #
#########

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_DB = os.environ.get("REDIS_DB", 0)
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
CACHES["default"]["LOCATION"] = REDIS_URL
CACHES["default"]["VERSION"] = os.environ.get("CACHE_VERSION", "1")

# django-smart-ratelimit uses Redis
RATELIMIT_REDIS = {
    "host": REDIS_HOST,
    "port": REDIS_PORT,
    "db": REDIS_DB,
}
