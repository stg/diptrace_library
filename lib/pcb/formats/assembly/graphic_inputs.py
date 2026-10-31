"""Temporary keys accompanying current geometry during import assembly."""
from dataclasses import dataclass

from ....common.model import Element
from .routing_inputs import RoutingInputs


@dataclass(frozen=True)
class DrawingInput:
    drawing: Element
    previous_number: int


@dataclass(frozen=True)
class PourInput:
    pour: Element
    previous_number: int
    regions_counted: bool


@dataclass(frozen=True)
class GraphicInputs(RoutingInputs):
    drawings: tuple[DrawingInput, ...] = ()
    pours: tuple[PourInput, ...] = ()
