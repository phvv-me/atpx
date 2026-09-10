from collections.abc import Iterable

from .node import Node


class Aliases:
    """The former names a node set still answers to, resolved and screened in one pass.

    Renaming a node breaks every wikilink written before the rename, and the ledger is
    full of links written years apart, so a node keeps its old spellings in the
    frontmatter `aliases` list and the graph resolves them to it. An alias is a pointer
    and never a second claim: it is not a node, it is counted nowhere, and it earns no
    index row.

    A pointer that resolves two ways resolves to nothing here rather than to whichever
    node happened to be read first: an alias a real slug already spells, or one two
    nodes both claim, is dropped from `resolved` and named in `collisions` for `doctor`.
    """

    def __init__(self, nodes: Iterable[Node]) -> None:
        """nodes: the node set whose declared aliases are read, read once."""
        self.nodes = list(nodes)
        self.names = {node.name for node in self.nodes}
        self.claimed: dict[str, list[Node]] = {}
        for node in self.nodes:
            for alias in node.aliases:
                self.claimed.setdefault(alias, []).append(node)

    def collisions(self) -> dict[str, str]:
        """Each alias that resolves ambiguously, mapped to what it collides with."""
        return {
            alias: (
                f"{alias} is already a node of its own"
                if alias in self.names
                else f"{', '.join(sorted(node.name for node in holders))} both declare it"
            )
            for alias, holders in sorted(self.claimed.items())
            if alias in self.names or len(holders) > 1
        }

    def resolved(self) -> dict[str, Node]:
        """Each unambiguous alias mapped to the node it names."""
        return {
            alias: holders[0]
            for alias, holders in self.claimed.items()
            if alias not in self.names and len(holders) == 1
        }
