import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *

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

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTOCOL", "ssl")

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

SENTRY_DSN = "{{ sentry_dsn }}"
sentry_sdk.init(
    dsn=SENTRY_DSN,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    send_default_pii=True,
    environment="test",
    integrations=[DjangoIntegration()],
)


##############
# SECRET_KEY #
##############

SECRET_KEY = "{{ secret_key }}"

######################
# CAS authentication #
######################

CAS_SERVER_URL = "https://cas-dev.unistra.fr/cas/"


#########
# Cache #
#########

REDIS_HOST = "{{ redis_host }}"
REDIS_DB = "{{ redis_db }}"
REDIS_PORT = "{{ redis_port }}"
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
CACHES["default"]["LOCATION"] = REDIS_URL
CACHES["default"]["VERSION"] = "{{ cache_version }}"
RATELIMIT_REDIS = {
    "host": REDIS_HOST,
    "port": REDIS_PORT,
    "db": REDIS_DB,
}
