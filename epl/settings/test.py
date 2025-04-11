from .base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

#######################
# Debug configuration #
#######################

DEBUG = True


##########################
# Database configuration #
##########################

DATABASES["default"]["HOST"] = "{{ default_db_host }}"
DATABASES["default"]["USER"] = "{{ default_db_user }}"
DATABASES["default"]["PASSWORD"] = "{{ default_db_password }}"
DATABASES["default"]["NAME"] = "{{ default_db_name }}"


############################
# Allowed hosts & Security #
############################

ALLOWED_HOSTS = [
    ".u-strasbg.fr",
    ".unistra.fr",
]


#####################
# Log configuration #
#####################

LOGGING["handlers"]["file"]["filename"] = "{{ remote_current_path }}/log/app.log"

for logger in LOGGING["loggers"]:
    LOGGING["loggers"][logger]["level"] = "DEBUG"


############
# Dipstrap #
############

DIPSTRAP_VERSION = "{{ dipstrap_version }}"
DIPSTRAP_STATIC_URL += "%s/" % DIPSTRAP_VERSION

sentry_sdk.init(
    dsn=SENTRY_DSN,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    environment="test",
    integrations=[DjangoIntegration()],
)
