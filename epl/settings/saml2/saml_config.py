
from os import path

import saml2
import saml2.saml

from epl.settings.base import SITE_ROOT

SAML_CONFIG = {
    "xmlsec_binary": "/usr/bin/xmlsec1",
    # your entity id, usually your subdomain plus the url to the metadata view
    "entityid": "https://{{ ENV }}.eplouribousse.fr/saml2/metadata/",
    "allow_unknown_attributes": True,
    "service": {
        "sp": {
            "name": "Federated Django sample SP",
            "name_id_format": saml2.saml.NAMEID_FORMAT_TRANSIENT,
            "discovery_response": False,
            "endpoints": {
                "assertion_consumer_service": [
                    ("https://{{ SITE_DOMAIN }}/saml2/acs/", saml2.BINDING_HTTP_POST),
                ],
                "single_logout_service": [
                    ("https://{{ SITE_DOMAIN }}/saml2/ls/", saml2.BINDING_HTTP_REDIRECT),
                    ("https://{{ SITE_DOMAIN }}/saml2/ls/post/", saml2.BINDING_HTTP_POST),
                ],
            },
            "signing_algorithm": saml2.xmldsig.SIG_RSA_SHA256,
            "digest_algorithm": saml2.xmldsig.DIGEST_SHA256,
            "force_authn": False,
            "name_id_format_allow_create": False,
            "required_attributes": ["givenName", "sn", "mail", "eduPersonPrincipalName"],
            "optional_attributes": [],
            "want_response_signed": True,
            "authn_requests_signed": True,
            "logout_requests_signed": True,
            "want_assertions_signed": True,
            "only_use_keys_in_metadata": True,
            "allow_unsolicited": False,
            "idp": {},
        },
    },
    "metadata": {
        "remote": [
            {"url": "{{ IDP_METADATA_URL }}"},
        ],
    },
    "key_file": path.join(SITE_ROOT / "keys",  "saml2-private.key"),
    "cert_file": path.join(SITE_ROOT / "keys", "saml2-public.pem"),  # public part
    "encryption_keypairs": [
        {
            "key_file": path.join(SITE_ROOT / "keys", "saml2-private.key"),  # private part
            "cert_file": path.join(SITE_ROOT / "keys", "saml2-public.pem"),  # public part
        }
    ],
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
