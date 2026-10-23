from __future__ import annotations

# Compatibility wrapper: layer1 support code now lives under apps/lib/lib_opcode.

from apps.deprecated.pre_shared_model.lib.opcode.layer1 import OpcodeToken as L1Token
from apps.deprecated.pre_shared_model.lib.opcode.layer1 import read_bytes, tokenize_opcode_layer as tokenize_layer1

__all__ = ["L1Token", "read_bytes", "tokenize_layer1"]
