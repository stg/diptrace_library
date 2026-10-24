from __future__ import annotations

"""Declarative semantic atlas over structural opcode nodes.

Descriptors are written as linear field layouts over layer3 structural atoms.
Branches that are evidenced in the structural atom stream are modeled as
separate linear descriptors under the same semantic type.
"""

from .model import (
    angle_deg,
    blob,
    bool_run,
    coord_bias1e4,
    empty_text,
    OpcodeSemanticContext,
    OpcodeSemanticDescriptor,
    OpcodeSemanticField,
    OpcodeSemanticRule,
    field,
    tok42_int,
    text,
)


PART_SIGNATURE = "01 00 0f 42 40 0f 42"


def descriptor(
    descriptor_id: str,
    semantic_type: str,
    *,
    signature_hex: str,
    opaque: bool = False,
    fields: tuple[OpcodeSemanticField, ...],
) -> OpcodeSemanticDescriptor:
    return OpcodeSemanticDescriptor(
        descriptor_id=descriptor_id,
        semantic_type=semantic_type,
        signature_hex=signature_hex,
        fields=fields,
        opaque=bool(opaque),
    )


PART_NORMAL_DESCRIPTOR = descriptor(
    "OpcodeSemantic.Part.normal.v1",
    "Part",
    signature_hex=PART_SIGNATURE,
    fields=(
        blob("unknown0"),
        blob("unknown1"),
        tok42_int("Type"),
        blob("unknown3"),
        blob("unknown4"),
        tok42_int("Page"),
        tok42_int("Orientation"),
        tok42_int("Group"),
        tok42_int("Number"),
        coord_bias1e4("X"),
        coord_bias1e4("Y"),
        coord_bias1e4("Width"),
        coord_bias1e4("Height"),
        text("Name", nullable=True),
        text("RefDes"),
        text("Value", nullable=True),
        text("BaseRefDes"),
        text("BaseName"),
        blob("unknown18"),
        blob("unknown19"),
        blob("unknown20"),
        blob("unknown21"),
        tok42_int("PartType"),
        text("PartName"),
        text("PartDescriptor"),
        bool_run("AllowParts"),
        tok42_int("ShowText2"),
        tok42_int("TextAlign2"),
        tok42_int("ShowNumbers"),
        coord_bias1e4("TextPosX"),
        coord_bias1e4("TextPosY"),
        coord_bias1e4("TextPosX2"),
        coord_bias1e4("TextPosY2"),
        empty_text("PartString"),
        tok42_int("HiddenId"),
        blob("unknown35"),
        tok42_int("FieldIndex1"),
        tok42_int("FieldIndex2"),
        bool_run("Locked"),
        angle_deg("Angle"),
        text("LibPath"),
    ),
)


PART_NETPORT_DESCRIPTOR = descriptor(
    "OpcodeSemantic.Part.netport.v1",
    "Part",
    signature_hex=PART_SIGNATURE,
    fields=(
        blob("unknown0"),
        blob("unknown1"),
        tok42_int("Type"),
        blob("unknown3"),
        blob("unknown4"),
        tok42_int("Page"),
        tok42_int("Orientation"),
        tok42_int("Group"),
        tok42_int("Number"),
        coord_bias1e4("X"),
        coord_bias1e4("Y"),
        coord_bias1e4("Width"),
        coord_bias1e4("Height"),
        text("Name", nullable=True),
        text("RefDes"),
        text("Value", nullable=True),
        text("BaseName"),
        blob("unknown17"),
        blob("unknown18"),
        blob("unknown19"),
        blob("unknown20"),
        tok42_int("PartType"),
        text("PartName"),
        text("PartDescriptor"),
        bool_run("AllowParts"),
        tok42_int("ShowText2"),
        tok42_int("TextAlign2"),
        tok42_int("ShowNumbers"),
        coord_bias1e4("TextPosX"),
        coord_bias1e4("TextPosY"),
        coord_bias1e4("TextPosX2"),
        coord_bias1e4("TextPosY2"),
        empty_text("PartString"),
        tok42_int("HiddenId"),
        blob("unknown34"),
        tok42_int("FieldIndex1"),
        tok42_int("FieldIndex2"),
        bool_run("Locked"),
        angle_deg("Angle"),
        text("LibPath"),
    ),
)


def _has_netport_branch(ctx: OpcodeSemanticContext) -> bool:
    slices = ctx.node.token_slices
    if len(slices) <= 39:
        return False
    return (
        str(ctx.node.record.signature_hex) == PART_SIGNATURE
        and slices[15].kind == "ZRUN"
        and slices[16].text is not None
        and slices[17].kind == "OP0F"
        and slices[22].text is not None
        and slices[23].text is not None
        and slices[39].text is not None
    )


SEMANTIC_RULES: tuple[OpcodeSemanticRule, ...] = (
    OpcodeSemanticRule(
        descriptor=PART_NETPORT_DESCRIPTOR,
        match=_has_netport_branch,
    ),
    OpcodeSemanticRule(
        descriptor=PART_NORMAL_DESCRIPTOR,
        match=lambda ctx: str(ctx.node.record.signature_hex) == PART_SIGNATURE,
    ),
)


def resolve_semantic_descriptor(ctx: OpcodeSemanticContext) -> OpcodeSemanticDescriptor:
    for rule in SEMANTIC_RULES:
        if rule.match(ctx):
            return rule.descriptor
    signature_hex = str(ctx.node.record.signature_hex)
    field_count = len(ctx.node.token_slices)
    fallback_fields = tuple(blob(f"unknown{i}") for i in range(field_count))
    return OpcodeSemanticDescriptor(
        descriptor_id=f"OpcodeSemantic.Opaque.{signature_hex.replace(' ', '_')}.v1",
        semantic_type=f"Opaque[{signature_hex}]",
        signature_hex=signature_hex,
        fields=fallback_fields,
        opaque=True,
    )
