import saml2
import saml2.saml

SAML_CONFIG = {
    "xmlsec_binary": "/usr/bin/xmlsec1",
    # your entity id, usually your subdomain plus the url to the metadata view
    "entityid": "https://eplouribousse-api-pprd.app.unistra.fr",
    "allow_unknown_attributes": True,
    "service": {
        "sp": {
            "name": "Federated Django sample SP",
            "name_id_format": saml2.saml.NAMEID_FORMAT_TRANSIENT,
            "discovery_response": False,
        },
    },
}
