from __future__ import annotations

"""Declarative semantic model over the structural opcode tree.

Semantic descriptors are intentionally data-only:
- match on structural evidence
- map named fields to linear structural atoms
- keep unknown structures lossless through structural backing
"""

from dataclasses import dataclass
from typing import Any, Callable

from lib.deprecated.pre_shared_model.lib.opcode.layer3 import OpcodeLayer3Node, OpcodeLayer3Tree


@dataclass(frozen=True)
class OpcodeSemanticField:
    name: str
    codec: str
    default: Any = None
    nullable: bool = False


@dataclass(frozen=True)
class OpcodeSemanticDescriptor:
    descriptor_id: str
    semantic_type: str
    signature_hex: str | None = None
    fields: tuple[OpcodeSemanticField, ...] = ()
    opaque: bool = True


@dataclass(frozen=True)
class OpcodeSemanticContext:
    node: OpcodeLayer3Node


@dataclass(frozen=True)
class OpcodeSemanticRule:
    descriptor: OpcodeSemanticDescriptor
    match: Callable[[OpcodeSemanticContext], bool]


@dataclass(frozen=True)
class OpcodeSemanticNode:
    descriptor: OpcodeSemanticDescriptor
    semantic_type: str
    props: dict[str, Any]
    field_atoms: dict[str, int | None]
    backing_node: OpcodeLayer3Node
    children: tuple["OpcodeSemanticNode", ...]

    def prop(self, name: str, default: Any = None) -> Any:
        return self.props.get(name, default)

    def as_dict(self) -> dict[str, Any]:
        return {
            "descriptor_id": self.descriptor.descriptor_id,
            "semantic_type": self.semantic_type,
            "opaque": bool(self.descriptor.opaque),
            "props": dict(self.props),
            "field_atoms": dict(self.field_atoms),
            "backing_record_index": int(self.backing_node.record.index),
            "children": [child.as_dict() for child in self.children],
        }


@dataclass(frozen=True)
class OpcodeSemanticTree:
    structural_tree: OpcodeLayer3Tree
    roots: tuple[OpcodeSemanticNode, ...]

    def iter_nodes(self):
        stack = list(reversed(self.roots))
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    def find_all(self, *, semantic_type: str | None = None, where: Callable[[OpcodeSemanticNode], bool] | None = None) -> list[OpcodeSemanticNode]:
        out: list[OpcodeSemanticNode] = []
        for node in self.iter_nodes():
            if semantic_type is not None and node.semantic_type != semantic_type:
                continue
            if where is not None and not where(node):
                continue
            out.append(node)
        return out

    def find_first(self, *, semantic_type: str | None = None, where: Callable[[OpcodeSemanticNode], bool] | None = None) -> OpcodeSemanticNode | None:
        for node in self.iter_nodes():
            if semantic_type is not None and node.semantic_type != semantic_type:
                continue
            if where is not None and not where(node):
                continue
            return node
        return None


def field(
    name: str,
    *,
    codec: str,
    default: Any = None,
    nullable: bool = False,
) -> OpcodeSemanticField:
    return OpcodeSemanticField(
        name=name,
        codec=codec,
        default=default,
        nullable=bool(nullable),
    )


def blob(name: str) -> OpcodeSemanticField:
    return field(name, codec="blob")


def unknown(name: str) -> OpcodeSemanticField:
    # Compatibility alias for older drafts. Prefer blob(...).
    return blob(name)


def text(name: str, *, nullable: bool = False, default: Any = None) -> OpcodeSemanticField:
    return field(name, codec="text", default=default, nullable=nullable)


def integer(name: str, *, nullable: bool = False, default: Any = None) -> OpcodeSemanticField:
    return field(name, codec="int", default=default, nullable=nullable)


def empty_text(name: str) -> OpcodeSemanticField:
    return field(name, codec="empty_text")


def tok42_int(name: str, *, default: Any = None) -> OpcodeSemanticField:
    return field(name, codec="tok42_int", default=default)


def bool_run(name: str, *, default: Any = None) -> OpcodeSemanticField:
    return field(name, codec="bool_run", default=default)


def angle_deg(name: str, *, default: Any = None) -> OpcodeSemanticField:
    return field(name, codec="angle_deg", default=default)


def coord_bias1e4(name: str, *, default: Any = None) -> OpcodeSemanticField:
    return field(name, codec="coord_bias1e4", default=default)
