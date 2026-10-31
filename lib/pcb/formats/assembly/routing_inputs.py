"""Temporary trace/net keys used by PCB import relationship assembly."""
from dataclasses import dataclass

from ....common.model import Element


@dataclass(frozen=True)
class TraceInput:
    trace: Element
    previous_number: int
    points: tuple


@dataclass(frozen=True)
class NetInput:
    net: Element
    traces: tuple


@dataclass(frozen=True)
class RoutingInputs:
    nets: tuple[NetInput, ...] = ()
    separate_traces: tuple[TraceInput, ...] = ()
