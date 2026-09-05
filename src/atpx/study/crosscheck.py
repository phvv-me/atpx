from functools import cached_property

from pydantic import JsonValue

from ..core.certificate import Certificate
from ..core.evidence import EvidenceStore
from ..graph.store import NodeStore


class DeviceComparison:
    """One node family's claim addresses read across every device that ran them.

    A program that measures the same claims on two cards needs one view of where the
    two agree. Every certificate already carries the device it was stamped on, so the
    comparison is a fold over evidence already on disk: nothing is re-run, nothing is
    re-tagged, and a family measured on a second card answers the moment its receipts
    land beside the first card's.

    One row is one claim address, `<node>/<claim>`, and one column is one device. A
    cell holds the newest verdict that device recorded for that address, and a blank
    cell is the reading the whole table exists for: a coordinate the second card still
    owes. Addresses whose devices disagree are named separately and are what makes the
    comparison a gate rather than a report, since one card passing and another failing
    the same address is a portability finding and not a difference of opinion.
    """

    PASSED: str = "passed"
    FAILED: str = "failed"

    def __init__(self, nodes: NodeStore, family: str = "") -> None:
        """nodes: the blueprint node graph whose evidence is folded.

        family: the slug prefix selecting the nodes to compare, every node when empty.
        """
        self.nodes = nodes
        self.family = family

    @property
    def addresses(self) -> list[str]:
        """Every claim address the family has evidence for, sorted."""
        return sorted({address for address, _ in self.newest})

    @property
    def devices(self) -> list[str]:
        """Every device the family was measured on, sorted."""
        return sorted({device for _, device in self.newest})

    @cached_property
    def newest(self) -> dict[tuple[str, str], Certificate]:
        """The newest certificate per address and device, folded over every host's ledger.

        Read per address rather than per host, because the same card reached through
        two hostnames is one device and the question is what the hardware answered.
        """
        found: dict[tuple[str, str], Certificate] = {}
        for node in self.nodes.canonical():
            if not node.primary or not node.name.startswith(self.family):
                continue
            for ledger in EvidenceStore.ledgers(node.directory).values():
                for certificate in ledger:
                    key = (certificate.claim, certificate.device)
                    current = found.get(key)
                    if current is None or current.timestamp < certificate.timestamp:
                        found[key] = certificate
        return found

    def compiled(self) -> dict[str, JsonValue]:
        """The whole comparison: devices, the verdict matrix, disagreements, and gaps."""
        return {
            "family": self.family,
            "devices": list[JsonValue](self.devices),
            "verdicts": {
                address: dict[str, JsonValue](self.__verdicts(address))
                for address in self.addresses
            },
            "disagreements": list[JsonValue](self.disagreements()),
            "gaps": {device: list[JsonValue](self.gaps(device)) for device in self.devices},
            "table": self.table(),
        }

    def disagreements(self) -> list[str]:
        """Addresses two devices answered differently, the finding the table is a gate on."""
        return [
            address
            for address in self.addresses
            if len(set(self.__verdicts(address).values())) > 1
        ]

    def gaps(self, device: str) -> list[str]:
        """Addresses some other device measured and this one never did."""
        return [address for address in self.addresses if device not in self.__verdicts(address)]

    def table(self) -> str:
        """The comparison as one markdown table, one row per address and one column per device."""
        devices = self.devices
        header = ["| Address | " + " | ".join(devices) + " |"]
        header += ["| --- |" + " --- |" * len(devices)]
        rows = [
            f"| {address} | "
            + " | ".join(self.__verdicts(address).get(device, "") for device in devices)
            + " |"
            for address in self.addresses
        ]
        return "\n".join(header + rows)

    def __verdicts(self, address: str) -> dict[str, str]:
        """One address's verdict per device that ran it, devices that never ran it absent."""
        return {
            device: self.PASSED if certificate.ok else self.FAILED
            for (claim, device), certificate in self.newest.items()
            if claim == address
        }
