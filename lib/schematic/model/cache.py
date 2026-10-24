"""Owned library definitions synthesized from old schematic instance data."""
import math

from ...common.model import (Element)
from .local_keys import (copy_missing_keys)


def reference_prefix(reference):
    """format public library prefix: remove trailing ASCII digits and spaces."""
    return reference.rstrip('0123456789 ')


def _copy_fields(source,target,names):
    for name in names.split():
        target.append(source.one(name).clone())


def _unrotate_symbol(part,angle):
    from .angles import (quarter_turns)
    quarter=quarter_turns(angle)
    turns=(-quarter)%4
    def rotate(x,y):
        # Exact quarter turns avoid introducing artificial trigonometric noise
        # into the editable model. ASC rounding happens at output only.
        return ((x,y),(-y,x),(-x,-y),(y,-x))[quarter%4]
    if quarter%2:
        width,height=part.one('Width'),part.one('Height')
        a,b=width.arguments,height.arguments
        width.set_values(*b)
        height.set_values(*a)
    x,y=rotate(part.scalar('Origin_X'),part.scalar('Origin_Y'))
    part.set_field('Origin_X',x)
    part.set_field('Origin_Y',y)
    for pin in part.select('Pins/Pin'):
        if pin.scalar('Enabled') not in (True,'Y'):
            continue
        x,y=rotate(*pin.values[1:3])
        pin.set_values(pin.arguments[0],x,y)
        orientation=pin.scalar('Orientation')
        pin.set_field('Orientation',(orientation+quarter)%4)
    for shape in part.select('Shapes/Shape'):
        for point in shape.select('Points_New/pt'):
            point.set_values(*rotate(*point.values))
        points=shape.select('Points_New/pt')
        if turns and shape.scalar('Type') in (4,5,6,7) and len(points)==2:
            a,b=points[0].values,points[1].values
            points[0].set_values(min(a[0],b[0]),min(a[1],b[1]))
            points[1].set_values(max(a[0],b[0]),max(a[1],b[1]))
        shape.set_field('TextAngle',(float(shape.scalar('TextAngle'))+turns*math.pi/2)%math.tau)


def symbol_definition(component):
    """Create an unplaced symbol from current instance geometry and data."""
    part=Element('Part',component.values[0],reference_prefix(component.values[1]))
    _copy_fields(component,part,'''Enabled PartType PartName ShowNumbers Type Number1
        Number2 Width Height Value LockProperties Origin_X Origin_Y ModelType Datasheet
        ModelString ModelBody Manufacturer Component_CategoryName
        Component_CategoryIndex Component_CategoryTypes Suppliers''')
    part.add('SubfolderIndex',-1)
    part.add('Verification',*(False for _ in range(7)))
    part.add('ModelNote','')
    part.add('Groups')
    users=part.add('UserFields')
    for source in component.select('UserFields/UserField'):
        users.add('UserField',*source.arguments[:3],*(0 for _ in range(7)))
    pins=part.add('Pins')
    names='''Enabled Locked ModelSig Type Orientation Number Length Name StringNumber
        ShowName PinNumXShift PinNumYShift PinNameXShift PinNameYShift ElectricType
        NameFontSize NameFontWidth NameFontScale SignalDelay Group PinNameRotate PinNumRotate'''
    for source in component.select('Pins/Pin'):
        pin=pins.add('Pin',len(pins.children()),*source.arguments[1:3])
        _copy_fields(source,pin,names)
        copy_missing_keys(source, pin)
    shapes=part.add('Shapes')
    for source in component.select('Shapes/Shape'):
        if source.scalar('Enabled') not in (True,'Y') or source.scalar('MarkingGenerated') in (True,'Y'):
            continue
        shape=shapes.append(source.clone())
        shape.set_values(len(shapes.children())-1)
        shape.set_field('ShowPart',False)
        shape.set_field('MarkingGenerated',False)
    _unrotate_symbol(part,float(component.scalar('Angle')))
    return part


def _definition(component,index):
    definition=Element('Definition',index)
    part=definition.append(symbol_definition(component))
    from ..layout.geometry import (symbol_bounds)
    bounds=symbol_bounds(part)
    # A definition can have a zero-size axis; the placed selection minimum
    # belongs to the instance rather than its unplaced library geometry.
    part.set_field('Width',bounds.width if bounds else 0)
    part.set_field('Height',bounds.height if bounds else 0)
    # The historical DCH cache dialect has no symbol datasheet or pin-delay
    # slots. Keep the general symbol builder independent of that narrower view.
    part.one('Datasheet').detach()
    for pin in part.select('Pins/Pin'):
        pin.one('SignalDelay').detach()
    pattern=definition.append(component.one('Pattern').clone())
    for parent,kind in [('Pads','Pad'),('Shapes','Shape')]:
        records=pattern.one(parent).children(kind)
        for index,record in enumerate(records):
            record.annotations.pop('asc_omit',None)
            # The two footprint drawing boundary slots become empty records
            # when a placed footprint is copied into a definition.
            if parent=='Shapes' and index in (0,len(records)-1):
                record.set_field('Type',0)
    return definition


def synthesize_legacy_cache(schematic, *, version):
    """Create definitions in first-use name order for pre-34 schematics.

    Instances sharing one reference form a physical component's variants. The
    first physical component with a given symbol name supplies its cache slot.
    Original instance data remains separate and unchanged.
    """
    if version>=34:
        raise ValueError('legacy cache synthesis only applies before schema 34')
    cache=Element('CacheLib')
    cache.add('Categories')
    cache.add('Subfolders')
    slots=cache.add('Slots')
    parts=[p for p in schematic.select('Components/Part') if p.scalar('Enabled') in (True,'Y')]
    groups={}
    for part in parts:
        groups.setdefault(part.values[1],[]).append(part)
    names=set()
    for group in groups.values():
        name=group[0].values[0]
        if name in names:
            continue
        names.add(name)
        slot=slots.add('Slot',len(slots.children()),'')
        for index,component in enumerate(group):
            slot.append(_definition(component,index))
    cache.annotations['derived_from']='pre-34 placed component definitions'
    return cache


def upgrade_legacy_cache(schematic, *, version):
    """Add the public cache and library defaults absent before schema 34."""
    if version>=34 or schematic.child('CacheLib') is not None:
        return
    cache=synthesize_legacy_cache(schematic,version=version)
    count=len(cache.one('Slots').children())
    for name,value in [('ProjectLibs_Name','Project Libraries'),('ProjectLibs_Type',2),
                       ('ProjectLibs_Content',0),('ProjectLibs_Sorted',False),
                       ('DesignCache_Count',count-1)]:
        schematic.add(name,value).annotations['default_for_version']=version
    for name in ('ProjectLibs_Folders','ProjectLibs_Libs'):
        schematic.add(name,0).annotations['default_for_version']=version
    links=schematic.add('DesignCache_Links',count)
    for index in range(count):
        links.add('Link',index)
    schematic.append(cache)
