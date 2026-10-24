from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from lib.deprecated.pre_shared_model.lib.opcode.layer2 import OpcodeLayer2Record, OpcodeTokenSlice, record_token_slices
from lib.deprecated.pre_shared_model.lib.opcode.layer1 import OpcodeToken


def _slug_signature(signature_hex: str) -> str:
    return signature_hex.replace(" ", "_")


@dataclass(frozen=True)
class OpcodeStructureDescriptor:
    descriptor_id: str
    structure_type: str
    signature_hex: str | None = None
    tail_class: str | None = None
    opaque: bool = True


@dataclass(frozen=True)
class OpcodeStructureContext:
    record: OpcodeLayer2Record
    token_slices_value: tuple[OpcodeTokenSlice, ...] | None = None
    tokens: tuple[OpcodeToken, ...] | None = None

    def token_slices(self) -> tuple[OpcodeTokenSlice, ...]:
        if self.token_slices_value is not None:
            return self.token_slices_value
        if self.tokens is None:
            return ()
        return record_token_slices(self.record, list(self.tokens))


@dataclass(frozen=True)
class OpcodeStructureRule:
    descriptor: OpcodeStructureDescriptor
    match: Callable[[OpcodeStructureContext], bool]
    decode_properties: Callable[[OpcodeStructureContext], dict[str, Any]]


def _default_properties(ctx: OpcodeStructureContext) -> dict[str, Any]:
    record = ctx.record
    return {
        "Signature": str(record.signature_hex),
        "PrefixByte": f"{int(record.prefix_byte):02x}",
        "TailClass": str(record.tail_class),
        "RawLength": int(record.raw_length),
        "SemanticLength": int(record.semantic_length),
    }


def _exact_header_descriptor(record: OpcodeLayer2Record) -> OpcodeStructureDescriptor:
    signature_hex = str(record.signature_hex)
    tail_class = str(record.tail_class)
    slug = _slug_signature(signature_hex)
    return OpcodeStructureDescriptor(
        descriptor_id=f"OpcodeStructure.{slug}.v1",
        structure_type=f"OpcodeStructure[{signature_hex}]",
        signature_hex=signature_hex,
        tail_class=tail_class,
        opaque=True,
    )


def _with_role(ctx: OpcodeStructureContext, *, role: str) -> dict[str, Any]:
    props = _default_properties(ctx)
    props["Role"] = role
    return props


def _with_text_atoms(ctx: OpcodeStructureContext) -> dict[str, Any]:
    props = _default_properties(ctx)
    text_atoms: list[str] = []
    text_slots: list[int] = []
    text_kinds: list[str] = []
    for idx, tok in enumerate(ctx.token_slices()):
        if tok.text is None:
            continue
        text_atoms.append(str(tok.text))
        text_slots.append(int(idx))
        text_kinds.append(str(tok.kind))
    props["Texts"] = text_atoms
    props["TextSlots"] = text_slots
    props["TextKinds"] = text_kinds
    return props


def _with_default_and_text_atoms(ctx: OpcodeStructureContext) -> dict[str, Any]:
    return _with_text_atoms(ctx)


def _exact_header_rule(
    *,
    family: str,
    signature_hex: str,
    tail_class: str,
    decode_properties: Callable[[OpcodeStructureContext], dict[str, Any]],
    opaque: bool = True,
) -> OpcodeStructureRule:
    slug = _slug_signature(signature_hex)
    descriptor = OpcodeStructureDescriptor(
        descriptor_id=f"{family}.{slug}.v1",
        structure_type=f"{family}[{signature_hex}]",
        signature_hex=signature_hex,
        tail_class=tail_class,
        opaque=opaque,
    )
    return OpcodeStructureRule(
        descriptor=descriptor,
        match=lambda ctx, _signature=signature_hex: str(ctx.record.signature_hex) == _signature,
        decode_properties=decode_properties,
    )


_ROOTLIKE_TEXT_HEADERS: tuple[str, ...] = (
    "01 00 0f 42 40 0f 42",
    "01 01 0f 42 41 0f 42",
    "01 00 0f 42 42 0f 42",
    "01 00 0f 42 41 0f 42",
    "01 00 0f 42 43 0f 42",
    "01 01 0f 42 40 0f 42",
    "01 01 0f 42 42 0f 42",
)

_ATTACHLIKE_TEXT_HEADERS: tuple[str, ...] = (
    "01 00 0f 42 41 01 0f",
    "01 00 0f 42 42 01 0f",
    "01 00 0f 42 44 01 0f",
    "01 01 0f 42 41 01 0f",
    "01 01 0f 42 42 01 0f",
    "01 00 0f 42 43 01 0f",
    "01 01 0f 42 43 01 0f",
    "01 00 0f 42 48 01 0f",
    "01 00 0f 42 50 01 0f",
    "01 01 0f 42 58 01 0f",
)

_ATTACHLIKE_PLAIN_HEADERS: tuple[str, ...] = (
    "01 00 0f 42 46 00 0f",
)


STRUCTURE_RULES: tuple[OpcodeStructureRule, ...] = (
    *(
        _exact_header_rule(
            family="OpcodeRootLike",
            signature_hex=signature_hex,
            tail_class="root_like",
            decode_properties=_with_text_atoms,
        )
        for signature_hex in _ROOTLIKE_TEXT_HEADERS
    ),
    *(
        _exact_header_rule(
            family="OpcodeAttachLike",
            signature_hex=signature_hex,
            tail_class="attach_like",
            decode_properties=_with_text_atoms,
        )
        for signature_hex in _ATTACHLIKE_TEXT_HEADERS
    ),
    *(
        _exact_header_rule(
            family="OpcodeAttachLike",
            signature_hex=signature_hex,
            tail_class="attach_like",
            decode_properties=_default_properties,
        )
        for signature_hex in _ATTACHLIKE_PLAIN_HEADERS
    ),
    _exact_header_rule(
        family="OpcodeSpecial",
        signature_hex="01 00 0f 42 40 00 01",
        tail_class="special",
        decode_properties=lambda ctx: _with_role(ctx, role="special_anchor"),
    ),
    _exact_header_rule(
        family="OpcodeSpecial",
        signature_hex="01 00 0f 42 4f 00 0f",
        tail_class="attach_like",
        decode_properties=lambda ctx: _with_role(ctx, role="special_link_a"),
    ),
    _exact_header_rule(
        family="OpcodeSpecial",
        signature_hex="01 01 0f 42 45 00 0f",
        tail_class="attach_like",
        decode_properties=lambda ctx: _with_role(ctx, role="special_link_b"),
    ),
)


def resolve_structure_descriptor(ctx: OpcodeStructureContext) -> OpcodeStructureDescriptor:
    for rule in STRUCTURE_RULES:
        if rule.match(ctx):
            return rule.descriptor
    return _exact_header_descriptor(ctx.record)


def decode_layer2_record_to_structure(ctx: OpcodeStructureContext) -> tuple[OpcodeStructureDescriptor, dict[str, Any]]:
    for rule in STRUCTURE_RULES:
        if rule.match(ctx):
            return rule.descriptor, rule.decode_properties(ctx)
    return _exact_header_descriptor(ctx.record), _with_default_and_text_atoms(ctx)
