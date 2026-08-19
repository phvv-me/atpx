from .counsel import (
    FitVerbs,
    LeanVerbs,
    ProveVerbs,
    RecallVerbs,
    RefuteVerbs,
    ScaffoldVerbs,
    SettleVerbs,
)


class CounselVerbs(
    FitVerbs, LeanVerbs, ProveVerbs, RecallVerbs, RefuteVerbs, ScaffoldVerbs, SettleVerbs
):
    """The judgment verbs: scaffold, settle, summon counsel, fit, ingest Lean, recall.

    Each of the seven concerns lives in its own single-verb mixin under
    `counsel/`; this class only combines them, so `fit` and `settle` can
    change independently of each other and of everything else here.
    """
