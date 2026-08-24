from ...graph.node import Node
from .workbench import Workbench


class Arena:
    """Everything a bout fights over, fixed for the whole ladder rather than per rung.

    A ladder fights the same node in the same workspace under the same summons,
    so a rung varies only in which lane swings. Holding the four together keeps
    a `Bout` carrying its configuration and its subject as two ideas instead of
    seven loose fields, and keeps `fought` from stashing state mid-flight.

    A plain class rather than a frozen model because `space` is a bare
    `Protocol`: pydantic builds an `is-instance` validator for a field whose
    type it cannot otherwise check, and that validator refuses a Protocol that
    is not `runtime_checkable`, so every model foundation fails to build here.
    """

    def __init__(self, space: Workbench, node: Node, *, summons: str, lessons: str) -> None:
        """space: the workspace the probes run in.

        node: the node under attack.
        summons: the assembled hostile system message every attacker opens with.
        lessons: the tactics text folded into the defense summons.
        """
        self.space = space
        self.node = node
        self.summons = summons
        self.lessons = lessons
