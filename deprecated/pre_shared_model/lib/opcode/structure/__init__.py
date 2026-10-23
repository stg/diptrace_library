from __future__ import annotations

from .registry import (
    OpcodeStructureContext,
    OpcodeStructureDescriptor,
    decode_layer2_record_to_structure,
    resolve_structure_descriptor,
)

__all__ = [
    "OpcodeStructureContext",
    "OpcodeStructureDescriptor",
    "decode_layer2_record_to_structure",
    "resolve_structure_descriptor",
]
