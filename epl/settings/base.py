from os import path
from pathlib import Path

import saml2.saml

SENTRY_DSN = "https://1ec47dc3f4a500ba87705bb8830b5549@sentry.app.unistra.fr/66"

######################
# Path configuration #
######################

DJANGO_ROOT = Path(__file__).resolve(strict=True).parent.parent
SITE_ROOT = DJANGO_ROOT.parent
SITE_NAME = DJANGO_ROOT.name


#######################
# Debug configuration #
#######################

DEBUG = False
TEMPLATE_DEBUG = DEBUG


##########################
# Manager configurations #
##########################

ADMINS = [
    # ('Your Name', 'your_email@example.com'),
]

MANAGERS = ADMINS


##########################
# Database configuration #
##########################

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": "epl",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "5432",
    }
}

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)


######################
# Site configuration #
######################

# Hosts/domain names that are valid for this site; required if DEBUG is False
# See https://docs.djangoproject.com/en/1.11/ref/settings/#allowed-hosts
ALLOWED_HOSTS = []


#########################
# General configuration #
#########################

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = "Europe/Paris"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "fr-FR"

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.

# If you set this to False, Django will not use timezone-aware datetime.
USE_TZ = True

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


#######################
# locale configuration #
#######################

LOCALE_PATHS = [DJANGO_ROOT / "locale"]


#######################
# Media configuration #
#######################

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = DJANGO_ROOT / "media"

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = "/media/"


##############################
# Static files configuration #
##############################

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = SITE_ROOT / "assets"

# URL prefix for static files.
# Example: "http://example.com/static/", "http://static.example.com/"
STATIC_URL = "/site_media/"

# Additional locations of static files
STATICFILES_DIRS = [
    DJANGO_ROOT / "static",
]

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]


############
# Dipstrap #
############

DIPSTRAP_STATIC_URL = "//django-static.u-strasbg.fr/dipstrap/"


##############
# Secret key #
##############

# Make this unique and don't share it with anybody.
# Only for dev and test environments. Should be redefined for
# a production environment
SECRET_KEY = "ma8r116)33!-#pty4!sht8tsa(1bfe%(+!&9xfack+2e9alah!"


##########################
# Template configuration #
##########################

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [DJANGO_ROOT / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
            ],
        },
    },
]


############################
# Middleware configuration #
############################

MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "djangosaml2.middleware.SamlSessionMiddleware",
    "epl.apps.tenant.middleware.CustomSentryTagsMiddleware",
]

########################
# Tenant configuration #
########################

TENANT_MODEL = "tenant.Consortium"
TENANT_DOMAIN_MODEL = "tenant.Domain"


#####################
# Url configuration #
#####################

ROOT_URLCONF = "%s.urls" % SITE_NAME


######################
# WSGI configuration #
######################

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "%s.wsgi.application" % SITE_NAME


#############################
# Application configuration #
#############################

SHARED_APPS = [
    # Shared Django apps
    "django_tenants",
    "epl",
    "epl.apps.tenant",
    "epl.apps.user",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Uncomment the next line to enable the admin:
    "django.contrib.admin",
    # 'django.contrib.admindocs',
    # Shared third party apps
    "django_extensions",
    "rest_framework",
    "django_cas",
    "djangosaml2",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "django_typer",
    # Shared local apps
]

TENANT_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "epl.apps.user",
    "epl.apps.project",
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]


#########################
# Session configuration #
#########################

SESSION_SERIALIZER = "django.contrib.sessions.serializers.JSONSerializer"


#######################
# User authentication #
#######################

AUTH_USER_MODEL = "user.User"

AUTHENTICATION_BACKENDS = (
    "djangosaml2.backends.Saml2Backend",
    "django_cas.backends.CASBackend",
    "django.contrib.auth.backends.ModelBackend",
)

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
    {
        "NAME": "epl.apps.user.validators.ZxcvbnPasswordValidator",
        "OPTIONS": {"min_score": 3},
    },
]

LOGIN_REDIRECT_URL = "login_success"


#####################
# JWT configuration #
#####################


def load_key(keyfile):
    try:
        keyfile = SITE_ROOT / "keys" / keyfile
        with open(keyfile, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return b""


SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "UPDATE_LAST_LOGIN": True,
    "USER_ID_CLAIM": "user_id",
    "SIGNING_KEY": load_key("jwtRS256.key"),
    "VERIFYING_KEY": load_key("jwtRS256.key.pub"),
    "TOKEN_OBTAIN_SERIALIZER": "epl.apps.user.serializers.TokenObtainPairSerializer",
}


######################
# CAS authentication #
######################


def username_format(username):
    return username.strip().lower()


CAS_SERVER_URL = "https://cas.unistra.fr/cas/"
CAS_LOGOUT_COMPLETELY = True
CAS_USERNAME_FORMAT = username_format
CAS_USER_CREATION_CALLBACK = ["epl.libs.cas.create_user"]
CAS_REDIRECT_URL = "/api/user/login-success/"


############################
# Shibboleth configuration #
############################

SAML_SESSION_COOKIE_NAME = "saml_session"
SESSION_COOKIE_SECURE = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SAML_ALLOWED_HOSTS = []
SAML_DEFAULT_BINDING = saml2.BINDING_HTTP_POST
SAML_LOGOUT_REQUEST_PREFERRED_BINDING = saml2.BINDING_HTTP_POST
SAML_IGNORE_LOGOUT_ERRORS = True
SAML2_DISCO_URL = "https://discovery.renater.fr/test"
SAML2_IDPHINT_PARAM = "idphint"

SAML_DJANGO_USER_MAIN_ATTRIBUTE = "username"
SAML_ATTRIBUTE_MAPPING = {
    "eduPersonPrincipalName": ("username",),
    "mail": ("email",),
    "givenName": ("first_name",),
    "sn": ("last_name",),
}

SAML_CONFIG_LOADER = "epl.libs.saml.saml_config_loader"

SAML_CONFIG = {
    # full path to the xmlsec1 binary program
    "xmlsec_binary": "/usr/bin/xmlsec1",
    # your entity id, usually your subdomain plus the url to the metadata view
    "entityid": "http://sxb.epl-api.localhost:8000/saml2/metadata/",
    # directory with attribute mapping
    # "attribute_map_dir": path.join(BASEDIR, "attribute-maps"),
    # Permits having attributes not configured in attribute-mappings
    # otherwise...without OID will be rejected
    "allow_unknown_attributes": True,
    # This block states what services we provide
    "service": {
        # we are just a lonely SP
        "sp": {
            "name": "Federated Django sample SP",
            "name_id_format": saml2.saml.NAMEID_FORMAT_TRANSIENT,
            # For Okta add signed logout requests. Enable this:
            # "logout_requests_signed": True,
            "discovery_response": False,
            "default_idp": "https://idp-dev.unistra.fr/idp/shibboleth",
            "endpoints": {
                # url and binding to the assetion consumer service view
                # do not change the binding or service name
                "assertion_consumer_service": [
                    ("http://sxb.epl-api.localhost:8000/saml2/acs/", saml2.BINDING_HTTP_POST),
                ],
                # url and binding to the single logout service view
                # do not change the binding or service name
                "single_logout_service": [
                    # Disable the next two lines for HTTP_REDIRECT for IDP's that only support HTTP_POST. Ex. Okta:
                    ("http://sxb.epl-api.localhost:8000/saml2/ls/", saml2.BINDING_HTTP_REDIRECT),
                    ("http://sxb.epl-api.localhost:8000/saml2/ls/post", saml2.BINDING_HTTP_POST),
                ],
            },
            "signing_algorithm": saml2.xmldsig.SIG_RSA_SHA256,
            "digest_algorithm": saml2.xmldsig.DIGEST_SHA256,
            # Mandates that the identity provider MUST authenticate the
            # presenter directly rather than rely on a previous security context.
            "force_authn": False,
            # Enable AllowCreate in NameIDPolicy.
            "name_id_format_allow_create": False,
            # attributes that this project need to identify a user
            "required_attributes": ["givenName", "sn", "mail", "eduPersonPrincipalName"],
            # attributes that may be useful to have but not required
            # "optional_attributes": ["eduPersonAffiliation"],
            "optional_attributes": [],
            "want_response_signed": True,
            "authn_requests_signed": True,
            "logout_requests_signed": True,
            # Indicates that Authentication Responses to this SP must
            # be signed. If set to True, the SP will not consume
            # any SAML Responses that are not signed.
            "want_assertions_signed": True,
            "only_use_keys_in_metadata": True,
            # When set to true, the SP will consume unsolicited SAML
            # Responses, i.e. SAML Responses for which it has not sent
            # a respective SAML Authentication Request.
            "allow_unsolicited": False,
            # in this section the list of IdPs we talk to are defined
            # This is not mandatory! All the IdP available in the metadata will be considered instead.
            "idp": {
                # we do not need a WAYF service since there is
                # only an IdP defined here. This IdP should be
                # present in our metadata
                # the keys of this dictionary are entity ids
                "https://idp-dev.unistra.fr/idp/shibboleth": {
                    "single_sign_on_service": {
                        saml2.BINDING_HTTP_REDIRECT: "https://idp-dev.unistra.fr/idp/profile/SAML2/Redirect/SSO",
                    },
                },
            },
        },
    },
    # Where the remote metadata is stored, local, remote or mdq server.
    # One metadatastore or many ...
    "metadata": {
        # "remote": [
        #     {"url": "https://idp-dev.unistra.fr/idp/shibboleth"},
        # ],
    },
    # set to 1 to output debugging information
    "debug": 1,
    # Signing
    "key_file": path.join(SITE_ROOT / "keys", "saml2-private.key"),  # private part
    "cert_file": path.join(SITE_ROOT / "keys", "saml2-public.pem"),  # public part
    # Encryption
    "encryption_keypairs": [
        {
            "key_file": path.join(SITE_ROOT / "keys", "saml2-private.key"),  # private part
            "cert_file": path.join(SITE_ROOT / "keys", "saml2-public.pem"),  # public part
        }
    ],
    # own metadata settings
    "contact_person": [
        {
            "given_name": "DIP",
            "sur_name": "DIP",
            "company": "Université de Strasbourg",
            "email_address": "dnum-dip@unistra.fr",
            "contact_type": "technical",
        },
        {
            "given_name": "Sacre",
            "sur_name": "Sacre",
            "company": "Université de Strasbourg",
            "email_address": "dnum-sacre@unistra.fr",
            "contact_type": "administrative",
        },
    ],
    # you can set multilanguage information here
    "organization": {
        "name": [("Université de Strasbourg", "fr"), ("University of Strasbourg", "en")],
        "display_name": [
            ("Unistra", "fr"),
            ("Unistra", "en"),
        ],
        "url": [("https://www.unistra.fr", "fr"), ("https://www.unistra.fr", "en")],
    },
}


#####################
# Log configuration #
#####################

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(levelname)s %(asctime)s %(name)s:%(lineno)s %(message)s"},
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[%(server_time)s] %(message)s",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
        },
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "",
            "maxBytes": 209715200,
            "backupCount": 3,
            "formatter": "default",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "mail_admins"],
            "level": "INFO",
        },
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
            "propagate": False,
        },
        "epl": {"handlers": ["mail_admins", "file"], "level": "ERROR", "propagate": True},
    },
}

##################
# REST Framework #
##################

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "djangorestframework_camel_case.render.CamelCaseJSONRenderer",
        "djangorestframework_camel_case.render.CamelCaseBrowsableAPIRenderer",
    ],
    "JSON_UNDERSCOREIZE": {
        "no_underscore_before_number": True,
    },
    "DEFAULT_PARSER_CLASSES": [
        "djangorestframework_camel_case.parser.CamelCaseFormParser",
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
        "djangorestframework_camel_case.parser.CamelCaseMultiPartParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "epl.apps.user.authentication.JWTAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "epl.libs.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Eplouribousse API",
    "DESCRIPTION": "API documentation for the Eplouribousse project",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}


########
# CORS #
########

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_HEADERS = (
    "x-requested-with",
    "content-type",
    "accept",
    "origin",
    "authorization",
    "x-csrftoken",
    "range",
)

#########
# EMAILS #
#########

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
DEFAULT_FROM_EMAIL = "ne-pas-repondre@unistra.fr"
CONTACT_EMAIL = "support-eplouribousse@unistra.fr"
EMAIL_SUPPORT = CONTACT_EMAIL

#########
# Cache #
#########
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = "10"
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "epl",
    },
}

CACHE_TIMEOUT_DASHBOARD = 0 # todo: restore dashboard caching
