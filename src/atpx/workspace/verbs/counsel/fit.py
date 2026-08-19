from collections.abc import Sequence

from ....core.certificate import Certificate
from ....core.evidence import EvidenceStore
from ....discovery.fitting import Discovery
from ...foundation import DataPath
from ...state import FoundationState


class FitVerbs(FoundationState):
    """The fit lane: PySR over a data artifact, certifying the Pareto front."""

    def fit(
        self,
        data: DataPath,
        target: str,
        slug: str | None = None,
        *,
        seed: int = 0,
        niterations: int = 40,
        unary: Sequence[str] | None = None,
        binary: Sequence[str] | None = None,
        tail: float | None = None,
        driver: str | None = None,
        features: Sequence[str] | None = None,
    ) -> Certificate:
        """The fit lane: PySR over a data artifact, certifying the Pareto front.

        Operator menus take repeated flags or comma-joined tokens, so
        `--binary "+,-,*"` sidesteps flag parsing of a bare `-`. The data path
        resolves cwd-first and then root-relative. Records honest
        unavailability when pysr is not installed.

        data: path to a CSV whose named column is the target.
        target: the column to fit.
        slug: blueprint to persist into, defaulting to an unpersisted certificate.
        seed: random_state for the certifying run.
        niterations: search budget.
        unary: unary operator menu, PySR's `unary_operators`, defaults hold when omitted.
        binary: binary operator menu, PySR's `binary_operators`, defaults hold when omitted.
        tail: hold out this fraction of the rows with the largest driver values
            instead of a random 20%.
        driver: the column ranking the tail holdout, defaulting to the first
            feature column.
        features: restrict the fit to these columns, defaulting to every
            non-target column.
        """
        certificate = Discovery(self.root).fit(
            data,
            target=target,
            seed=seed,
            niterations=niterations,
            unary=unary,
            binary=binary,
            tail=tail,
            driver=driver,
            features=features,
        )
        if slug and certificate.ok:
            store = EvidenceStore(self.register(slug, claim="fit").directory)
            store.append(certificate)
        return certificate
