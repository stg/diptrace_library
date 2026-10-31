"""Placed PCB XML components from physical style plans and current references."""
from ....common.conversion import info, warn
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_font_output import project_size
from ....common.xml_footprint_vocabulary import HORZ, VERT
from ....common.xml_library_output import project_category
from ....common.xml_output import enum_text, field, numeric, point_attributes
from ...model import definitions, markings
from ...model.hierarchy import linkage_path
from ..errors import PcbError
from ..output_validation import check_tree, field_value
from .components import SHOW, ALIGN
from .pad_output import project_options
from .patterns import PCB_PATTERN_TYPES
from .placement_frame import in_xml_frame


def project_marking(source, target, *, prefix, units):
    for side in markings.SIDES:
        row = target.add(side)
        stem = prefix+'_'+side if prefix else side
        for name, labels in (('Show', SHOW), ('Align', ALIGN), ('Horz', HORZ), ('Vert', VERT)):
            set_attribute(row, name, enum_text(field_value(source, stem+name), labels,
                          negative=labels[-1] if name in ('Horz', 'Vert') else None))
        point_attributes(row, field_value(source, stem+'X'), field_value(source, stem+'Y'), units)
        set_attribute(row, 'Angle', field_value(source, stem+'Angle'))


def _connections(component, result, keys):
    def key(pad):
        if pad not in keys:
            raise PcbError(f'{component.path}: internal connection has no physical XML pad key')
        return keys[pad]
    pairs = component.select('IntConRecords/Item')
    if pairs:
        target = result.add('IntConRecords')
        for pair in pairs:
            row = target.add('Item')
            set_attribute(row, 'X', key(pair['Pad1']))
            set_attribute(row, 'Y', key(pair['Pad2']))
    groups = component.select('InternalConnections/IntCon')
    if groups:
        target = result.add('InternalConnections')
        for group in groups:
            members = group['Members']
            tree = group['Ratlines']
            if members is None or tree is None:
                raise PcbError(f'{group.path}: internal connection requires a current pad group')
            row = target.add('IntCon')
            set_attribute(row, 'ConnectAll', group['ConnectAll'])
            pads = row.add('PadId')
            for pad in members:
                field(pads, 'Item', key(pad))
            edges = row.add('Ratlines')
            for first, second in tree:
                line = edges.add('Ratline')
                set_attribute(line, 'X', key(first))
                set_attribute(line, 'Y', key(second))


@in_xml_frame
def project_component(component, *, style, units, report=None):
    """Project a placement; its style owns the complete current physical data."""
    check_tree(component, definitions.COMPONENT, destination='DIPXML')
    if not field_value(component, 'Enabled'):
        raise PcbError(f'{component.path}: inactive component needs output normalization')
    pattern = component.one('Pattern')
    if field_value(component, 'BaseName') != pattern['Name']:
        if field_value(component, 'BaseName'):
            warn(report, 'component-base-name', 'dipxml',
                 'XML cannot retain an independent component base name', (component,),
                 recoverability='the physical style name remains; the independent base name is omitted')
        else:
            info(report, 'component-base-name-default', 'dipxml',
                 'XML initializes an empty component base name from its physical style', (component,))
    if component['ConnectedLayer'] >= 0:
        warn(report, 'component-connected-layer', 'dipxml',
             'XML output omits the component\'s independent connected copper-layer selection', (component,),
             recoverability='pad geometry, placement side and routing layers remain; the separate selection is omitted')
    suppliers = component.child('Suppliers')
    if suppliers is not None and any(suppliers.get(name, None) not in (None, '', False)
                                     for name in suppliers.schema.fields):
        warn(report, 'placed-supplier-data', 'dipxml', 'XML omits independent placed supplier data', (suppliers,))
    if suppliers is not None and suppliers.select('Prices/Quote'):
        warn(report, 'placed-supplier-prices', 'dipxml', 'XML omits placed supplier price breaks', (suppliers,))
    result = Element('Component')
    if style.name is not None:
        set_attribute(result, 'PatternStyle', style.name)
    elif pattern['Type'] != 16 or component['ViaStyle'] < 0:
        raise PcbError(f'{pattern.path}: implicit physical data requires a selected static-via style')
    for name, value in (('Id', component['Number']), ('UpdateId', field_value(component, 'HiddenId')),
                        ('Type', enum_text(pattern['Type'], PCB_PATTERN_TYPES)),
                        ('Angle', field_value(component, 'Angle')), ('Side', 'Bottom' if field_value(component, 'BottomSide') else 'Top'),
                        ('Flip', field_value(component, 'Flipped')), ('HorzFlip', field_value(component, 'HorizontalFlip')),
                        ('GridAlign', enum_text(field_value(component, 'GsType'), ('Pad', 'Origin'))),
                        ('ShowFiducials', enum_text(field_value(component, 'ShowFiducial'), SHOW))):
        set_attribute(result, name, value)
    point_attributes(result, component['X'], component['Y'], units)
    for name in ('Selected', 'Locked', 'PanelExclude', 'CustomMarkingFont', 'MarkingFontAll'):
        set_attribute(result, name, field_value(component, name))
    project_size(component, result, size='MarkingFontSize', legacy='MarkingFontSize',
                 floating='MarkingFontSizeFloat', mono=None)
    for name, value in (('Group', component['GroupId']), ('ShieldGroup', field_value(component, 'ShieldGroup')),
                        ('ViaStyle', component['ViaStyle'])):
        if value >= 0:
            set_attribute(result, name, value)
    if field_value(component, 'PlacementClearance') >= 0:
        set_attribute(result, 'PlacementClearance', numeric(units.length(field_value(component, 'PlacementClearance'))))
    for name in ('Name', 'RefDes', 'Value', 'Manufacturer', 'Datasheet'):
        field(result, name, field_value(component, name))
    path = result.add('LibPath')
    field(path, 'Path', field_value(component, 'LibPath'))
    field(path, 'Var', field_value(component, 'LibPath_Variable'))
    if category := project_category(component):
        result.append(category)
    if path := linkage_path(component):
        target = result.add('HierarchyPath')
        for identifier in path:
            field(target, 'Item', identifier)
    for name in markings.NAMES:
        project_marking(component, result.add(name+'Marking'), prefix=name, units=units)
    users = component.select('UserFields/UserField')
    if users:
        target = result.add('AddFields')
        for user in users:
            row = target.add('AddField')
            set_attribute(row, 'Type', enum_text(user['Type'], ('Text', 'Link')))
            field(row, 'Name', user['Name'])
            field(row, 'Text', user['Value'])
            project_marking(user, row, prefix='', units=units)
    pads = result.add('Pads')
    for pad in pattern.select('Pads/Pad'):
        if pad not in style.pad_keys:
            raise PcbError(f'{pad.path}: missing physical XML pad key')
        row = pads.add('Pad')
        set_attribute(row, 'Id', style.pad_keys[pad])
        set_attribute(row, 'NetId', -1 if pad['Net'] is None else pad['Net']['Number'])
        set_attribute(row, 'InternalConnection', pad['InternalConnection'])
        project_options(pad, row, units=units, via=pattern['Type'] == 16, report=report)
    _connections(component, result, style.pad_keys)
    excluded = component.select('AssemblyExclude/Item')
    if excluded:
        target = result.add('AssemblyExclude')
        for member in excluded:
            field(target, 'Item', member['Index'])
    return result


def project_components(board, *, library, units, report=None):
    result = Element('Components')
    for component in board.select('Components/Component'):
        pattern = component.one('Pattern')
        if pattern not in library.physical_styles:
            raise PcbError(f'{pattern.path}: include placed physical data in the XML library plan')
        result.append(project_component(component, style=library.physical_styles[pattern], units=units, report=report))
    return result
