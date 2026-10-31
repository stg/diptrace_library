"""Core PCB authoring records, extending shared physical footprint definitions."""
from dataclasses import replace

from ...common.schema import Child, Field, Record, MISSING
from ...common import footprint_records as footprint
from ...common.units import DISPLAY_UNITS
from ...common.library_metadata import definition as metadata_definition
from ...common.local_keys import definition as local_key_definition
from .membership import get_net, set_net, net_number, net_dependencies, net_ordinal, MEMBER
from . import routing_records, board_rules
from .relationships import reference_field, index_field
from . import graphic_records, pad_records, internal_connections, hierarchy_records
from . import connection_policies
from . import settings_records, markings, board_records
from . import library_records
from .library_relations import DRAWING_PAD_FIELDS
from . import table_records
from . import title_records, length_matching
from . import ratlines, drc_results, teardrops
from . import assembly_variants


def _fields(kind, names, *, default=MISSING):
    return {name: Field(name, kind, default=default) for name in names.split()}


PAD = replace(footprint.PAD, name='PcbPad', fields={
    **{name: field for name, field in footprint.PAD.fields.items() if name != 'Number_New'},
    **{name: replace(footprint.PAD.fields[name], nullable=True,
                    description='Main copper dimension; None means unavailable geometry.')
       for name in ('PadWidth_New', 'PadHeight_New')},
    'Net': Field('Net', 'reference', nullable=True, getter=get_net, setter=set_net,
                 reference_dependencies=net_dependencies,
                 description='Assigned PCB net identity; None disconnects the pad.'),
    'NetNumber': Field('NetNumber', 'integer', getter=net_number,
                       reference_dependencies=net_dependencies, ordinal_dependencies=net_ordinal,
                       description='Calculated net position; edit Net instead.'),
    'InternalConnection': connection_policies.PAD_GROUP,
    'ShieldGroup': Field('ShieldGroup', 'integer', default=-1),
    'SignalDelay': Field('SignalDelay', 'number', default=0),
}, children={**footprint.PAD.children,
    'HideLayer': Child('HideLayer', 'HiddenPadLayers'),
    'BlindLayer': Child('BlindLayer', 'BlindPadLayers'),
    'CustomSpokes': Child('CustomSpokes', 'PadThermals'),
    'TeardropParams': Child('TeardropParams', 'TeardropParameters'),
})
PATTERN_SHAPE = replace(footprint.PATTERN_SHAPE, name='PcbPatternDrawing', fields={
    **footprint.PATTERN_SHAPE.fields,
    **DRAWING_PAD_FIELDS,
    'MarkingGenerated': Field('MarkingGenerated', 'boolean', default=False),
    'ShieldGroup': Field('ShieldGroup', 'integer', default=-1),
})
PATTERN = replace(footprint.PATTERN, name='PcbPattern', fields={
    **footprint.PATTERN.fields,
    'Pattern_Manufacturer': Field('Pattern_Manufacturer', 'text'),
}, children={
    **{name: child for name, child in footprint.PATTERN.children.items()
       if name not in ('InternalConnections', 'UserFields', 'Pattern_Groups')},
    'Pads': Child('Pads', 'PcbPads'), 'Shapes': Child('Shapes', 'PcbPatternDrawings'),
    'Holes': Child('Holes', 'PcbHoles'), 'Dimensions': Child('Dimensions', 'PcbPatternDimensions'),
})

_PLACED_COLLECTION_OWNERS = {
    'InternalConnections': 'Component.IntConRecords',
    'UserFields': 'Component.UserFields',
    'Pattern_Groups': 'the cached pattern definition',
}

COMPONENT = Record('PcbComponent', {
    **markings.COMPONENT_FIELDS,
    **_fields('text', 'Name RefDes Value BaseName LibPath LibPath_Variable Manufacturer Datasheet', default=''),
    **_fields('boolean', 'Selected Locked PanelExclude BottomSide Flipped HorizontalFlip '
                        'CustomMarkingFont MarkingFontAll', default=False),
    **_fields('integer', 'HiddenId GsType ShowFiducial', default=0),
    'ShieldGroup': Field('ShieldGroup', 'integer', default=-1),
    **graphic_records.GROUP_FIELDS,
    'Layer': reference_field('Layer', 'copper-layer'),
    'ConnectedLayer': index_field('ConnectedLayer', 'copper-layer'),
    **board_rules.VIA_FIELDS,
    'Enabled': Field('Enabled', 'boolean', required=True, default=True),
    **{name: Field(name, 'number', required=True, default=0, unit='shared length')
       for name in ('X', 'Y')},
    'Angle': Field('Angle', 'number', required=True, default=0, unit='radians'),
    'PlacementClearance': Field('PlacementClearance', 'number', default=-1, unit='shared length'),
    'MarkingFontSize': Field('MarkingFontSize', 'number', default=5),
    'Component_CategoryName': Field('Component_CategoryName', 'text', default=''),
    'Component_CategoryIndex': Field('Component_CategoryIndex', 'integer', default=-1),
    'Number': Field('Number', 'integer', getter=lambda component: component._ordinal(),
                    ordinal_dependencies=lambda component: (component,)),
}, parameters=('Name', 'RefDes'), children={
    'Pattern': Child('Pattern', 'PcbPattern', minimum=1),
    'Suppliers': Child('Suppliers', 'Suppliers'),
    'AssemblyExclude': Child('AssemblyExclude', assembly_variants.EXCLUSIONS.name),
    'UserFields': Child('UserFields', markings.USER_FIELDS.name),
    'IntConRecords': Child('IntConRecords', internal_connections.DEFINITIONS.name),
    'HierarchyPath': Child('HierarchyPath', hierarchy_records.PATH.name),
    'InternalConnections': Child('InternalConnections', connection_policies.POLICIES.name),
    'Component_CategoryTypes': Child('Component_CategoryTypes', 'Classifications'),
})
NET = Record('PcbNet', {
    **board_rules.CLASS_FIELDS,
    'Name': Field('Name', 'text', required=True, default=''),
    'Enabled': Field('Enabled', 'boolean', required=True, default=True),
    **_fields('boolean', 'Locked HideRatlines ShowLength CustomColor AllowLoops Highlighted', default=False),
    'HiddenId': Field('HiddenId', 'integer', default=-1),
    **_fields('integer', 'RouteMode TraceColor', default=0),
    **_fields('integer', 'ActiveLine ActivePoint', default=-1),
    **_fields('number', 'Width Clearance MeanderGap', default=-1),
    'Number': Field('Number', 'integer', getter=lambda net: net._ordinal(),
                    ordinal_dependencies=lambda net: (net,)),
}, parameters=('Name',), children={
    'Pads': Child('Pads', 'PcbNetMembers', minimum=1),
    'Traces': Child('Traces', 'PcbTraces', minimum=1),
    'TeardropParams': Child('TeardropParams', pad_records.TEARDROP.name),
    'Teardrops': Child('Teardrops', teardrops.TEARDROPS.name),
})


def _collection(name, kind, record):
    return Record(name, {}, children={kind: Child(kind, record, maximum=None)})


COLLECTIONS = {
    'Components': _collection('PcbComponents', 'Component', 'PcbComponent'),
    'Nets': _collection('PcbNets', 'Net', 'PcbNet'),
    'ComponentPads': _collection('PcbPads', 'Pad', 'PcbPad'),
    'NetPads': _collection('PcbNetMembers', 'Item', 'PcbNetMember'),
    'PatternShapes': _collection('PcbPatternDrawings', 'Shape', 'PcbPatternDrawing'),
}
BOARD = Record('Board', {**board_records.BOARD_FIELDS,
                       'Enabled': Field('Enabled', 'boolean', default=True),
                       'Selected': Field('Selected', 'boolean', default=False),
                       'ShieldGroup': Field('ShieldGroup', 'integer', default=-1),
                       'LayerStackName': Field('LayerStackName', 'text', default=''),
                       'ClassToClass': Field('ClassToClass', 'boolean', default=False),
                       'DefaultClass': reference_field('DefaultClass', 'default-net-class')}, children={
    'AssemblyVariants': Child('AssemblyVariants', assembly_variants.VARIANTS.name),
    'Layers': Child('Layers', 'PcbCopperLayers'),
    'Ratlines': Child('Ratlines', ratlines.RATLINES.name),
    'DesignErrors': Child('DesignErrors', drc_results.ERRORS.name),
    'ViaStyles': Child('ViaStyles', 'PcbViaStyles'),
    'NetClasses': Child('NetClasses', 'PcbNetClasses'),
    'LayerStackItems': Child('LayerStackItems', 'PcbLayerStackItems'),
    'ClassClearances': Child('ClassClearances', 'PcbClassClearances'),
    'DRC': Child('DRC', 'PcbDesignRules'),
    'LastDRC': Child('LastDRC', 'PcbDesignRules'),
    'MainLengthRule': Child('MainLengthRule', length_matching.POLICY.name),
    'LengthRules': Child('LengthRules', length_matching.POLICIES.name),
    **{name: Child(name, schema.name) for name, schema in graphic_records.COLLECTIONS.items()
       if name != 'Holes'},
    'Components': Child('Components', 'PcbComponents', minimum=1),
    'Nets': Child('Nets', 'PcbNets', minimum=1),
    'DifferentialPairs': Child('DifferentialPairs', 'PcbDifferentialPairs'),
    'RemovedDifferentialPairs': Child('RemovedDifferentialPairs', 'PcbRemovedDifferentialPairs'),
    'HierarchySheets': Child('HierarchySheets', hierarchy_records.SHEETS.name),
    'Settings': Child('Settings', settings_records.SETTINGS.name),
    'SheetSettings': Child('SheetSettings', settings_records.SHEET.name),
    'Panel': Child('Panel', board_records.PANEL.name),
    'ConnectivityCheck': Child('ConnectivityCheck', settings_records.CONNECTIVITY.name),
    'CacheLib': Child('CacheLib', library_records.CACHE.name),
    'ProjectLibs_Folders': Child('ProjectLibs_Folders', 'ProjectFolders'),
    'ProjectLibs_Libs': Child('ProjectLibs_Libs', 'ProjectLibraries'),
    'DesignCache_Links': Child('DesignCache_Links', library_records.DESIGN_LINKS.name),
    'Userfields_Global': Child('Userfields_Global', markings.GLOBAL_USER_FIELDS.name),
})
DOCUMENT = Record('PcbDocument', {
    'Units': Field('Units', 'text', required=True, default='mm', choices=DISPLAY_UNITS,
                   description='Display units; stored coordinates remain in shared length units.'),
    'Scale': Field('Scale', 'number', default=100, unit='%'),
    'Xpos': Field('Xpos', 'number', default=0, unit='shared length'),
    'Ypos': Field('Ypos', 'number', default=0, unit='shared length'),
}, children={'Board': Child('Board', 'Board', minimum=1)})


def definition(node):
    if (variant := assembly_variants.definition(node)) is not None:
        return variant
    if (polygon := teardrops.definition(node)) is not None:
        return polygon
    if (error := drc_results.definition(node)) is not None:
        return error
    if (ratline := ratlines.definition(node)) is not None:
        return ratline
    if (length := length_matching.definition(node)) is not None:
        return length
    if (title := title_records.definition(node)) is not None:
        return title
    if (global_marking := markings.global_definition(node)) is not None:
        return global_marking
    if (table := table_records.definition(node)) is not None:
        return table
    if (shared := footprint.nested_definition(node)) is not None:
        return shared
    if (metadata := metadata_definition(node)) is not None:
        return metadata
    if (local_key := local_key_definition(node)) is not None:
        return local_key
    if library_records.contains(node):
        return library_records.definition(node)
    if (settings := settings_records.definition(node)) is not None:
        return settings
    if (board_record := board_records.definition(node)) is not None:
        return board_record
    if (policy := connection_policies.definition(node)) is not None:
        return policy
    if (hierarchy := hierarchy_records.definition(node)) is not None:
        return hierarchy
    if (connection := internal_connections.definition(node)) is not None:
        return connection
    if (pad := pad_records.definition(node)) is not None:
        return pad
    if (graphic := graphic_records.definition(node)) is not None:
        return graphic
    rule = board_rules.definition(node)
    if rule is not None:
        return rule
    routing = routing_records.definition(node)
    if routing is not None:
        return routing
    parent = node.parent
    owner = parent.parent if parent is not None else None
    if parent is None and not node.kind:
        return DOCUMENT
    if node.kind == 'Board' and parent is not None and not parent.kind:
        return BOARD
    if parent is None:
        return None
    if parent.kind == 'Board':
        return COLLECTIONS.get(node.kind)
    if node.kind == 'Component' and parent.kind == 'Components':
        return COMPONENT
    if node.kind == 'Net' and parent.kind == 'Nets':
        return NET
    if node.kind == 'Pattern' and parent.kind == 'Component':
        return PATTERN
    if node.kind == 'UserFields' and parent.kind == 'Component':
        return markings.USER_FIELDS
    if (node.kind == 'UserField' and parent.kind == 'UserFields' and
            owner is not None and owner.kind == 'Component'):
        return markings.USER_FIELD
    if node.kind == 'Pads' and parent.kind in ('Pattern', 'Net'):
        return COLLECTIONS['ComponentPads' if parent.kind == 'Pattern' else 'NetPads']
    if node.kind == 'Shapes' and parent.kind == 'Pattern':
        return COLLECTIONS['PatternShapes']
    if node.kind == 'Pad' and parent.kind == 'Pads' and owner is not None and owner.kind == 'Pattern':
        return PAD
    if node.kind == 'Shape' and parent.kind == 'Shapes' and owner is not None and owner.kind == 'Pattern':
        return PATTERN_SHAPE
    if node.kind == 'Item' and parent.kind == 'Pads' and owner is not None and owner.kind == 'Net':
        return MEMBER
    return None


def establish_records(root):
    for node in root.walk(include_self=True):
        schema = definition(node)
        if schema is not None:
            if schema is PATTERN:
                # Shared constructors include template collections. A placement
                # owns geometry; its component owns current fields and pairs,
                # while reusable group definitions stay with the cached pattern.
                for name, owner in _PLACED_COLLECTION_OWNERS.items():
                    if (collection := node.child(name)) is not None:
                        if collection.arguments or collection.children():
                            raise ValueError(f'{collection.path}: placed {name} belongs to {owner}')
                        collection.detach()
            node.bind_schema(schema)
