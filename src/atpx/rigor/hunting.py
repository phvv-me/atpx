from ..core.certificate import Certificate


def hunted(certificate: Certificate) -> str:
    """The one-line reading of a hunt probe's exit, the refuter convention.

    Exit 0 means the property-based search FOUND and shrunk a counterexample,
    printed in the probe output; nonzero means the property survived the
    search budget, which is evidence of absence, never a proof.
    """
    if certificate.ok:
        return (
            f"hunt {certificate.claim}: counterexample FOUND and shrunk, "
            "see the falsifying example in the probe output"
        )
    return (
        f"hunt {certificate.claim}: property survived the search "
        f"(exit {certificate.exit_status}), no counterexample found"
    )
