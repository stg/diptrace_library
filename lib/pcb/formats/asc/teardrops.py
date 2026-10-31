"""ASC teardrop settings and compact supplied polygon vertices."""
from .values import rename, numeric_row
from ..errors import PcbError


PARAMETERS = {
    'Teardrop_PadVia': 'PadVia', 'Teardrop_Smd': 'Smd', 'Teardrop_Trace': 'Trace',
    'TearDrop_Trace': 'Trace',
    'Teardrop_TJunction': 'TJunc', 'Teardrop_PadVia_Width': 'PadViaWidth',
    'Teardrop_PadVia_Length': 'PadViaLength', 'Teardrop_Smd_Width': 'SmdWidth',
    'Teardrop_Smd_Length': 'SmdLength', 'Teardrop_Trace_Length': 'TraceLength',
    'Teardrop_TJunction_Length': 'TJuncLength',
}


def unpack_parameters(owner):
    settings = [(node, PARAMETERS[node.kind]) for node in owner.children() if node.kind in PARAMETERS]
    if not settings:
        return
    if len({name for node, name in settings}) != len(settings):
        raise PcbError(f'{owner.path}: duplicate teardrop parameter aliases')
    if owner.child('TeardropParams') is not None:
        raise PcbError(f'{owner.path}: duplicate teardrop parameters')
    parameters = owner.add('TeardropParams')
    for node, name in settings:
        node.kind = name
        node.move_to(parameters)


def unpack_teardrops(net):
    unpack_parameters(net)
    for index, polygon in enumerate(net.select('Teardrops/Teardrop')):
        if polygon.arguments:
            raise PcbError(f'{polygon.path}: unexpected teardrop header')
        polygon.set_values(index)
        rename(polygon, {'Layer': 'Lay'})
        for index, row in enumerate(polygon.select('Points/Point')):
            values = numeric_row(row, 2, kind='Point')
            row.set_values(index)
            row.add('X', values[0])
            row.add('Y', values[1])
