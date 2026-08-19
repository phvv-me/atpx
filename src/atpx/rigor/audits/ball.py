from .audit import witnesses


class BallAudit:
    """The ball gate: at least one printed ball certificate, every one verified."""

    rigor = "ball"
    key = "ball_certificate"

    def violation(self, output: str) -> str:
        """Why the output does not earn ball rigor, empty when it does."""
        lines = witnesses(output, key=self.key)
        if not lines:
            return "no ball_certificate line printed"
        failed = [str(line.get("name")) for line in lines if line.get("verified") is not True]
        if failed:
            return f"ball certificates not verified: {', '.join(failed)}"
        return ""
