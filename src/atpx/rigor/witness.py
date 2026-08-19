import json

from flint import arb, ctx, fmpq

from ..support.console import announce
from .audits import BallAudit


def is_ball_witness(
    name: str, value: arb, target: arb | fmpq | int, tol: float, prec: int = 128
) -> bool:
    """Decide `|value - target| < tol` over the WHOLE enclosure, print the witness, report it.

    The probe-side half of the ball gate: `value` is an arb enclosure, and the
    check passes only when every point of the ball `mid +/- rad` lies strictly
    inside the tolerance interval around `target`, arb's certified comparison.
    One `ball_certificate` JSON line prints either way, the line the
    `atpx ball` verb audits.

    name: the quantity's label inside the witness line.
    value: the arb enclosure the probe computed.
    target: the exact target, an arb, `fmpq` rational, or integer.
    tol: the tolerance the whole enclosure must sit inside.
    prec: working precision in bits for the comparison, recorded in the line.
    """
    previous = ctx.prec
    ctx.prec = prec
    try:
        verified: bool = abs(value - target) < arb(tol)
    finally:
        ctx.prec = previous
    record = {
        BallAudit.key: {
            "name": name,
            "mid": value.mid().str(32, radius=False),
            "rad": value.rad().str(8, radius=False),
            "target": str(target),
            "tol": tol,
            "prec": prec,
            "verified": verified,
        }
    }
    announce(json.dumps(record))
    return verified
