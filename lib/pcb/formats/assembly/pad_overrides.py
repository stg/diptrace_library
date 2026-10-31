"""Bind placed-pad layer selectors to the board's copper layer identities."""
from ....common.structural_edits import assembly
from ...model import pad_records
from ..errors import PcbError


def assemble_pad_overrides(rules):
    document, layers = rules.document, rules.layers
    pads = rules.routing.core.pads.records
    records, links = [], []
    for pad in pads:
        for kind in ('HideLayer', 'BlindLayer'):
            for member in pad.select(kind+'/Item'):
                key, = member.values
                if key not in layers:
                    raise PcbError(f'unresolved pad {kind} layer {key}')
                records.append((member, pad_records.LAYER_MEMBER, ()))
                links.append((member, layers[key]))
        for thermal in pad.select('CustomSpokes/CustomSpoke'):
            key, kind, spoke, width = thermal.values
            if key >= 0:
                if key not in layers:
                    raise PcbError(f'unresolved pad thermal layer {key}')
                links.append((thermal, layers[key]))
            elif key != -1:
                raise PcbError(f'invalid pad thermal layer {key}')
            records.append((thermal, pad_records.THERMAL, (kind, spoke, width)))
    with assembly(document):
        for node, schema, values in records:
            node.set_values()
            if schema is pad_records.THERMAL:
                for name, value in zip(('Type', 'Spoke', 'Width'), values):
                    node.add(name, value)
            node.bind_schema(schema)
        for pad in pads:
            for node in pad.walk(include_self=True):
                if (schema := pad_records.definition(node)) is not None:
                    node.bind_schema(schema)
        for node in document.select('/Board/Nets/Net/TeardropParams'):
            node.bind_schema(pad_records.TEARDROP)
        with document.references.binding_batch():
            for source, target in links:
                document.references.bind(source, target, role='copper-layer', preserve=True)
    return rules
