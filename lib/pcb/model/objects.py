"""Core PCB record constructors; no routing or geometric editing algorithms."""
from ...common.model import Element
from ...common.schema import MISSING
from ...common.footprint_objects import (new_pad as new_footprint_pad, new_pattern,
                                       new_pattern_drawing as new_footprint_drawing)
from .definitions import COMPONENT, PAD, PATTERN, PATTERN_SHAPE, NET, DOCUMENT, establish_records
from .document import Document
from . import routing_records, board_rules, markings


def _defaults(node, schema):
    node.bind_schema(schema)
    for name, field in schema.fields.items():
        if field.getter is None and field.default is not MISSING and node.child(name) is None:
            node.add(name, field.default)
    return node


def new_pad(number='', name='', *, x=0, y=0):
    pad = new_footprint_pad(number, name, x=x, y=y)
    pad.one('Number_New').detach()
    _defaults(pad, PAD)
    establish_records(pad)
    return pad


def new_component(name='', refdes=''):
    component = _defaults(Element('Component', name, refdes), COMPONENT)
    # A newly authored PCB component has no linked schematic component.
    component['HiddenId'] = -1
    component.add('UserFields')
    component.add('Component_CategoryTypes')
    pattern = new_pattern()
    pattern.one('Pattern_Manufacturer').detach()
    component.append(pattern.bind_schema(PATTERN))
    establish_records(component)
    return component


def new_user_field(name='', value='', *, kind=0):
    """Create user data with independent silk/assembly marking placements."""
    return _defaults(Element('UserField', name, value, kind), markings.USER_FIELD)


def new_pattern_drawing(*, kind=0):
    """Create footprint geometry with PCB drawing constraints and defaults."""
    drawing = new_footprint_drawing(kind=kind)
    drawing.one('PadId').detach()
    _defaults(drawing, PATTERN_SHAPE)
    establish_records(drawing)
    return drawing


def new_net(name=''):
    net = _defaults(Element('Net', name), NET)
    net.add('Pads')
    net.add('Traces')
    establish_records(net)
    return net


def new_point(*, x=0, y=0, width=-1):
    point = _defaults(Element('Point'), routing_records.POINT)
    point['X'], point['Y'], point['Width'] = x, y, width
    return point


def new_trace():
    trace = _defaults(Element('Trace'), routing_records.TRACE)
    trace.add('Points').bind_schema(routing_records.COLLECTIONS['Points'])
    return trace


def new_pair(name=''):
    pair = _defaults(Element('DifferentialPair'), routing_records.PAIR)
    pair['Name'] = name
    for name in ('PadPoints', 'Segments', 'PosSeparateTraces', 'NegSeparateTraces'):
        pair.add(name).bind_schema(routing_records.COLLECTIONS[name])
    return pair


def new_removed_pair(name=''):
    """Create restorable pair data; this does not remove or restore any routing."""
    pair = _defaults(Element('RemovedDifferentialPair'), routing_records.REMOVED_PAIR)
    pair['Name'] = name
    for name in ('PadPoints', 'Segments'):
        pair.add(name).bind_schema(routing_records.COLLECTIONS[name])
    return pair


def new_document():
    document = Document()
    _defaults(document.root, DOCUMENT)
    board = document.root.add('Board')
    board.add('Components')
    board.add('Nets')
    layers = board.add('Layers')
    layers.append(new_layer('Top'))
    layers.append(new_layer('Bottom'))
    board.add('ViaStyles')
    board.add('NetClasses')
    board.add('DesignCache_Count', -1)
    board.add('DesignCache_Links')
    cache = board.add('CacheLib')
    for name in ('Categories', 'Subfolders', 'Slots'):
        cache.add(name)
    establish_records(document.root)
    return document


def new_layer(name=''):
    return _defaults(Element('Layer', name), board_rules.LAYER)


def new_via_style(name='', *, size=0, hole_size=0):
    style = _defaults(Element('ViaStyle', name), board_rules.VIA)
    style['Size'], style['HoleSize'] = size, hole_size
    return style


def new_net_class(name=''):
    return _defaults(Element('NetClass', name), board_rules.NET_CLASS)
