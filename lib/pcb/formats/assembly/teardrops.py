"""Consume saved teardrop keys into polygon, layer and trace identities."""
from ....common.conversion import import_notice
from ....common.drawing_records import POINT, POINTS
from ....common.structural_edits import assembly
from ...model import teardrops as model
from ..errors import PcbError


def assemble_teardrops(rules):
    document, core = rules.document, rules.routing.core
    links, stale, polygons = [], [], []
    for (net_key, key), polygon in core.teardrops.items():
        layer = polygon.child('Lay')
        if layer is None or len(layer.values) != 1 or type(layer.values[0]) is not int:
            raise PcbError(f'{polygon.path}: expected one teardrop copper-layer selection')
        target = rules.layers.get(layer.values[0])
        if target is None:
            raise PcbError(f'{polygon.path}: unresolved teardrop copper layer {layer.values[0]}')
        vertices = []
        for row in polygon.select('Points/Point'):
            if row.arguments and (len(row.arguments) != 1 or type(row.values[0]) is not int):
                raise PcbError(f'{row.path}: invalid input point counter')
            vertices.append((row, row['X'], row['Y']))
        polygons.append((polygon, layer, target, vertices))
    for net_key, net in core.nets.items():
        for trace in net.select('Traces/Trace'):
            for row in trace.select('ConnectedTeardrops/Item'):
                if len(row.values) != 1 or type(row.values[0]) is not int or row.children():
                    raise PcbError(f'{row.path}: expected one teardrop key')
                key = row.values[0]
                target = core.teardrops.get((net_key, key))
                if target is None:
                    stale.append((row, key))
                else:
                    links.append((row, target))
    with assembly(document), document.references.binding_batch():
        for net in core.nets.values():
            if (collection := net.child('Teardrops')) is not None:
                collection.bind_schema(model.TEARDROPS)
            for trace in net.select('Traces/Trace'):
                if (collection := trace.child('ConnectedTeardrops')) is not None:
                    collection.bind_schema(model.MEMBERS)
        for polygon, layer, target, vertices in polygons:
            layer.detach()
            polygon.set_values()
            polygon.bind_schema(model.TEARDROP)
            polygon.parent.bind_schema(model.TEARDROPS)
            polygon.one('Points').bind_schema(POINTS)
            for row, x, y in vertices:
                for field in ('X', 'Y'):
                    row.one(field).detach()
                row.kind = 'pt'
                row.set_values(x, y)
                row.bind_schema(POINT)
            document.references.bind(polygon, target, role='copper-layer', preserve=True)
        for row, key in stale:
            row.detach()
        for row, target in links:
            row.set_values()
            row.bind_schema(model.MEMBER)
            row.parent.bind_schema(model.MEMBERS)
            document.references.bind(row, target, role=model.ROLE, preserve=True)
    missing = tuple(row for row, key in stale if key >= 0)
    if missing:
        import_notice('info', 'stale-trace-teardrops',
            'Removed trace selections whose supplied teardrops no longer exist.', missing,
            recoverability='valid polygon geometry and trace selections retained')
    return rules
