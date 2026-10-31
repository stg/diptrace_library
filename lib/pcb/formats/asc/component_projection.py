"""Detached placed PCB components and their owned physical footprint content."""
from ....common.conversion import info, warn
from ....common.library_metadata import CLASSIFICATIONS, CATEGORY_TYPE, POSSIBLE_NAMES, POSSIBLE_NAME
from ....common.model import Element, Value
from ....common.footprint_records import PASTE_SEGMENTS, PASTE_SEGMENT
from ....common.supplier_records import SUPPLIERS, PRICES, QUOTE
from ...model import definitions as model, hierarchy_records, internal_connections, connection_policies
from ...model import assembly_variants, markings
from ...model.hierarchy import linkage_path
from ..errors import PcbError
from ..output_indices import pad_number
from .projection import check, collection, fields, flag, rows, value
from .footprint_projection import (points, project_pads, project_drawings, project_holes,
                                   project_dimensions, project_model, project_terminals)


def _classifications(owner, name, output):
    records = collection(owner, name, CLASSIFICATIONS, CATEGORY_TYPE)
    projected = output.add(name, len(records))
    for record in records:
        projected.add('Component_Type' if name.startswith('Component') else 'Pattern_Type', *record.arguments)


def _suppliers(component, output, report):
    source = component.child('Suppliers')
    if source is None:
        return
    check(source, SUPPLIERS)
    target = output.add('Suppliers')
    fields(source, target, exclude=('SourceLocator',))
    prices = collection(source, 'Prices', PRICES, QUOTE)
    if value(source, 'SourceLocator') or prices:
        warn(report, 'supplier-details', 'asc', 'ASC omits supplier source locators and price breaks', [source],
             recoverability='supplier identity and currency remain; source locator and ordered prices are omitted')


def _user_fields(component, output):
    target = output.add('UserFields')
    for source in collection(component, 'UserFields', markings.USER_FIELDS, markings.USER_FIELD):
        row = target.add('UserField', *source.arguments)
        fields(source, row, exclude=source.schema.parameters)


def _connections(component, output):
    target = output.add('InternalConnection_Records')
    for pair in collection(component, 'IntConRecords', internal_connections.DEFINITIONS, internal_connections.PAIR):
        target.add('pt', pad_number(pair['Pad1']), pad_number(pair['Pad2']))
    target = output.add('InternalConnections')
    for source in collection(component, 'InternalConnections', connection_policies.POLICIES, connection_policies.POLICY):
        members, tree = source['Members'], source['Ratlines']
        if members is None or tree is None:
            raise PcbError(f'{source.path}: internal connection policy requires a current pad group')
        row = target.add('IntCon')
        row.add('ConnectAll', flag(value(source, 'ConnectAll')))
        pads = row.add('PadNum')
        for pad in members:
            pads.add('pt', pad_number(pad))
        edges = row.add('Line')
        for first, second in tree:
            edges.add('pt', pad_number(first), pad_number(second))


def project_hierarchy_path(component):
    """Serialize the complete current schematic identity chain, including its terminal."""
    collection(component, 'HierarchyPath', hierarchy_records.PATH, hierarchy_records.PATH_ITEM)
    path = linkage_path(component)
    output = Element('Hidden_Path', len(path))
    for identifier in path:
        output.add('pt', identifier)
    return output


def project_component(component, *, report=None):
    """Return full component syntax, generating boundary rows and saved selectors."""
    check(component, model.COMPONENT)
    pattern = component.one('Pattern')
    check(pattern, model.PATTERN)
    output = Element('Component', component['Name'])
    if component['RefDes']:
        output.set_values(*output.arguments, Value(component['RefDes'], 'symbol'))
    fields(component, output, exclude=('Name', 'RefDes', 'ShieldGroup'))
    if value(component, 'ShieldGroup') != -1:
        warn(report, 'component-shield-group', 'asc', 'ASC omits component shield-group membership', (component,))
    for name in ('Number', 'ConnectedLayer', 'ViaStyle'):
        output.add(name, component[name])
    output.add('Group', component['GroupId'])
    output.add('Pattern', pattern['Name'])
    fields(pattern, output, exclude=('Name', 'Datasheet', 'RefDes', 'Sided', 'Pattern_Manufacturer'))
    for name in ('Datasheet', 'RefDes', 'Sided', 'Pattern_Manufacturer'):
        if pattern.child(name) is not None and value(pattern, name):
            warn(report, 'placed-pattern-metadata', 'asc', 'ASC omits independent placed-pattern '+name, [pattern],
                 recoverability='component metadata and footprint geometry remain; the independent pattern default is omitted')
    defaults = [name for name in ('Datasheet', 'RefDes', 'Sided', 'Pattern_Manufacturer')
                if pattern.child(name) is not None and not value(pattern, name)]
    if defaults:
        info(report, 'placed-pattern-default-metadata', 'asc',
             'ASC omits empty/default placed-pattern '+', '.join(defaults), [pattern])
    for name in ('PadPoints', 'PadMask_TopSegments', 'PadMask_BotSegments'):
        if (source := pattern.child(name)) is not None:
            if name == 'PadPoints':
                output.append(points(source, row_kind='Type'))
            else:
                output.append(points(source, schema=PASTE_SEGMENTS, member=PASTE_SEGMENT))
    output.append(project_terminals(pattern))
    output.append(project_pads(pattern, report=report))
    output.append(project_drawings(pattern, report=report))
    output.append(project_holes(pattern))
    output.append(project_dimensions(pattern, report=report))
    output.append(project_model(pattern.one('Model3D')))
    names = output.add('PossibleNames')
    for source in collection(pattern, 'PossibleNames', POSSIBLE_NAMES, POSSIBLE_NAME):
        names.add('PossibleName', source['Name'])
    _classifications(component, 'Component_CategoryTypes', output)
    _classifications(pattern, 'Pattern_CategoryTypes', output)
    _suppliers(component, output, report)
    _user_fields(component, output)
    output.append(project_hierarchy_path(component))
    excluded = collection(component, 'AssemblyExclude', assembly_variants.EXCLUSIONS, assembly_variants.MEMBER)
    target = output.add('AssemblyExclude', len(excluded))
    for source in excluded:
        target.add('pt', source['Index'])
    _connections(component, output)
    return output


def project_components(board, *, report=None):
    output = Element('Components')
    for component in collection(board, 'Components', model.COLLECTIONS['Components'], model.COMPONENT):
        output.append(project_component(component, report=report))
    return output
