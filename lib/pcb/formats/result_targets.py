"""Detached check-result selectors shared by PCB output formats."""
from ...common.conversion import info, warn
from ..model import drc_results as model
from .errors import PcbError
from .output_validation import check_tree


def target(row, side, *, indices, destination, report, footprint_boundaries=False):
    kind = row['ObjectType'+side]
    if kind >= 0 and kind not in model.TARGET_TYPES:
        raise PcbError(f'{row.path}: design-check object domain {kind} mapping is not implemented')
    data = {name: row[name+side] for name in ('Object', 'SubObject', 'Point', 'ExtObject')}
    if (unavailable := row.child('UnresolvedTarget'+side)) is not None:
        check_tree(unavailable, model.UNRESOLVED, destination=destination.upper())
        if kind in model.PAUSED_TYPES:
            info(report, 'paused-design-error-targets', destination,
                 'Saved check target belongs to unavailable interactive routing geometry', (row,),
                 recoverability='the explicit unresolved selectors and supplied measurement remain')
        elif kind in model.PANEL_HOLE_TYPES:
            info(report, 'generated-panel-hole-targets', destination,
                 'Saved check target belongs to panel holes generated from the panel settings', (row,),
                 recoverability='the explicit selectors and supplied measurement remain; panel holes can be generated')
        else:
            warn(report, 'unresolved-design-error-targets', destination, 'Saved check target is unavailable', (row,),
                 recoverability='the explicit unresolved selectors and supplied measurement remain')
    else:
        selected = row['Target'+side]
        if selected is not None and kind == 18:
            data['Object'], data['SubObject'] = indices.length_position(selected)
        elif selected is not None and footprint_boundaries and kind in (*model.PAD_TYPES, *model.HOLE_TYPES):
            data['SubObject'] += 1
        elif selected is None and kind == 1:
            kind = -1
            info(report, 'detached-outline-check', destination,
                 'Encoded a detached outline check without an outline target', (row,))
    return kind, data


def net_class(row, side, *, indices, destination, report):
    if row.child('UnresolvedObjectNetClass'+side) is not None:
        warn(report, 'unresolved-design-error-class', destination, 'Saved check class is unavailable', (row,),
             recoverability='the explicit unresolved class index is retained')
        return row['ObjectNetClass'+side]
    return indices.class_number(row['NetClass'+side])


def layer_mask(row, *, copper, destination, report):
    selected = set()
    if (layers := row.child('Layers')) is not None:
        check_tree(layers, model.LAYERS, destination=destination.upper())
    for member in row.select('Layers/Layer'):
        index = member['Index']
        if index < 0:
            info(report, 'empty-design-error-layer', destination, 'Omitted an empty check-layer selection', (member,))
        elif index in selected:
            raise PcbError(f'{member.path}: duplicate check-layer selection')
        else:
            selected.add(index)
        if member.child('UnresolvedIndex') is not None:
            warn(report, 'unresolved-design-error-layer', destination, 'Saved check layer is unavailable', (member,),
                 recoverability='the explicit unresolved index remains in the output mask')
    return tuple(index in selected for index in range(max(len(copper), max(selected, default=-1)+1)))
