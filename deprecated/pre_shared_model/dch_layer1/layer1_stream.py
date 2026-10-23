from __future__ import annotations

"""Legacy framing wrapper for early layer1 stream experiments.

This module is exploratory compatibility only. The live opcode pipeline uses:
- apps.deprecated.pre_shared_model.lib.opcode.layer1
- apps.deprecated.pre_shared_model.lib.opcode.layer2
"""

from apps.deprecated.pre_shared_model.dch_layer1.legacy_stream import OpcodeFrame as Layer1Record
from apps.deprecated.pre_shared_model.dch_layer1.legacy_stream import OpcodeStart as StartCandidate
from apps.deprecated.pre_shared_model.dch_layer1.legacy_stream import build_opcode_frames as build_layer1_records
from apps.deprecated.pre_shared_model.dch_layer1.legacy_stream import classify_start_family, detect_opcode_starts as detect_start_candidates

__all__ = [
    "StartCandidate",
    "Layer1Record",
    "detect_start_candidates",
    "build_layer1_records",
    "classify_start_family",
]
