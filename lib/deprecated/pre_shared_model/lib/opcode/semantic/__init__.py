from __future__ import annotations

"""Semantic layer over the structural opcode tree."""

from .codecs import apply_semantic_tree_to_tokens, decode_descriptor_fields
from .model import (
    OpcodeSemanticContext,
    OpcodeSemanticDescriptor,
    OpcodeSemanticField,
    OpcodeSemanticNode,
    OpcodeSemanticRule,
    OpcodeSemanticTree,
)
from .registry import resolve_semantic_descriptor

from lib.deprecated.pre_shared_model.lib.opcode.layer3 import OpcodeLayer3Tree, encode_layer3_tree


def build_semantic_tree_from_layer3(tree: OpcodeLayer3Tree) -> OpcodeSemanticTree:
    def _build(node):
        from .model import OpcodeSemanticContext, OpcodeSemanticNode

        descriptor = resolve_semantic_descriptor(OpcodeSemanticContext(node=node))
        props, field_atoms = decode_descriptor_fields(node, descriptor)
        props["Signature"] = str(node.record.signature_hex)
        props["PrefixByte"] = f"{int(node.record.prefix_byte):02x}"
        props["TailClass"] = str(node.record.tail_class)
        children = tuple(_build(child) for child in node.children)
        return OpcodeSemanticNode(
            descriptor=descriptor,
            semantic_type=str(descriptor.semantic_type),
            props=props,
            field_atoms=field_atoms,
            backing_node=node,
            children=children,
        )

    return OpcodeSemanticTree(structural_tree=tree, roots=tuple(_build(root) for root in tree.roots))


def encode_semantic_tree(tree: OpcodeSemanticTree, tokens):
    updated_tokens = apply_semantic_tree_to_tokens(tree, list(tokens))
    return encode_layer3_tree(tree.structural_tree, updated_tokens)


def decode_opcode_semantic_tree(path):
    from lib.deprecated.pre_shared_model.lib.opcode.layer1 import read_dch_header
    from lib.deprecated.pre_shared_model.lib.opcode.layer2 import build_layer2_stream_from_tokens
    from lib.deprecated.pre_shared_model.lib.opcode.layer3 import build_layer3_tree_from_layer2
    from lib.deprecated.pre_shared_model.lib.opcode.layer1 import read_bytes, tokenize_opcode_layer

    data = read_bytes(path)
    header_end, header_text = read_dch_header(data)
    tokens = tokenize_opcode_layer(data)
    stream = build_layer2_stream_from_tokens(header_text=header_text, header_end=header_end, tokens=tokens)
    layer3_tree = build_layer3_tree_from_layer2(stream, tokens=tokens)
    return tokens, stream, layer3_tree, build_semantic_tree_from_layer3(layer3_tree)


__all__ = [
    "OpcodeSemanticContext",
    "OpcodeSemanticDescriptor",
    "OpcodeSemanticField",
    "OpcodeSemanticNode",
    "OpcodeSemanticRule",
    "OpcodeSemanticTree",
    "build_semantic_tree_from_layer3",
    "decode_opcode_semantic_tree",
    "encode_semantic_tree",
    "resolve_semantic_descriptor",
]
