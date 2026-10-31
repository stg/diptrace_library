"""Project current physical definitions into PCB XML library records."""
from dataclasses import dataclass

from ....common.conversion import info, warn
from ....common.key_allocation import allocate_keys
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_catalog import StyleTable
from ....common.xml_footprint_output import project_model3d, project_drawing, project_dimension
from ....common.xml_library_output import project_category
from ....common.xml_output import enum_text, field, numeric, point_attributes
from ....common.xml_pad_output import project_pad_style
from ....common.xml_footprint_vocabulary import PATTERN_TYPES
from ...model.definitions import PATTERN
from ...model import library_records
from ..errors import PcbError
from ..output_validation import check_tree
from ..local_group_projection import reserved, selection
from .patterns import PCB_PATTERN_TYPES
from .placement_frame import in_xml_frame
from .dimension_attachments import marking_endpoint


@dataclass(frozen=True)
class PatternProjection:
    """Physical XML plus keys/pairs for the enclosing component-library writer."""
    element: Element
    styles: Element
    pad_keys: dict
    connections: tuple
    shape_keys: dict
    hole_keys: dict


def _physical_type(pattern, report):
    """Library geometry and placed PCB objects use different type labels."""
    kind = pattern['Type']
    label = enum_text(kind, PCB_PATTERN_TYPES)
    if kind < len(PATTERN_TYPES):
        return label
    placed = pattern.parent is not None and pattern.parent.kind == 'Component'
    if placed:
        info(report, 'xml-physical-pattern-type', 'dipxml',
             'Represented standalone geometry as a Free library pattern; the placement retains its PCB type.',
             (pattern,), recoverability='the component Type retains the object classification')
    else:
        warn(report, 'xml-physical-pattern-type', 'dipxml',
             'An unplaced XML library pattern cannot retain its PCB-only object type.',
             (pattern,), recoverability='physical data and explicit lock settings remain; the library type becomes Free')
    return PATTERN_TYPES[0]


class _Keys:
    def __init__(self, pattern, *, report=None):
        self.report = report
        self.members = {name: tuple(pattern.select(path)) for name,path in (
            ('Pads','Pads/Pad'),('Shapes','Shapes/Shape'),('Holes','Holes/Hole'),
            ('Groups','Pattern_Groups/pt'))}
        self.generated = frozenset(shape for shape in self.members['Shapes']
                                   if shape['Type'] == 7 and shape.get('MarkingGenerated', False))
        self.placement_groups = None
        if pattern.parent is not None and pattern.parent.kind == 'Component' and not self.members['Groups']:
            # Placements supply memberships, rather than template group objects.
            # Build the XML namespace from the exported members alone. Sorting
            # the distinct keys avoids allocating an array up to a sparse Id.
            grouped = {}
            objects = (*self.members['Pads'], *self.members['Shapes'], *self.members['Holes'],
                       *pattern.select('Dimensions/Dimension'))
            for member in objects:
                if member not in self.generated and (number := member['Group']) >= 0:
                    grouped.setdefault(number, []).append(member)
            self.placement_groups = {number: index for index, number in enumerate(
                sorted(number for number, members in grouped.items() if len(members) > 1))}
            normalized = [member for number, members in grouped.items()
                          if self.placement_groups.get(number, -1) != number for member in members]
            if normalized:
                info(report, 'placement-group-normalization', 'dipxml',
                     'XML numbers placed footprint groups consecutively and omits single-member groups.', normalized,
                     recoverability='shared membership and physical geometry remain; the source model is unchanged')
        self.values = {name: allocate_keys(tuple(row for row in rows if row not in self.generated),
                                          declared='Id' if name == 'Pads' else None,
                                          start=0 if name == 'Groups' else 1,
                                          reserved=reserved(pattern) if name == 'Groups' else ())
                       for name,rows in self.members.items()}

    def member(self, collection, number):
        rows = self.members[collection]
        if not 1 <= number <= len(rows):
            raise PcbError(f'unavailable {collection} selector {number} needs an XML mapping')
        return rows[number-1]

    def at(self, collection, number):
        return self.values[collection][self.member(collection, number)]

    def group(self, node):
        if node.child('UnresolvedGroupId') is not None:
            return selection(node, destination='dipxml', report=self.report)
        selected = node['Group']
        if node.schema.fields['Group'].kind == 'reference':
            if selected is None:
                return -1
            return self.values['Groups'][selected]
        if selected < 0:
            return -1
        if self.placement_groups is not None:
            return self.placement_groups.get(selected, -1)
        matches = [group for group in self.members['Groups'] if group['Id'] == selected]
        if len(matches) > 1:
            raise PcbError(f'{node.path}: unavailable local group {selected}')
        if not matches:
            warn(self.report, 'unresolved-footprint-group', 'dipxml',
                 'XML output omits a footprint group selection with no current target', (node,),
                 recoverability='object geometry remains; the unavailable group selection is omitted')
            return -1
        return self.values['Groups'][matches[0]]

    def attachments(self, dimension):
        result = []
        for side in ('1','2'):
            mode = dimension['Connected'+side]
            member = dimension['SubObject'+side]
            if mode in (0,1,2):
                collection = ('Pads','Shapes','Holes')[mode]
                target = self.member(collection, member)
                if mode == 1 and (adapted := marking_endpoint(dimension, side, target, report=self.report)) is not None:
                    result.append(adapted)
                    continue
                member = self.values[collection][target]
            result.append((mode,dimension['Object'+side],member,dimension['Point'+side]))
        return tuple(result)


def _unavailable(node):
    if node.child('UnresolvedKeys') is not None:
        raise PcbError(f'{node.path}: unresolved public keys need a PCB XML output mapping')
    document = node._owner()
    if document is not None and any(document.references.unresolved_slot(node.one(name+side))
            for side in ('1','2') for name in ('Object','SubObject','Point')
            if node.child(name+side) is not None):
        raise PcbError(f'{node.path}: unresolved attachment needs a PCB XML output mapping')


@in_xml_frame
def project_pattern(pattern, *, style, units, explicit_pad_style=True,
                    physical_font_width=True, report=None):
    """Create a physical library view; return pad pairs for its owning Part.

    Component electrical assignments and placement overrides are separate output
    sections. This helper does not claim to export an entire PCB document.
    """
    schema = library_records.PATTERN if library_records.is_pattern(pattern) else PATTERN
    check_tree(pattern,schema,destination='DIPXML')
    keys = _Keys(pattern, report=report)
    for node in pattern.walk(include_self=True):
        _unavailable(node)
    result, styles = Element('Pattern'),StyleTable('PadStyles','PadStyle','Name','Pad')
    set_attribute(result,'PatternStyle',style)
    set_attribute(result,'Type',_physical_type(pattern, report))
    set_attribute(result,'Mounting',enum_text(pattern['Mounting'],('Through','SMD','Chassis','Mixed'),negative='None'))
    orientation = pattern['PatternOrientation']
    set_attribute(result,'Orientation',orientation*90 if orientation in (0,1,2,3) else orientation)
    set_attribute(result,'LockTypeChange',pattern['LockProperties'])
    for name in ('Width','Height'):
        set_attribute(result,name,numeric(units.length(pattern.one(name).arguments[0])))
    for index in (1,2,3):
        set_attribute(result,'Float'+str(index),numeric(units.length(pattern.one('Spacing'+str(index)).arguments[0])))
    for index in (1,2):
        set_attribute(result,'Int'+str(index),pattern['Number'+str(index)])
    field(result,'Name',pattern['Name'])
    if pattern.get('RefDes',''):
        set_attribute(result,'RefDes',pattern['RefDes'])
    for public, own in (('Value','Value'),('Name_Description','Name_Description'),('Name_Unique','Name_Unique'),
                        ('Datasheet','Datasheet'),('Manufacturer','Pattern_Manufacturer')):
        if pattern.get(own,''):
            field(result,public,pattern[own])
    if category := project_category(pattern):
        result.append(category)
    names = pattern.select('PossibleNames/PossibleName')
    if names:
        target = result.add('PossibleNames')
        for name in names:
            field(target,'PossibleName',name['Name'])
    origin = result.add('Origin')
    point_attributes(origin,pattern['OriginX'],pattern['OriginY'],units)
    for public, own in (('Cross','OriginCross'),('Circle','OriginCircle')):
        set_attribute(origin,public,pattern[own])
    set_attribute(origin,'Common',enum_text(pattern['OriginCommon'],('Show','Hide')))
    set_attribute(origin,'Courtyard',enum_text(pattern['OriginCourtyard'],('Show','Hide','Show if not center')))
    if pattern['RecoveryCode']:
        target = field(result,'RecoveryCode',pattern['RecoveryCode'])
        for name in ('Generator','Model'):
            set_attribute(target,name,pattern['RecoveryCode_'+name])
    _groups(pattern,result,keys,units,report)
    users = pattern.select('UserFields/UserField')
    if users:
        target = result.add('AddFields')
        for user in users:
            row = target.add('AddField')
            set_attribute(row,'Type',enum_text(user['Type'],('Text','Link')))
            field(row,'Name',user['Name'])
            field(row,'Text',user['Value'])
    default = styles.include(project_pad_style(pattern,name='',units=units))
    set_attribute(result.add('DefPad'),'Style',default)
    pads = result.add('Pads')
    for pad in keys.members['Pads']:
        row = pads.add('Pad')
        set_attribute(row,'Id',keys.values['Pads'][pad])
        # Earlier XML infers inheritance from style identity. A distinct style
        # must remain distinct even when its current geometry equals the default.
        excluded = (default,) if not explicit_pad_style and not pad['Standard'] else ()
        set_attribute(row,'Style',styles.include(project_pad_style(pad,name='',units=units), exclude=excluded))
        for name,current in (('DefStyle',pad['Standard']),('Angle',pad['PadAngle']),
                             ('Locked',pad['Locked']),('Side','Bottom' if pad['Sided'] else 'Top')):
            set_attribute(row,name,current)
        point_attributes(row,pad['X'],pad['Y'],units)
        group = keys.group(pad)
        if group >= 0:
            set_attribute(row,'Group',group)
        field(row,'Number',pad['StringNumber'])
        if pad['Name']:
            field(row,'Note',pad['Name'])
    shapes = result.add('Shapes')
    if keys.generated:
        info(report, 'generated-marking-geometry', 'dipxml', 'XML omits calculated component marking drawings',
             tuple(shape for shape in keys.members['Shapes'] if shape in keys.generated),
             recoverability='component marking settings remain; a receiving editor can regenerate their display geometry')
    for shape in keys.members['Shapes']:
        if shape in keys.generated:
            continue
        if shape['Type'] <= 0:
            raise PcbError(f'{shape.path}: inactive drawing needs output normalization')
        if shape.get('MarkingGenerated', False):
            info(report, 'non-text-marking-flag', 'dipxml', 'XML omits an inapplicable non-text marking flag', (shape,))
        pad_id = shape.get('PadId',-1)
        row = project_drawing(shape,index=keys.values['Shapes'][shape],units=units,group=keys.group(shape),
                              pad_id=keys.at('Pads',pad_id) if pad_id >= 0 else -1,
                              physical_font_width=physical_font_width)
        shapes.append(row)
        if shape.get('ShieldGroup',-1) != -1:
            warn(report,'pattern-shield-group','dipxml','XML footprint styles omit drawing shield-group membership',(shape,))
    holes = result.add('Holes')
    for hole in keys.members['Holes']:
        if not hole['Enabled']:
            raise PcbError(f'{hole.path}: inactive hole needs output normalization')
        row = holes.add('Hole')
        set_attribute(row,'Id',keys.values['Holes'][hole])
        set_attribute(row,'Locked',hole['Locked'])
        point_attributes(row,hole['X'],hole['Y'],units)
        for name in ('Diam','HoleDiam'):
            set_attribute(row,name,numeric(units.length(hole[name])))
        if (group := keys.group(hole)) >= 0:
            set_attribute(row,'Group',group)
    dimensions = result.add('Dimensions')
    for dimension in pattern.select('Dimensions/Dimension'):
        if not dimension['Enabled']:
            raise PcbError(f'{dimension.path}: inactive dimension needs output normalization')
        dimensions.append(project_dimension(dimension,units=units,attachments=keys.attachments(dimension),
                                            group=keys.group(dimension), physical_font_width=physical_font_width))
    result.append(project_model3d(pattern.one('Model3D'),units=units,variable_fallback=False))
    omitted = [name for name in pattern.schema.fields if name.startswith('VariableParameter') and pattern[name]]
    if omitted:
        warn(report,'pattern-parameter-options','dipxml','XML omits footprint parameter-enable choices',(pattern,))
    pairs = []
    for pair in pattern.select('InternalConnections/IntCon'):
        if pair['Pad1'] is None or pair['Pad2'] is None:
            raise PcbError(f'{pair.path}: assign both internal-connection pads before export')
        pairs.append(tuple(keys.values['Pads'][pair[name]] for name in ('Pad1','Pad2')))
    return PatternProjection(result,styles.element,keys.values['Pads'],tuple(pairs),
                             keys.values['Shapes'],keys.values['Holes'])


def _groups(pattern, result, keys, units, report):
    if keys.placement_groups:
        target = result.add('Groups')
        for number in keys.placement_groups.values():
            row = target.add('Item')
            set_attribute(row, 'Number', number)
            point_attributes(row, 0, 0, units)
        return
    if not keys.members['Groups']:
        return
    target = result.add('Groups')
    inactive = []
    for group in keys.members['Groups']:
        if not group['Enabled']:
            inactive.append(group)
            continue
        row = target.add('Item')
        set_attribute(row,'Number',keys.values['Groups'][group])
        point_attributes(row,group['X'],group['Y'],units)
    if inactive:
        info(report, 'local-group-normalization', 'dipxml', 'XML omits inactive local groups', inactive,
             recoverability='active group identities and member geometry retained')
