"""Component facts shared by the BOM and usage database applications."""
from collections.abc import Iterator
from dataclasses import dataclass

from lib import document_family
from lib.common.model import Document

Signature = tuple[str, str, str]


@dataclass(frozen=True)
class Component:
    reference: str
    name: str
    value: str
    pattern: str

    @property
    def signature(self) -> Signature:
        return self.name, self.value, self.pattern


def physical_components(design: Document) -> Iterator[Component]:
    """Read enabled physical parts through the public, named-field model API."""
    if document_family(design) != 'schematic':
        raise ValueError('component listing expects a schematic document')
    for part in design.select("/Schematic/Components/Part"):
        # Ports and other logical symbols do not identify parts to purchase or
        # find in a component usage database.
        if not part["Enabled"] or part["PartType"] != 0:
            continue
        reference = part["RefDes"].strip()
        if not reference:
            continue
        pattern = part.child("Pattern")
        yield Component(
            reference=reference,
            name=part["Name"],
            value=part.get("Value", ""),
            pattern=pattern["Name"] if pattern is not None else "",
        )
