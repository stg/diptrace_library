"""Board XML dimensions over current attachment identities and authored anchors."""
from ....common.conversion import warn
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_footprint_output import project_dimension
from ...model import graphic_records
from ...model.dimensions import BOARD_ROLES
from ..errors import PcbError
from ..output_indices import non_signal_number
from ..output_validation import check_tree, field_value
from .dimensions import CONNECTIONS
from .dimension_attachments import marking_endpoint


def _ancestor(node, kind):
    while node is not None and node.kind != kind:
        node = node.parent
    return node


def _attachment(dimension, side, *, board, keys, report):
    mode = dimension['Connected'+side]
    owner, member, point = (dimension[name+side] for name in ('Object', 'SubObject', 'Point'))
    document = dimension._owner()
    names = tuple(dimension.one(name+side) for name in ('Object', 'SubObject', 'Point'))
    unresolved = document is not None and any(document.references.unresolved_slot(field) for field in names)
    links = document.references.outgoing(dimension, role=BOARD_ROLES[int(side)-1]) if document is not None else ()
    if mode in range(8) and not unresolved and len(links) != 1:
        raise PcbError(f'{dimension.path}: bind the dimension attachment before export')
    if unresolved:
        warn(report, 'unresolved-dimension-attachment', 'dipxml', 'Dimension attachment is unavailable', (dimension,),
             recoverability='authored coordinates and current unresolved selectors remain available')
    if mode in (0, 1, 2):
        target = links[0].target if len(links) == 1 else None
        if target is not None:
            target = _ancestor(target, ('Pad', 'Shape', 'Hole')[mode])
        elif unresolved:
            # An unavailable vertex can still have a valid current owner. The
            # model guards freeze that scope until the selection is repaired.
            components = board.select('Components/Component')
            if not 0 <= owner < len(components):
                raise PcbError(f'{dimension.path}: unresolved attachment owner needs an XML mapping')
            collection, offset = (('Pads/Pad', 1), ('Shapes/Shape', 0), ('Holes/Hole', 0))[mode]
            members = components[owner].select('Pattern/'+collection)
            if not 0 <= member-offset < len(members):
                raise PcbError(f'{dimension.path}: unresolved attachment member needs an XML mapping')
            target = members[member-offset]
        if target is None:
            raise PcbError(f'{dimension.path}: bind the placed dimension attachment before export')
        if mode == 1 and (adapted := marking_endpoint(dimension, side, target, report=report)) is not None:
            return adapted
        owner, member = (keys.pad, keys.shape, keys.hole)[mode](target)
    elif mode not in (-1, 3, 4, 5, 6, 7, 8, 9):
        raise PcbError(f'{dimension.path}: dimension attachment mode {mode} needs an XML mapping')
    return mode, owner, member, point


def project_dimensions(board, *, keys, units, physical_font_width=True, report=None):
    result = Element('Dimensions')
    for dimension in board.select('Dimensions/Dimension'):
        check_tree(dimension, graphic_records.DIMENSION, destination='DIPXML')
        if not field_value(dimension, 'Enabled'):
            raise PcbError(f'{dimension.path}: inactive dimension needs output normalization')
        if dimension.child('UnresolvedKeys') is not None:
            raise PcbError(f'{dimension.path}: unresolved dimension extensions need a PCB XML mapping')
        attachments = tuple(_attachment(dimension, side, board=board, keys=keys, report=report)
                            for side in ('1', '2'))
        row = project_dimension(dimension, units=units, attachments=attachments,
                                group=dimension['GroupId'], connection_labels=CONNECTIONS,
                                font_name_attribute=False, physical_font_width=physical_font_width)
        set_attribute(row, 'Id', dimension._ordinal())
        for name in ('Enabled', 'Selected', 'PanelExclude'):
            set_attribute(row, name, field_value(dimension, name))
        set_attribute(row, 'NonSignal', non_signal_number(dimension, destination='dipxml', report=report))
        result.append(row)
    return result
