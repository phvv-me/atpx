import json

from atpx import Certificate


def result_of(certificate: Certificate):
    """The certificate result as plain parsed JSON, untyped so asserts can index freely."""
    return json.loads(certificate.model_dump_json())["result"]
