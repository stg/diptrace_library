from __future__ import annotations

"""Strict layer3 opaque tree builder for DipTrace DCH structures.

This module consumes only layer2 records and emits a lossless tree of
structure nodes:
- exact record-backed nodes
- known structure descriptors where evidence is solid
- opaque fallback descriptors everywhere else

It does not assume byte-oriented legacy record layouts or decode
application-specific semantics beyond what the structure layer proves.
"""

# TODO(layer3):
# Outer layer2 record boundaries are now strong, but some families clearly
# contain embedded struct-valued fields inside their token slices. These local
# blocks recur across many outer signatures, so they should be treated as a
# generalized record-local grammar rather than as Part-specific hacks. Keep the
# embedded pass structural: exact local start motifs, conservative end rules,
# and no semantic field naming here.
#
# Current confidence:
# - the embedded grammar is broader than the two extracted text-bearing
#   families below
# - unclaimed ORUN-led motifs recur thousands of times and include non-text
#   fixed-size structs
# - at least one recurring motif is effectively a short wrapper/prefix that is
#   immediately followed by another ORUN start, so a full embedded parser will
#   need family-specific spans and chaining rules rather than a global
#   "consume until next ORUN" rule
# - several high-support families now look like a local protocol:
#   ORUN + OP0F(0x4240+n) local code/flags + fixed-size payload
#   This is a better working model than treating every ORUN as just an
#   undifferentiated separator.
# - the first OP0F after ORUN is exposed as `LocalCode` on embedded nodes and
#   already clusters cleanly by family; future work should use that as a real
#   structural discriminator before adding more semantic naming
# - common transitions now look grammar-like, for example:
#   Block16|0 -> text2|0, text2|1 -> text1|0, text1|0 -> wrapper|2.


from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from lib.deprecated.pre_shared_model.lib.opcode.layer2 import (
    OpcodeLayer2Record,
    OpcodeLayer2Stream,
    OpcodeTokenSlice,
    build_stream_attachment_tree,
    encode_layer2_stream,
    preamble_token_slices,
    record_token_slices,
)
from lib.deprecated.pre_shared_model.lib.opcode.structure import OpcodeStructureContext, OpcodeStructureDescriptor, decode_layer2_record_to_structure
from lib.deprecated.pre_shared_model.lib.opcode.layer1 import OpcodeToken


@dataclass(frozen=True)
class OpcodeEmbeddedDescriptor:
    descriptor_id: str
    structure_type: str
    opaque: bool = True


@dataclass(frozen=True)
class OpcodeLayer3EmbeddedNode:
    descriptor: OpcodeEmbeddedDescriptor
    structure_type: str
    properties: dict[str, Any]
    start_atom: int
    end_atom: int
    token_slices: tuple[OpcodeTokenSlice, ...]
    children: tuple["OpcodeLayer3EmbeddedNode", ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "descriptor_id": self.descriptor.descriptor_id,
            "structure_type": self.structure_type,
            "opaque": bool(self.descriptor.opaque),
            "properties": dict(self.properties),
            "start_atom": int(self.start_atom),
            "end_atom": int(self.end_atom),
            "atom_count": int(self.end_atom - self.start_atom + 1),
            "token_slices": [tok.as_dict() for tok in self.token_slices],
            "children": [child.as_dict() for child in self.children],
        }

    def iter_nodes(self) -> Iterator["OpcodeLayer3EmbeddedNode"]:
        yield self
        for child in self.children:
            yield from child.iter_nodes()

    def matches(
        self,
        *,
        structure_type: str | None = None,
        descriptor_id: str | None = None,
        local_code: int | None = None,
    ) -> bool:
        if structure_type is not None and self.structure_type != structure_type:
            return False
        if descriptor_id is not None and self.descriptor.descriptor_id != descriptor_id:
            return False
        if local_code is not None and self.properties.get("LocalCode") != int(local_code):
            return False
        return True


@dataclass(frozen=True)
class OpcodeLayer3LocalSegment:
    start_atom: int
    end_atom: int
    token_slices: tuple[OpcodeTokenSlice, ...]
    recognized_structure_type: str | None

    def as_dict(self) -> dict[str, Any]:
        texts = [str(tok.text) for tok in self.token_slices if tok.text is not None]
        kind_prefix = [str(tok.kind) for tok in self.token_slices[: min(8, len(self.token_slices))]]
        value_prefix = [
            None if tok.text is not None else tok.value
            for tok in self.token_slices[: min(8, len(self.token_slices))]
        ]
        local_code = None
        if len(self.token_slices) > 1 and str(self.token_slices[1].kind) == "OP0F" and self.token_slices[1].value is not None:
            local_code = int(self.token_slices[1].value) - 0x4240
        return {
            "start_atom": int(self.start_atom),
            "end_atom": int(self.end_atom),
            "atom_count": int(self.end_atom - self.start_atom + 1),
            "recognized_structure_type": self.recognized_structure_type,
            "texts": texts,
            "local_code": local_code,
            "kind_prefix": kind_prefix,
            "value_prefix": value_prefix,
            "token_slices": [tok.as_dict() for tok in self.token_slices],
        }


@dataclass(frozen=True)
class OpcodeLayer3Node:
    descriptor: OpcodeStructureDescriptor
    structure_type: str
    properties: dict[str, Any]
    record: OpcodeLayer2Record
    token_slices: tuple[OpcodeTokenSlice, ...]
    parent_record_index: int | None
    depth: int
    local_segments: tuple[OpcodeLayer3LocalSegment, ...]
    embedded_children: tuple[OpcodeLayer3EmbeddedNode, ...]
    children: tuple["OpcodeLayer3Node", ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "descriptor_id": self.descriptor.descriptor_id,
            "structure_type": self.structure_type,
            "opaque": bool(self.descriptor.opaque),
            "properties": dict(self.properties),
            "record": self.record.as_dict(),
            "parent_record_index": self.parent_record_index,
            "depth": int(self.depth),
            "token_slices": [tok.as_dict() for tok in self.token_slices],
            "local_segments": [segment.as_dict() for segment in self.local_segments],
            "embedded_children": [child.as_dict() for child in self.embedded_children],
            "children": [child.as_dict() for child in self.children],
        }

    def prop(self, name: str, default: Any = None) -> Any:
        return self.properties.get(name, default)

    @property
    def opaque(self) -> bool:
        return bool(self.descriptor.opaque)

    def matches(
        self,
        *,
        structure_type: str | None = None,
        descriptor_id: str | None = None,
        props: dict[str, Any] | None = None,
        where: Callable[["OpcodeLayer3Node"], bool] | None = None,
    ) -> bool:
        if structure_type is not None and self.structure_type != structure_type:
            return False
        if descriptor_id is not None and self.descriptor.descriptor_id != descriptor_id:
            return False
        if props is not None:
            for key, value in props.items():
                if self.properties.get(key) != value:
                    return False
        if where is not None and not where(self):
            return False
        return True

    def iter_nodes(self) -> Iterator["OpcodeLayer3Node"]:
        yield self
        for child in self.children:
            yield from child.iter_nodes()

    def iter_embedded_nodes(self) -> Iterator[OpcodeLayer3EmbeddedNode]:
        for child in self.embedded_children:
            yield from child.iter_nodes()

    def find_embedded_all(
        self,
        *,
        structure_type: str | None = None,
        descriptor_id: str | None = None,
        local_code: int | None = None,
    ) -> list[OpcodeLayer3EmbeddedNode]:
        out: list[OpcodeLayer3EmbeddedNode] = []
        for child in self.iter_embedded_nodes():
            if child.matches(structure_type=structure_type, descriptor_id=descriptor_id, local_code=local_code):
                out.append(child)
        return out

    def find_embedded_first(
        self,
        *,
        structure_type: str | None = None,
        descriptor_id: str | None = None,
        local_code: int | None = None,
    ) -> OpcodeLayer3EmbeddedNode | None:
        for child in self.iter_embedded_nodes():
            if child.matches(structure_type=structure_type, descriptor_id=descriptor_id, local_code=local_code):
                return child
        return None

    def iter_records(self) -> Iterator[OpcodeLayer2Record]:
        for node in self.iter_nodes():
            yield node.record

    def child(self, index: int) -> "OpcodeLayer3Node":
        return self.children[index]

    def find_all(
        self,
        *,
        structure_type: str | None = None,
        descriptor_id: str | None = None,
        props: dict[str, Any] | None = None,
        where: Callable[["OpcodeLayer3Node"], bool] | None = None,
    ) -> list["OpcodeLayer3Node"]:
        out: list[OpcodeLayer3Node] = []
        for node in self.iter_nodes():
            if node.matches(structure_type=structure_type, descriptor_id=descriptor_id, props=props, where=where):
                out.append(node)
        return out

    def find_first(
        self,
        *,
        structure_type: str | None = None,
        descriptor_id: str | None = None,
        props: dict[str, Any] | None = None,
        where: Callable[["OpcodeLayer3Node"], bool] | None = None,
    ) -> "OpcodeLayer3Node" | None:
        for node in self.iter_nodes():
            if node.matches(structure_type=structure_type, descriptor_id=descriptor_id, props=props, where=where):
                return node
        return None


@dataclass(frozen=True)
class OpcodeLayer3Tree:
    header_text: str
    header_end: int
    preamble_fragments: tuple[Any, ...]
    preamble_token_slices: tuple[OpcodeTokenSlice, ...]
    root_sections: tuple["OpcodeLayer3RootSection", ...]
    roots: tuple[OpcodeLayer3Node, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "header_text": self.header_text,
            "header_end": int(self.header_end),
            "preamble_fragments": [frag.as_dict() for frag in self.preamble_fragments],
            "preamble_token_slices": [frag.as_dict() for frag in self.preamble_token_slices],
            "root_sections": [section.as_dict() for section in self.root_sections],
            "roots": [root.as_dict() for root in self.roots],
        }

    @property
    def root_count(self) -> int:
        return len(self.roots)

    @property
    def node_count(self) -> int:
        return sum(1 for _ in self.iter_nodes())

    @property
    def record_count(self) -> int:
        return self.node_count

    @property
    def embedded_node_count(self) -> int:
        return sum(1 for _ in self.iter_embedded_nodes())

    def iter_nodes(self) -> Iterator[OpcodeLayer3Node]:
        for root in self.roots:
            yield from root.iter_nodes()

    def iter_root_sections(self) -> Iterator["OpcodeLayer3RootSection"]:
        yield from self.root_sections

    def iter_records(self) -> Iterator[OpcodeLayer2Record]:
        for node in self.iter_nodes():
            yield node.record

    def iter_embedded_nodes(self) -> Iterator[OpcodeLayer3EmbeddedNode]:
        for root in self.roots:
            yield from root.iter_embedded_nodes()

    def find_embedded_all(
        self,
        *,
        structure_type: str | None = None,
        descriptor_id: str | None = None,
        local_code: int | None = None,
    ) -> list[OpcodeLayer3EmbeddedNode]:
        out: list[OpcodeLayer3EmbeddedNode] = []
        for root in self.roots:
            out.extend(root.find_embedded_all(structure_type=structure_type, descriptor_id=descriptor_id, local_code=local_code))
        return out

    def find_all(
        self,
        *,
        structure_type: str | None = None,
        descriptor_id: str | None = None,
        props: dict[str, Any] | None = None,
        where: Callable[[OpcodeLayer3Node], bool] | None = None,
    ) -> list[OpcodeLayer3Node]:
        out: list[OpcodeLayer3Node] = []
        for root in self.roots:
            out.extend(root.find_all(structure_type=structure_type, descriptor_id=descriptor_id, props=props, where=where))
        return out

    def find_first(
        self,
        *,
        structure_type: str | None = None,
        descriptor_id: str | None = None,
        props: dict[str, Any] | None = None,
        where: Callable[[OpcodeLayer3Node], bool] | None = None,
    ) -> OpcodeLayer3Node | None:
        for root in self.roots:
            got = root.find_first(structure_type=structure_type, descriptor_id=descriptor_id, props=props, where=where)
            if got is not None:
                return got
        return None

    def find_by_record_index(self, record_index: int) -> OpcodeLayer3Node | None:
        return self.find_first(where=lambda node: int(node.record.index) == int(record_index))

    def find_by_signature(self, signature_hex: str) -> list[OpcodeLayer3Node]:
        return self.find_all(where=lambda node: str(node.record.signature_hex) == str(signature_hex))

    def find_by_role(self, role: str) -> list[OpcodeLayer3Node]:
        return self.find_all(props={"Role": role})

    def structure_type_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for node in self.iter_nodes():
            counts[str(node.structure_type)] += 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def embedded_structure_type_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for node in self.iter_embedded_nodes():
            counts[str(node.structure_type)] += 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


@dataclass(frozen=True)
class OpcodeLayer3RootSection:
    section_index: int
    signature_hex: str
    start_root_index: int
    end_root_index: int
    roots: tuple[OpcodeLayer3Node, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "section_index": int(self.section_index),
            "signature_hex": str(self.signature_hex),
            "start_root_index": int(self.start_root_index),
            "end_root_index": int(self.end_root_index),
            "run_length": int(len(self.roots)),
            "root_record_indexes": [int(node.record.index) for node in self.roots],
        }

    @property
    def run_length(self) -> int:
        return len(self.roots)

    def signature_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter(str(node.record.signature_hex) for node in self.roots)
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


_EMBEDDED_ORUN_3B24_3B24_OP0F_TEXT_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_3b24_3b24_op0f_text.v1",
    structure_type="OpcodeEmbedded[ORUN,OP3B24,OP3B24,OP0F,TEXT]",
    opaque=True,
)

_EMBEDDED_ORUN_OP0F_OP0F44FC_OP0F_ZRUN_OP0F_TEXT_TEXT_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_op0f_op0f44fc_op0f_zrun_op0f_text_text.v1",
    structure_type="OpcodeEmbedded[ORUN,OP0F,OP0F44FC,OP0F,ZRUN,OP0F,TEXT,TEXT]",
    opaque=True,
)

_EMBEDDED_ORUN_OP0F_WRAPPER_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_op0f_wrapper.v1",
    structure_type="OpcodeEmbedded[ORUN,OP0F]",
    opaque=True,
)

_EMBEDDED_ORUN_OP0F_OP0F_OP0F_ZRUN_OP0F_ZRUN_OP3B24_BLOCK16_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_op0f_op0f_op0f_zrun_op0f_zrun_op3b24.block16.v1",
    structure_type="OpcodeEmbedded[ORUN,OP0F,OP0F,OP0F,ZRUN,OP0F,ZRUN,OP3B24].Block16",
    opaque=True,
)

_EMBEDDED_ORUN_4X3B24_OP0F_ZRUN_OP0F_2X3B24_BLOCK10_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_4x3b24_op0f_zrun_op0f_2x3b24.block10.v1",
    structure_type="OpcodeEmbedded[ORUN,4xOP3B24,OP0F,ZRUN,OP0F,2xOP3B24].Block10",
    opaque=True,
)

_EMBEDDED_ORUN_OP0F_2X3B24_TEXT_ZRUN_4X3B24_OP0F_BLOCK11_TEXT_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_op0f_2x3b24_text_zrun_4x3b24_op0f.block11_text.v1",
    structure_type="OpcodeEmbedded[ORUN,OP0F,2xOP3B24,TEXT,ZRUN,4xOP3B24,OP0F].Block11Text",
    opaque=True,
)

_EMBEDDED_ORUN_4XOP0F_3X3B24_2XTEXT_ZRUN_4X3B24_OP0F_ZRUN_OP0F_2X3B24_BLOCK20_TEXT2_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_4xop0f_3x3b24_2xtext_zrun_4x3b24_op0f_zrun_op0f_2x3b24.block20_text2.v1",
    structure_type="OpcodeEmbedded[ORUN,4xOP0F,3xOP3B24,2xTEXT,ZRUN,4xOP3B24,OP0F,ZRUN,OP0F,2xOP3B24].Block20Text2",
    opaque=True,
)

_EMBEDDED_ORUN_4XOP0F_3X3B24_2XTEXT_ZRUN_4X3B24_OP0F_ZRUN_OP0F_2X3B24_OP0F_BLOCK21_TEXT2_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_4xop0f_3x3b24_2xtext_zrun_4x3b24_op0f_zrun_op0f_2x3b24_op0f.block21_text2.v1",
    structure_type="OpcodeEmbedded[ORUN,4xOP0F,3xOP3B24,2xTEXT,ZRUN,4xOP3B24,OP0F,ZRUN,OP0F,2xOP3B24,OP0F].Block21Text2",
    opaque=True,
)

_EMBEDDED_ORUN_2X3B24_2XOP0F_ZRUN_2XOP0F_2X3B24_ZRUN_OP3B24_BLOCK12_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_2x3b24_2xop0f_zrun_2xop0f_2x3b24_zrun_op3b24.block12.v1",
    structure_type="OpcodeEmbedded[ORUN,2xOP3B24,2xOP0F,ZRUN,2xOP0F,2xOP3B24,ZRUN,OP3B24].Block12",
    opaque=True,
)

_EMBEDDED_ORUN_OP0F_4X3B24_OP0F_BLOCK7_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_op0f_4x3b24_op0f.block7.v1",
    structure_type="OpcodeEmbedded[ORUN,OP0F,4xOP3B24,OP0F].Block7",
    opaque=True,
)

_EMBEDDED_ORUN_OP0F_ZRUN_2X3B24_BLOCK5_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_op0f_zrun_2x3b24.block5.v1",
    structure_type="OpcodeEmbedded[ORUN,OP0F,ZRUN,2xOP3B24].Block5",
    opaque=True,
)

_EMBEDDED_ORUN_2X3B24_2XOP0F_ZRUN_2XOP0F_2X3B24_ZRUN_OP3B24_ZRUN_OP0F_2X3B24_4X3B24_OP0F_ZRUN_2X3B24_OP0F_ZRUN_4X3B24_ZRUN_6XOP0F_ZRUN_9X3B24_BLOCK46_DESCRIPTOR = OpcodeEmbeddedDescriptor(
    descriptor_id="OpcodeEmbedded.orun_2x3b24_2xop0f_zrun_2xop0f_2x3b24_zrun_op3b24_zrun_op0f_2x3b24_4x3b24_op0f_zrun_2x3b24_op0f_zrun_4x3b24_zrun_6xop0f_zrun_9x3b24.block46.v1",
    structure_type="OpcodeEmbedded[ORUN,2xOP3B24,2xOP0F,ZRUN,2xOP0F,2xOP3B24,ZRUN,OP3B24,ZRUN,OP0F,2xOP3B24,4xOP3B24,OP0F,ZRUN,2xOP3B24,OP0F,ZRUN,4xOP3B24,ZRUN,6xOP0F,ZRUN,9xOP3B24].Block46",
    opaque=True,
)


def _embedded_text_props(token_slices: tuple[OpcodeTokenSlice, ...]) -> dict[str, Any]:
    texts: list[str] = []
    text_slots: list[int] = []
    for idx, tok in enumerate(token_slices):
        if tok.text is None:
            continue
        texts.append(str(tok.text))
        text_slots.append(int(idx))
    return {
        "AtomCount": int(len(token_slices)),
        "Texts": texts,
        "TextSlots": text_slots,
    }


def _embedded_generic_props(token_slices: tuple[OpcodeTokenSlice, ...]) -> dict[str, Any]:
    props = _embedded_text_props(token_slices)
    props["KindPrefix"] = [str(tok.kind) for tok in token_slices[: min(8, len(token_slices))]]
    props["ValuePrefix"] = [
        None if tok.text is not None else tok.value
        for tok in token_slices[: min(8, len(token_slices))]
    ]
    op0f_values = [int(tok.value) for tok in token_slices if str(tok.kind) == "OP0F" and tok.value is not None]
    props["Op0FValuesPrefix"] = op0f_values[: min(8, len(op0f_values))]
    props["LocalCode"] = None if not op0f_values else int(op0f_values[0] - 0x4240)
    return props


def _find_next_orun(token_slices: tuple[OpcodeTokenSlice, ...], start: int, *, minimum_end: int) -> int | None:
    for idx in range(max(start + 1, minimum_end + 1), len(token_slices)):
        if str(token_slices[idx].kind) == "ORUN":
            return idx
    return None


def _match_orun_3b24_3b24_op0f_text(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    if start + 4 >= len(token_slices):
        return None
    a0, a1, a2, a3, a4 = token_slices[start : start + 5]
    if str(a0.kind) != "ORUN" or int(a0.value or -1) != 1:
        return None
    if str(a1.kind) != "OP3B24" or str(a2.kind) != "OP3B24":
        return None
    if str(a3.kind) != "OP0F":
        return None
    if a4.text is None:
        return None
    next_orun = _find_next_orun(token_slices, start, minimum_end=start + 24)
    if next_orun is None:
        return None
    return _EMBEDDED_ORUN_3B24_3B24_OP0F_TEXT_DESCRIPTOR, int(next_orun - 1)


def _match_orun_op0f_wrapper(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    if start + 2 >= len(token_slices):
        return None
    a0, a1, a2 = token_slices[start : start + 3]
    if str(a0.kind) != "ORUN" or int(a0.value or -1) != 1:
        return None
    if str(a1.kind) != "OP0F":
        return None
    if str(a2.kind) != "ORUN":
        return None
    return _EMBEDDED_ORUN_OP0F_WRAPPER_DESCRIPTOR, int(start + 1)


def _match_orun_op0f_op0f_op0f_zrun_op0f_zrun_op3b24_block16(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    end = start + 15
    if end >= len(token_slices):
        return None
    seq = token_slices[start : end + 1]
    if str(seq[0].kind) != "ORUN" or int(seq[0].value or -1) != 1:
        return None
    if not all(str(seq[idx].kind) == "OP0F" for idx in (1, 2, 3, 5)):
        return None
    if str(seq[4].kind) != "ZRUN" or int(seq[4].value if seq[4].value is not None else -1) != 0:
        return None
    if str(seq[6].kind) != "ZRUN" or int(seq[6].value if seq[6].value is not None else -1) != 0:
        return None
    if str(seq[7].kind) != "OP3B24":
        return None
    next_idx = start + 16
    if next_idx >= len(token_slices) or str(token_slices[next_idx].kind) != "ORUN":
        return None
    return _EMBEDDED_ORUN_OP0F_OP0F_OP0F_ZRUN_OP0F_ZRUN_OP3B24_BLOCK16_DESCRIPTOR, int(end)


def _match_orun_4x3b24_op0f_zrun_op0f_2x3b24_block10(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    end = start + 9
    if end >= len(token_slices):
        return None
    seq = token_slices[start : end + 1]
    if str(seq[0].kind) != "ORUN" or int(seq[0].value or -1) != 1:
        return None
    if not all(str(seq[idx].kind) == "OP3B24" for idx in (1, 2, 3, 4, 8, 9)):
        return None
    if str(seq[5].kind) != "OP0F":
        return None
    if str(seq[6].kind) != "ZRUN" or int(seq[6].value if seq[6].value is not None else -1) != 0:
        return None
    if str(seq[7].kind) != "OP0F":
        return None
    next_idx = start + 10
    if next_idx >= len(token_slices) or str(token_slices[next_idx].kind) != "ORUN":
        return None
    return _EMBEDDED_ORUN_4X3B24_OP0F_ZRUN_OP0F_2X3B24_BLOCK10_DESCRIPTOR, int(end)


def _match_orun_op0f_op0f44fc_op0f_zrun_op0f_text_text(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    if start + 7 >= len(token_slices):
        return None
    a0, a1, a2, a3, a4, a5, a6, a7 = token_slices[start : start + 8]
    if str(a0.kind) != "ORUN" or int(a0.value or -1) != 1:
        return None
    if str(a1.kind) != "OP0F":
        return None
    if str(a2.kind) != "OP0F" or int(a2.value or -1) != 17660:
        return None
    if str(a3.kind) != "OP0F" or int(a3.value or -1) != 16962:
        return None
    if str(a4.kind) != "ZRUN" or int(a4.value if a4.value is not None else -1) != 0:
        return None
    if str(a5.kind) != "OP0F":
        return None
    if a6.text is None or a7.text is None:
        return None
    next_orun = _find_next_orun(token_slices, start, minimum_end=start + 12)
    if next_orun is None:
        return None
    return _EMBEDDED_ORUN_OP0F_OP0F44FC_OP0F_ZRUN_OP0F_TEXT_TEXT_DESCRIPTOR, int(next_orun - 1)


def _match_orun_op0f_2x3b24_text_zrun_4x3b24_op0f_block11_text(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    end = start + 10
    if end >= len(token_slices):
        return None
    seq = token_slices[start : end + 1]
    if str(seq[0].kind) != "ORUN" or int(seq[0].value or -1) != 1:
        return None
    if str(seq[1].kind) != "OP0F":
        return None
    if str(seq[2].kind) != "OP3B24" or str(seq[3].kind) != "OP3B24":
        return None
    if seq[4].text is None:
        return None
    if str(seq[5].kind) != "ZRUN" or int(seq[5].value if seq[5].value is not None else -1) != 0:
        return None
    if not all(str(seq[idx].kind) == "OP3B24" for idx in (6, 7, 8, 9)):
        return None
    if str(seq[10].kind) != "OP0F":
        return None
    next_idx = start + 11
    if next_idx >= len(token_slices) or str(token_slices[next_idx].kind) != "ORUN":
        return None
    return _EMBEDDED_ORUN_OP0F_2X3B24_TEXT_ZRUN_4X3B24_OP0F_BLOCK11_TEXT_DESCRIPTOR, int(end)


def _match_exact_kinds(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
    *,
    kinds: tuple[str, ...],
) -> int | None:
    end = start + len(kinds) - 1
    if end >= len(token_slices):
        return None
    seq = token_slices[start : end + 1]
    if any(str(tok.kind) != expected for tok, expected in zip(seq, kinds)):
        return None
    next_idx = end + 1
    if next_idx < len(token_slices) and str(token_slices[next_idx].kind) != "ORUN":
        return None
    return int(end)


def _match_orun_4xop0f_3x3b24_2xtext_zrun_4x3b24_op0f_zrun_op0f_2x3b24_block20_text2(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    end = _match_exact_kinds(
        token_slices,
        start,
        kinds=(
            "ORUN", "OP0F", "OP0F", "OP0F", "OP0F",
            "OP3B24", "OP3B24", "OP3B24",
            "STR16BE_LEN16", "STR16BE_LEN16",
            "ZRUN",
            "OP3B24", "OP3B24", "OP3B24", "OP3B24",
            "OP0F", "ZRUN", "OP0F", "OP3B24", "OP3B24",
        ),
    )
    if end is None:
        return None
    return _EMBEDDED_ORUN_4XOP0F_3X3B24_2XTEXT_ZRUN_4X3B24_OP0F_ZRUN_OP0F_2X3B24_BLOCK20_TEXT2_DESCRIPTOR, end


def _match_orun_4xop0f_3x3b24_2xtext_zrun_4x3b24_op0f_zrun_op0f_2x3b24_op0f_block21_text2(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    end = _match_exact_kinds(
        token_slices,
        start,
        kinds=(
            "ORUN", "OP0F", "OP0F", "OP0F", "OP0F",
            "OP3B24", "OP3B24", "OP3B24",
            "STR16BE_LEN16", "STR16BE_LEN16",
            "ZRUN",
            "OP3B24", "OP3B24", "OP3B24", "OP3B24",
            "OP0F", "ZRUN", "OP0F", "OP3B24", "OP3B24", "OP0F",
        ),
    )
    if end is None:
        return None
    return _EMBEDDED_ORUN_4XOP0F_3X3B24_2XTEXT_ZRUN_4X3B24_OP0F_ZRUN_OP0F_2X3B24_OP0F_BLOCK21_TEXT2_DESCRIPTOR, end


def _match_orun_2x3b24_2xop0f_zrun_2xop0f_2x3b24_zrun_op3b24_block12(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    end = _match_exact_kinds(
        token_slices,
        start,
        kinds=(
            "ORUN", "OP3B24", "OP3B24", "OP0F", "OP0F", "ZRUN", "OP0F", "OP0F",
            "OP3B24", "OP3B24", "ZRUN", "OP3B24",
        ),
    )
    if end is None:
        return None
    return _EMBEDDED_ORUN_2X3B24_2XOP0F_ZRUN_2XOP0F_2X3B24_ZRUN_OP3B24_BLOCK12_DESCRIPTOR, end


def _match_orun_op0f_4x3b24_op0f_block7(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    end = _match_exact_kinds(
        token_slices,
        start,
        kinds=("ORUN", "OP0F", "OP3B24", "OP3B24", "OP3B24", "OP3B24", "OP0F"),
    )
    if end is None:
        return None
    return _EMBEDDED_ORUN_OP0F_4X3B24_OP0F_BLOCK7_DESCRIPTOR, end


def _match_orun_op0f_zrun_2x3b24_block5(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    end = _match_exact_kinds(
        token_slices,
        start,
        kinds=("ORUN", "OP0F", "ZRUN", "OP3B24", "OP3B24"),
    )
    if end is None:
        return None
    return _EMBEDDED_ORUN_OP0F_ZRUN_2X3B24_BLOCK5_DESCRIPTOR, end


def _match_orun_block46(
    token_slices: tuple[OpcodeTokenSlice, ...],
    start: int,
) -> tuple[OpcodeEmbeddedDescriptor, int] | None:
    end = _match_exact_kinds(
        token_slices,
        start,
        kinds=(
            "ORUN", "OP3B24", "OP3B24", "OP0F", "OP0F", "ZRUN", "OP0F", "OP0F",
            "OP3B24", "OP3B24", "ZRUN", "OP3B24", "ZRUN", "OP0F", "OP3B24", "OP3B24",
            "OP3B24", "OP3B24", "OP0F", "ZRUN", "OP3B24", "OP3B24", "OP0F", "ZRUN",
            "OP3B24", "OP3B24", "OP3B24", "OP3B24", "ZRUN", "OP0F", "OP0F", "OP0F",
            "OP0F", "OP0F", "OP0F", "ZRUN", "OP3B24", "OP3B24", "OP3B24", "OP3B24",
            "OP3B24", "OP3B24", "OP3B24", "OP3B24", "OP3B24", "ZRUN",
        ),
    )
    if end is None:
        return None
    return _EMBEDDED_ORUN_2X3B24_2XOP0F_ZRUN_2XOP0F_2X3B24_ZRUN_OP3B24_ZRUN_OP0F_2X3B24_4X3B24_OP0F_ZRUN_2X3B24_OP0F_ZRUN_4X3B24_ZRUN_6XOP0F_ZRUN_9X3B24_BLOCK46_DESCRIPTOR, end


def _extract_embedded_nodes(
    token_slices: tuple[OpcodeTokenSlice, ...],
    *,
    atom_base: int = 0,
) -> tuple[OpcodeLayer3EmbeddedNode, ...]:
    # Embedded grammar is still exploratory. Keep start rules exact and end
    # rules conservative: consume from a proven local header up to the next
    # local ORUN anchor after a family-specific minimum block size.
    out: list[OpcodeLayer3EmbeddedNode] = []
    i = 0
    while i < len(token_slices):
        matched = _match_orun_op0f_wrapper(token_slices, i)
        if matched is None:
            matched = _match_orun_op0f_zrun_2x3b24_block5(token_slices, i)
        if matched is None:
            matched = _match_orun_op0f_4x3b24_op0f_block7(token_slices, i)
        if matched is None:
            matched = _match_orun_2x3b24_2xop0f_zrun_2xop0f_2x3b24_zrun_op3b24_block12(token_slices, i)
        if matched is None:
            matched = _match_orun_op0f_op0f_op0f_zrun_op0f_zrun_op3b24_block16(token_slices, i)
        if matched is None:
            matched = _match_orun_4xop0f_3x3b24_2xtext_zrun_4x3b24_op0f_zrun_op0f_2x3b24_block20_text2(token_slices, i)
        if matched is None:
            matched = _match_orun_4xop0f_3x3b24_2xtext_zrun_4x3b24_op0f_zrun_op0f_2x3b24_op0f_block21_text2(token_slices, i)
        if matched is None:
            matched = _match_orun_4x3b24_op0f_zrun_op0f_2x3b24_block10(token_slices, i)
        if matched is None:
            matched = _match_orun_op0f_op0f44fc_op0f_zrun_op0f_text_text(token_slices, i)
        if matched is None:
            matched = _match_orun_op0f_2x3b24_text_zrun_4x3b24_op0f_block11_text(token_slices, i)
        if matched is None:
            matched = _match_orun_3b24_3b24_op0f_text(token_slices, i)
        if matched is None:
            matched = _match_orun_block46(token_slices, i)
        if matched is None:
            i += 1
            continue
        descriptor, end_idx = matched
        block_slices = tuple(token_slices[i : end_idx + 1])
        children = _extract_embedded_nodes(block_slices[1:], atom_base=atom_base + i + 1)
        props = _embedded_generic_props(block_slices)
        out.append(
            OpcodeLayer3EmbeddedNode(
                descriptor=descriptor,
                structure_type=str(descriptor.structure_type),
                properties=props,
                start_atom=int(atom_base + i),
                end_atom=int(atom_base + end_idx),
                token_slices=block_slices,
                children=children,
            )
        )
        i = end_idx + 1
    return tuple(out)


def _extract_local_segments(
    token_slices: tuple[OpcodeTokenSlice, ...],
    embedded_children: tuple[OpcodeLayer3EmbeddedNode, ...],
) -> tuple[OpcodeLayer3LocalSegment, ...]:
    if not token_slices:
        return ()
    starts = [idx for idx, tok in enumerate(token_slices) if str(tok.kind) == "ORUN"]
    if not starts or starts[0] != 0:
        starts = [0, *starts]
    embedded_by_span = {
        (int(node.start_atom), int(node.end_atom)): str(node.structure_type)
        for node in embedded_children
    }
    out: list[OpcodeLayer3LocalSegment] = []
    for idx, start in enumerate(starts):
        end = (starts[idx + 1] - 1) if idx + 1 < len(starts) else (len(token_slices) - 1)
        out.append(
            OpcodeLayer3LocalSegment(
                start_atom=int(start),
                end_atom=int(end),
                token_slices=tuple(token_slices[start : end + 1]),
                recognized_structure_type=embedded_by_span.get((int(start), int(end))),
            )
        )
    return tuple(out)


def build_layer3_tree_from_layer2(stream: OpcodeLayer2Stream, *, tokens: list[OpcodeToken] | None = None) -> OpcodeLayer3Tree:
    attachment_tree = build_stream_attachment_tree(list(stream.records))
    by_index = {int(record.index): record for record in stream.records}
    by_node_index = {int(node["index"]): node for node in attachment_tree["nodes"]}
    tokens_tuple = None if tokens is None else tuple(tokens)

    def _build(
        node_index: int,
        *,
        parent_record_index: int | None,
        parent_signature_hex: str | None,
        depth: int,
    ) -> OpcodeLayer3Node:
        node = by_node_index[int(node_index)]
        record = by_index[int(node["index"])]
        token_slices = () if tokens is None else record_token_slices(record, tokens)
        children = tuple(
            _build(
                int(child_index),
                parent_record_index=int(record.index),
                parent_signature_hex=str(record.signature_hex),
                depth=int(depth + 1),
            )
            for child_index in node.get("children", [])
        )
        descriptor, properties = decode_layer2_record_to_structure(
            OpcodeStructureContext(record=record, token_slices_value=token_slices, tokens=tokens_tuple)
        )
        properties = dict(properties)
        embedded_children = _extract_embedded_nodes(token_slices)
        local_segments = _extract_local_segments(token_slices, embedded_children)
        properties["ChildCount"] = len(children)
        properties["ChildSignatures"] = [str(child.record.signature_hex) for child in children]
        properties["ParentSignature"] = parent_signature_hex
        properties["Depth"] = int(depth)
        properties["TextCount"] = len([tok for tok in token_slices if tok.text is not None])
        properties["HasTexts"] = bool(properties["TextCount"])
        properties["LocalSegmentCount"] = len(local_segments)
        properties["LocalSegmentSpans"] = [[int(seg.start_atom), int(seg.end_atom)] for seg in local_segments]
        properties["LocalSegmentRecognizedTypes"] = [seg.recognized_structure_type for seg in local_segments]
        properties["EmbeddedCount"] = len(embedded_children)
        properties["EmbeddedTypes"] = [str(child.structure_type) for child in embedded_children]
        properties["EmbeddedSequence"] = [str(child.structure_type) for child in embedded_children]
        properties["EmbeddedLocalCodes"] = [child.properties.get("LocalCode") for child in embedded_children]
        properties["EmbeddedAtomSpans"] = [
            [int(child.start_atom), int(child.end_atom)]
            for child in embedded_children
        ]
        embedded_type_counts: Counter[str] = Counter(str(child.structure_type) for child in embedded_children)
        properties["EmbeddedTypeCounts"] = dict(embedded_type_counts)
        return OpcodeLayer3Node(
            descriptor=descriptor,
            structure_type=str(descriptor.structure_type),
            properties=properties,
            record=record,
            token_slices=token_slices,
            parent_record_index=parent_record_index,
            depth=int(depth),
            local_segments=local_segments,
            embedded_children=embedded_children,
            children=children,
        )

    roots = tuple(
        _build(
            int(idx),
            parent_record_index=None,
            parent_signature_hex=None,
            depth=0,
        )
        for idx in attachment_tree["roots"]
    )
    root_sections: list[OpcodeLayer3RootSection] = []
    i = 0
    while i < len(roots):
        j = i + 1
        sig = str(roots[i].record.signature_hex)
        while j < len(roots) and str(roots[j].record.signature_hex) == sig:
            j += 1
        root_sections.append(
            OpcodeLayer3RootSection(
                section_index=int(len(root_sections)),
                signature_hex=sig,
                start_root_index=int(i),
                end_root_index=int(j - 1),
                roots=tuple(roots[i:j]),
            )
        )
        i = j
    section_by_root_index: dict[int, OpcodeLayer3RootSection] = {}
    for section in root_sections:
        for root_index in range(section.start_root_index, section.end_root_index + 1):
            section_by_root_index[int(root_index)] = section
    rebased_roots: list[OpcodeLayer3Node] = []
    for root_index, root in enumerate(roots):
        section = section_by_root_index[int(root_index)]
        props = dict(root.properties)
        props["RootSectionIndex"] = int(section.section_index)
        props["RootSectionSignature"] = str(section.signature_hex)
        props["RootSectionRunLength"] = int(section.run_length)
        rebased_roots.append(
            OpcodeLayer3Node(
                descriptor=root.descriptor,
                structure_type=root.structure_type,
                properties=props,
                record=root.record,
                token_slices=root.token_slices,
                parent_record_index=root.parent_record_index,
                depth=root.depth,
                local_segments=root.local_segments,
                embedded_children=root.embedded_children,
                children=root.children,
            )
        )
    roots = tuple(rebased_roots)
    return OpcodeLayer3Tree(
        header_text=stream.header_text,
        header_end=int(stream.header_end),
        preamble_fragments=stream.preamble_fragments,
        preamble_token_slices=() if tokens is None else preamble_token_slices(stream, tokens),
        root_sections=tuple(root_sections),
        roots=roots,
    )


def build_layer2_stream_from_layer3(tree: OpcodeLayer3Tree) -> OpcodeLayer2Stream:
    flat_records = list(tree.iter_records())
    flat_records.sort(key=lambda rec: int(rec.index))
    return OpcodeLayer2Stream(
        header_text=tree.header_text,
        header_end=int(tree.header_end),
        preamble_fragments=tuple(tree.preamble_fragments),
        records=tuple(flat_records),
    )


def encode_layer3_tree(tree: OpcodeLayer3Tree, tokens: list[OpcodeToken]) -> bytes:
    return encode_layer2_stream(build_layer2_stream_from_layer3(tree), tokens)
