import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *

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


##############
# Secret key #
##############

SECRET_KEY = "{{ secret_key }}"


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
    environment="preprod",
    integrations=[DjangoIntegration()],
)

##############
# Shibboleth #
##############

SAML_TENANT_CONFIG = {
    "t1": {
        "entityid": "https://eplouribousse-api-pprd.app.unistra.fr",
        "service": {
            "sp": {
                "default_idp": "",
                "endpoints": {
                    "assertion_consumer_service": [
                        ("https://t1-eplouribousse-api-pprd.app.unistra.fr/saml2/acs/", saml2.BINDING_HTTP_POST),
                    ],
                    "single_logout_service": [
                        ("https://t1-eplouribousse-api-pprd.app.unistra.fr/saml2/ls/", saml2.BINDING_HTTP_REDIRECT),
                        ("https://t1-eplouribousse-api-pprd.app.unistra.fr/saml2/ls/post", saml2.BINDING_HTTP_POST),
                    ],
                },
                "idp": {
                    "https://idp-pprd.unistra.fr/idp/shibboleth": {
                        "single_sign_on_service": {
                            saml2.BINDING_HTTP_REDIRECT: "https://idp-pprd.unistra.fr/idp/profile/SAML2/Redirect/SSO",
                        },
                    },
                },
            },
            "metadata": {
                "remote": [
                    {"url": "https://pub.federation.renater.fr/metadata/test/idps.xml"},
                ],
            },
        },
    },
    "t2": {
        "entityid": "https://eplouribousse-api-pprd.app.unistra.fr",
        "service": {
            "sp": {
                "default_idp": "",
                "endpoints": {
                    "assertion_consumer_service": [
                        ("https://t2-eplouribousse-api-pprd.app.unistra.fr/saml2/acs/", saml2.BINDING_HTTP_POST),
                    ],
                    "single_logout_service": [
                        ("https://t2-eplouribousse-api-pprd.app.unistra.fr/saml2/ls/", saml2.BINDING_HTTP_REDIRECT),
                        ("https://t2-eplouribousse-api-pprd.app.unistra.fr/saml2/ls/post", saml2.BINDING_HTTP_POST),
                    ],
                },
                "idp": {
                    "https://idp-pprd.unistra.fr/idp/shibboleth": {
                        "single_sign_on_service": {
                            saml2.BINDING_HTTP_REDIRECT: "https://idp-pprd.unistra.fr/idp/profile/SAML2/Redirect/SSO",
                        },
                    },
                },
            },
        },
        "metadata": {
            "remote": [
                {"url": "https://pub.federation.renater.fr/metadata/test/idps.xml"},
            ],
        },
    },
}

SAML_CONFIG = {
    # full path to the xmlsec1 binary program
    "xmlsec_binary": "/usr/bin/xmlsec1",
    # your entity id, usually your subdomain plus the url to the metadata view
    "entityid": "https://eplouribousse-api-pprd.app.unistra.fr",
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
            # "default_idp": "",
            "endpoints": {
                "assertion_consumer_service": [
                    ("https://t1-eplouribousse-api-pprd.app.unistra.fr/saml2/acs/", saml2.BINDING_HTTP_POST),
                ],
                "single_logout_service": [
                    ("https://t1-eplouribousse-api-pprd.app.unistra.fr/saml2/ls/", saml2.BINDING_HTTP_REDIRECT),
                    ("https://t1-eplouribousse-api-pprd.app.unistra.fr/saml2/ls/post", saml2.BINDING_HTTP_POST),
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
                # "https://idp-dev.unistra.fr/idp/shibboleth": {
                #     "single_sign_on_service": {
                #         saml2.BINDING_HTTP_REDIRECT: "https://idp-dev.unistra.fr/idp/profile/SAML2/Redirect/SSO",
                #     },
                # },
            },
        },
    },
    # Where the remote metadata is stored, local, remote or mdq server.
    # One metadatastore or many ...
    "metadata": {
        "remote": [
            {"url": "https://pub.federation.renater.fr/metadata/test/idps.xml"},
        ],
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
