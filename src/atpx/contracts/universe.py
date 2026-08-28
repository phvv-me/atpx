from patos import FrozenModel
from pydantic import ConfigDict


class Universe(FrozenModel):
    """Where a workspace's trials live, declared once for whatever executes them.

    A DATA CONTRACT, not an executor. atpx declares `[universe]` because the workspace
    manifest is where a project says what shape it is, and a hermetic trial executor
    reads the same table to find the nodes, the per-node evidence path, the coverage
    coordinates and the distributions whose version every receipt records. atpx never
    runs a trial and the executor never imports atpx: the table is the joint, so a new
    executor is a new reader of a declaration that already exists rather than an edit
    here.

    root: the directory holding the nodes, one directory per claim, a lane's own file
        living under one of them. A flat universe names the root itself and is the same
        rule with one store, so neither layout is a special case downstream.
    evidence: the per-node path the receipt partitions sit under.
    axes: the coverage coordinates, each one a receipt column asked of every lane. An
        axis is resolved from a trial's own parameters when it names one and from the
        run's probed provenance otherwise, so `model` comes off a parametrize grid and
        `card` off the machine without either being special-cased.
    probed: the distributions whose version every receipt records.
    samples: how many passing receipts one cell owes before a lane is complete there.
        One suits a claim that is either true or false on this machine; a program whose
        subject is variance declares several and a re-run accumulates toward the target
        instead of replaying it.
    """

    model_config = ConfigDict(extra="forbid")

    root: str
    evidence: str = "evidence/receipts"
    axes: list[str] = []
    probed: list[str] = []
    samples: int = 1
