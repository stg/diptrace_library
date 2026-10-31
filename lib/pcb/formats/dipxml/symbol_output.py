"""PCB library-symbol output resolves current pad and local-group identities."""
from ....common import xml_symbol_output
from ....common.conversion import info, warn
from ....common.supplier_conversion import report_supplier_omissions
from ....common.key_allocation import allocate_keys
from ....common.xml import set_attribute
from ...model import library_records
from ...model.library_relations import PIN_PAD_ROLE
from ..errors import PcbError
from ..output_validation import check_tree
from ..local_group_projection import reserved, selection
from ..symbol_pin_projection import number as pin_number


def _assignments(part):
    document = part._owner()
    if document is None:
        return {}
    return {reference.indices[0].field.parent: reference.target
            for reference in document.references.outgoing(part, role=PIN_PAD_ROLE)}


def project_symbol(part, *, units, pad_keys=None, pattern_style=None, connections=(),
                   physical_font_width=True, report=None):
    """Emit an unplaced symbol using physical keys supplied by its library plan.

    ``pad_keys`` maps actual pad identities to destination keys. Positional pin
    assignments are never interpreted as public keys, even after reordering.
    """
    check_tree(part, library_records.SYMBOL, destination='DIPXML')
    for node in part.walk(include_self=True):
        if node.kind == 'UnresolvedKeys':
            raise PcbError(f'{node.path}: unresolved symbol keys need a PCB XML mapping')
    inactive_groups = tuple(group for group in part.select('Groups/pt') if not group['Enabled'])
    groups = tuple(group for group in part.select('Groups/pt') if group['Enabled'])
    if inactive_groups:
        info(report, 'local-group-normalization', 'dipxml', 'XML omits inactive local groups', inactive_groups,
             recoverability='active group identities and member geometry retained')
    group_keys = allocate_keys(groups, declared=None, start=0, reserved=reserved(part))
    assignments, pad_keys = _assignments(part), {} if pad_keys is None else pad_keys

    def group_key(node):
        if node.child('UnresolvedGroupId') is not None:
            return selection(node, destination='dipxml', report=report)
        selected = node['Group']
        if selected is None:
            return -1
        if selected not in group_keys:
            raise PcbError(f'{node.path}: local group is outside this symbol')
        return group_keys[selected]

    pins, drawings, inactive = [], [], []
    for pin in part.select('Pins/Pin'):
        if not pin['Enabled']:
            inactive.append(pin)
            continue
        key = pin_number(pin, destination='dipxml', report=report)
        if part['PartType'] == 0 and key >= 0:
            target = assignments.get(pin)
            if target is None and not pad_keys:
                # Numbered symbol pins can exist before a physical definition
                # is assigned. Keep the number without inventing a pad target.
                pass
            elif target not in pad_keys:
                raise PcbError(f'{pin.path}: current pin assignment has no physical XML key')
            else:
                key = pad_keys[target]
        pins.append(xml_symbol_output.project_symbol_pin(pin, units=units, pad_id=key, group=group_key(pin),
                                                        physical_font_width=physical_font_width))
    for shape in part.select('Shapes/Shape'):
        if not shape['Enabled']:
            inactive.append(shape)
            continue
        drawings.append(xml_symbol_output.project_symbol_drawing(shape, units=units, group=group_key(shape),
                                                                physical_font_width=physical_font_width))
    if inactive:
        warn(report, 'inactive-library-records', 'dipxml', 'XML omits inactive symbol content', inactive)
    if not part['Enabled']:
        warn(report, 'inactive-library-state', 'dipxml', 'XML omits the symbol activation state', (part,))
    report_supplier_omissions((part,), destination='dipxml', report=report, omit_preference=True)
    result = xml_symbol_output.project_symbol(
        part, units=units, destination='dipxml', report=report, pins=pins, drawings=drawings,
        groups=((group_keys[group], group['X'], group['Y']) for group in groups),
        pattern_style=pattern_style, connections=connections)
    return result
