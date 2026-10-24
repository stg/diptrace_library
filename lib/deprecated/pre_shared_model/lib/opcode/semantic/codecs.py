from __future__ import annotations

"""Generic semantic codecs over structural token slices.

The semantic layer decodes sequentially over layer3 token slices:
- each field consumes zero or one structural atoms
- text fields accept null markers where the format uses them
- blob fields stay visible to end-apps by the same property model
"""

from dataclasses import replace
import math

from lib.deprecated.pre_shared_model.lib.opcode.layer2 import OpcodeTokenSlice
from lib.deprecated.pre_shared_model.lib.opcode.layer3 import OpcodeLayer3Node
from lib.deprecated.pre_shared_model.lib.opcode.layer1 import OpcodeToken, encode_opcode_token
from .model import OpcodeSemanticDescriptor, OpcodeSemanticField, OpcodeSemanticTree


_TEXT_TOKEN_KINDS = frozenset({"STR16BE_LEN16", "STR16LE_LEN16", "STR16LE_LEN16_TAIL8", "STR16LE_RAW"})
_NULL_TOKEN_KINDS = frozenset({"ZRUN"})


def _decode_atom(token_slice: OpcodeTokenSlice, field: OpcodeSemanticField):
    if token_slice.text is not None:
        return str(token_slice.text)
    if token_slice.value is not None:
        return int(token_slice.value)
    return field.default


def _is_null_marker(token_slice: OpcodeTokenSlice) -> bool:
    return str(token_slice.kind) in _NULL_TOKEN_KINDS and int(token_slice.value or 0) == 0


def _decode_text_field(field: OpcodeSemanticField, token_slice: OpcodeTokenSlice | None) -> tuple[object, int]:
    if token_slice is None:
        return field.default, 0
    if token_slice.text is not None:
        return str(token_slice.text), 1
    if field.nullable and _is_null_marker(token_slice):
        return None, 1
    return field.default, 0


def _decode_int_field(field: OpcodeSemanticField, token_slice: OpcodeTokenSlice | None) -> tuple[object, int]:
    if token_slice is None:
        return field.default, 0
    if token_slice.value is not None:
        return int(token_slice.value), 1
    if field.nullable and _is_null_marker(token_slice):
        return None, 1
    return field.default, 0


def _decode_blob_field(field: OpcodeSemanticField, token_slice: OpcodeTokenSlice | None) -> tuple[object, int]:
    if token_slice is None:
        return field.default, 0
    return _decode_atom(token_slice, field), 1


def _decode_empty_text_field(field: OpcodeSemanticField, token_slice: OpcodeTokenSlice | None) -> tuple[object, int]:
    if token_slice is None:
        return field.default, 0
    if token_slice.text is not None:
        return str(token_slice.text), 1
    if _is_null_marker(token_slice):
        return "", 1
    return field.default, 0


def _decode_tok42_int_field(field: OpcodeSemanticField, token_slice: OpcodeTokenSlice | None) -> tuple[object, int]:
    if token_slice is None:
        return field.default, 0
    if str(token_slice.kind) != "OP0F" or token_slice.value is None:
        return field.default, 0
    return int(token_slice.value) - 16960, 1


def _decode_bool_run_field(field: OpcodeSemanticField, token_slice: OpcodeTokenSlice | None) -> tuple[object, int]:
    if token_slice is None:
        return field.default, 0
    if str(token_slice.kind) == "ZRUN" and int(token_slice.value or 0) == 0 and int(token_slice.end - token_slice.start) == 1:
        return False, 1
    if str(token_slice.kind) == "ORUN" and int(token_slice.value or 0) == 1 and int(token_slice.end - token_slice.start) == 1:
        return True, 1
    return field.default, 0


def _decode_angle_deg_field(field: OpcodeSemanticField, token_slice: OpcodeTokenSlice | None) -> tuple[object, int]:
    if token_slice is None:
        return field.default, 0
    if str(token_slice.kind) != "OP3B24" or token_slice.value is None:
        return field.default, 0
    radians = (int(token_slice.value) - 0x9ACA00) / 10000.0
    degrees = round(radians * 180.0 / math.pi, 4)
    return degrees, 1


def _decode_coord_bias1e4_field(field: OpcodeSemanticField, token_slice: OpcodeTokenSlice | None) -> tuple[object, int]:
    if token_slice is None:
        return field.default, 0
    if str(token_slice.kind) != "OP3B24" or token_slice.value is None:
        return field.default, 0
    value = round((int(token_slice.value) - 0x9ACA00) / 10000.0, 4)
    return value, 1


def decode_descriptor_fields(
    node: OpcodeLayer3Node,
    descriptor: OpcodeSemanticDescriptor,
) -> tuple[dict[str, object], dict[str, int | None]]:
    props: dict[str, object] = {}
    field_atoms: dict[str, int | None] = {}
    cursor = 0
    total = len(node.token_slices)
    for field in descriptor.fields:
        token_slice = node.token_slices[cursor] if cursor < total else None
        if field.codec == "text":
            value, consumed = _decode_text_field(field, token_slice)
        elif field.codec == "empty_text":
            value, consumed = _decode_empty_text_field(field, token_slice)
        elif field.codec == "tok42_int":
            value, consumed = _decode_tok42_int_field(field, token_slice)
        elif field.codec == "bool_run":
            value, consumed = _decode_bool_run_field(field, token_slice)
        elif field.codec == "angle_deg":
            value, consumed = _decode_angle_deg_field(field, token_slice)
        elif field.codec == "coord_bias1e4":
            value, consumed = _decode_coord_bias1e4_field(field, token_slice)
        elif field.codec == "int":
            value, consumed = _decode_int_field(field, token_slice)
        elif field.codec == "blob":
            value, consumed = _decode_blob_field(field, token_slice)
        else:
            raise ValueError(f"unsupported semantic codec {field.codec!r}")
        props[field.name] = value
        field_atoms[field.name] = cursor if consumed > 0 and cursor < total else None
        cursor += consumed
    return props, field_atoms


def _encode_text_slot(token: OpcodeToken, token_slice: OpcodeTokenSlice, value: str) -> OpcodeToken:
    if token.kind not in _TEXT_TOKEN_KINDS:
        raise ValueError(f"token kind {token.kind!r} is not a text token")
    raw_len = int(token.end - token.start)
    if int(token_slice.start_trim) != 0 or int(token_slice.end_trim) != raw_len:
        raise ValueError("text slot does not cover the full token")
    updated = replace(token, text=str(value))
    updated_raw_len = len(encode_opcode_token(updated))
    return replace(updated, end=int(updated.start) + updated_raw_len)


def _encode_value_slot(token: OpcodeToken, token_slice: OpcodeTokenSlice, value: int) -> OpcodeToken:
    raw_len = int(token.end - token.start)
    if int(token_slice.start_trim) != 0 or int(token_slice.end_trim) != raw_len:
        raise ValueError("value slot does not cover the full token")
    updated = replace(token, value=int(value))
    updated_raw_len = len(encode_opcode_token(updated))
    return replace(updated, end=int(updated.start) + updated_raw_len)


def apply_semantic_tree_to_tokens(tree: OpcodeSemanticTree, tokens: list[OpcodeToken]) -> list[OpcodeToken]:
    updated = list(tokens)
    for node in tree.iter_nodes():
        for field in node.descriptor.fields:
            atom_index = node.field_atoms.get(field.name)
            if atom_index is None:
                continue
            if atom_index >= len(node.backing_node.token_slices):
                continue
            token_slice = node.backing_node.token_slices[int(atom_index)]
            desired = node.props.get(field.name)
            if desired is None and field.codec != "text":
                continue
            current = _decode_atom(token_slice, field)
            if current == desired:
                continue
            token_index = int(token_slice.token_index)
            if field.codec == "text":
                if desired is None:
                    continue
                if token_slice.text is None:
                    continue
                updated[token_index] = _encode_text_slot(updated[token_index], token_slice, str(desired))
                continue
            if field.codec == "empty_text":
                if desired == "" and _is_null_marker(token_slice):
                    continue
                if desired is None:
                    continue
                if token_slice.text is None:
                    continue
                updated[token_index] = _encode_text_slot(updated[token_index], token_slice, str(desired))
                continue
            if field.codec == "tok42_int":
                if desired is None or token_slice.value is None:
                    continue
                updated[token_index] = _encode_value_slot(updated[token_index], token_slice, int(desired) + 16960)
                continue
            if field.codec == "bool_run":
                continue
            if field.codec == "angle_deg":
                continue
            if field.codec == "coord_bias1e4":
                continue
            if field.codec == "int":
                if desired is None:
                    continue
                if token_slice.value is None:
                    continue
                updated[token_index] = _encode_value_slot(updated[token_index], token_slice, int(desired))
                continue
            if field.codec == "blob":
                continue
            raise ValueError(f"unsupported semantic codec {field.codec!r}")
    return updated
