from __future__ import annotations

"""Public opcode API for the clean layer pipeline.

The package-level API is intentionally thin. Core logic lives in the layers:
- layer1: bytes <-> tokens
- layer2: tokens <-> structures
- layer3: structures <-> structural tree
- semantic: structural tree <-> semantic tree
"""

from pathlib import Path

from .layer1 import OpcodeToken, read_bytes, read_dch_header, tokenize_opcode_layer
from .layer2 import encode_layer2_stream, preamble_token_slices, record_token_slices
from .layer3 import (
    OpcodeLayer3EmbeddedNode,
    OpcodeLayer3LocalSegment,
    OpcodeLayer3Node,
    OpcodeLayer3RootSection,
    OpcodeLayer3Tree,
    build_layer2_stream_from_layer3,
    build_layer3_tree_from_layer2,
    encode_layer3_tree,
)
from .semantic import OpcodeSemanticNode, OpcodeSemanticTree, build_semantic_tree_from_layer3, decode_opcode_semantic_tree, encode_semantic_tree


def decode_opcode_tokens(path: str | Path) -> tuple[str, int, list[OpcodeToken]]:
    data = read_bytes(path)
    header_end, header_text = read_dch_header(data)
    return header_text, header_end, tokenize_opcode_layer(data)


def build_opcode_layer2_stream(path: str | Path, semantic_starts: list[int]):
    from .layer2 import build_layer2_stream_from_semantic_starts

    header_text, header_end, tokens = decode_opcode_tokens(path)
    stream = build_layer2_stream_from_semantic_starts(
        header_text=header_text,
        header_end=header_end,
        tokens=tokens,
        semantic_starts=semantic_starts,
    )
    return tokens, stream


def decode_opcode_layer2_stream(path: str | Path):
    from .layer2 import build_layer2_stream_from_tokens

    header_text, header_end, tokens = decode_opcode_tokens(path)
    return tokens, build_layer2_stream_from_tokens(header_text=header_text, header_end=header_end, tokens=tokens)


def decode_opcode_layer3_tree(path: str | Path):
    tokens, stream = decode_opcode_layer2_stream(path)
    return tokens, stream, build_layer3_tree_from_layer2(stream, tokens=tokens)


def decode_opcode_structure_tree(path: str | Path):
    return decode_opcode_layer3_tree(path)


__all__ = [
    "build_opcode_layer2_stream",
    "decode_opcode_layer2_stream",
    "decode_opcode_layer3_tree",
    "decode_opcode_structure_tree",
    "decode_opcode_tokens",
    "encode_layer2_stream",
    "record_token_slices",
    "preamble_token_slices",
    "OpcodeLayer3Node",
    "OpcodeLayer3EmbeddedNode",
    "OpcodeLayer3LocalSegment",
    "OpcodeLayer3RootSection",
    "OpcodeLayer3Tree",
    "build_layer2_stream_from_layer3",
    "encode_layer3_tree",
    "OpcodeSemanticNode",
    "OpcodeSemanticTree",
    "build_semantic_tree_from_layer3",
    "decode_opcode_semantic_tree",
    "encode_semantic_tree",
]
