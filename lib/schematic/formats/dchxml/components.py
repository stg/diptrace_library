"""XML placed components and marking choices from shared schematic facts.

Definition/style selection belongs to the library exporter. This adapter accepts
that explicit association and does not infer definitions from reference names.
"""
import math

from ....common.xml_footprint_vocabulary import HORZ, VERT
from .syntax import (set_attribute)
from .settings import SHOW, ALIGN
from ....common.xml_output import enum_text, field, numeric
from ....common.model import (Element)
from ....common.xml_library_output import project_category


def project_marking(name, values, *, units, show_part=False):
    expected = 8 if show_part else 7
    if len(values) != expected:
        raise ValueError(f'{name}: marking requires {expected} values')
    result = Element(name)
    modes = [('Show', SHOW)]
    if show_part:
        modes.append(('ShowPart', SHOW))
    modes.extend((('Align', ALIGN), ('Horz', HORZ), ('Vert', VERT)))
    for (public, labels), value in zip(modes, values):
        set_attribute(result, public, enum_text(value.value, labels,
                      negative=labels[-1] if public in ('Horz', 'Vert') else None))
    x, y = units.point(*values[-3:-1])
    for public, value in (('X', x), ('Y', y), ('Angle', values[-1])):
        set_attribute(result, public, numeric(value))
    return result


def project_component(part, *, units, component_style, component_part=0, version=46):
    result = Element('Part')
    for public, value in (('Id', part.scalar('Number')), ('UpdateId', part.scalar('HiddenId'))):
        set_attribute(result, public, value)
    if part.scalar('PartType') == 4:
        set_attribute(result, 'BlockId', part.scalar('PageHiddenId'))
    set_attribute(result, 'ComponentStyle', component_style)
    set_attribute(result, 'ComponentPart', component_part)
    for name, own in (('AllowParts', 'AllowParts'), ('PartNumber', 'PartNumber'), ('Sheet', 'Page')):
        set_attribute(result, name, part.one(own).arguments[0])
    x, y = units.point(part.one('X').arguments[0], part.one('Y').arguments[0])
    set_attribute(result, 'X', numeric(x))
    set_attribute(result, 'Y', numeric(y))
    angle = math.radians(float(part.scalar('Angle')))
    if numeric(angle).value:
        set_attribute(result, 'Angle', numeric(angle))
    for name in ('HorzFlip', 'VertFlip'):
        if part.scalar(name):
            set_attribute(result, name, True)
    if part.scalar('ShowNumbers') > 0:
        set_attribute(result, 'ShowNumbers', enum_text(part.scalar('ShowNumbers'), SHOW))
    for name in ('ShowOrigin', 'CustomMarkingFont'):
        if part.scalar(name):
            set_attribute(result, name, True)
    from .fonts import (project_size)
    project_size(part, result, size='MarkingFontSize', legacy='MarkingFontSize', floating='MarkingFontSizeFloat', mono=None, version=version)
    if part.scalar('MarkingFontAll'):
        set_attribute(result, 'MarkingFontAll', True)
    if part.scalar('Group') >= 0:
        set_attribute(result, 'Group', part.scalar('Group'))
    for name in ('Selected', 'Locked'):
        if part.scalar(name):
            set_attribute(result, name, True)
    field(result, 'RefDes', part.arguments[1])
    for public, own in (('PartRefDes', 'PartDescriptor'), ('PartName', 'PartName'), ('Value', 'Value')):
        field(result, public, part.one(own).arguments[0])
    field(result, 'Name', part.arguments[0])
    if version >= 52:
        for name in ('BaseName', 'Manufacturer', 'Datasheet', 'PartString'):
            field(result, name, part.scalar(name))
    path = result.add('LibPath')
    field(path, 'Path', part.scalar('LibPath'))
    field(path, 'Var', part.scalar('LibPath_Variable', part.scalar('LibPath')))
    for name in ('RefDes', 'Name', 'Value', 'Manufacturer', 'Datasheet'):
        result.append(project_marking(name+'Marking', part.one('Show'+name).arguments,
                                     units=units, show_part=name in ('RefDes', 'Name')))
    users = part.select('UserFields/UserField')
    if users:
        target = result.add('AddFields')
        for user in users:
            if len(user.arguments) != 10:
                raise ValueError(f'{user.path}: user field requires name, text, type and seven marking values')
            item = project_marking('AddField', user.arguments[3:], units=units)
            # XML attribute order is immaterial. Keep all attributes before text
            # children in the editable representation, as in the raw adapter.
            set_attribute(item, 'Type', enum_text(user.values[2], ('Text', 'Link')))
            field(item, 'Name', user.arguments[0])
            field(item, 'Text', user.arguments[1])
            target.append(item)
    pins = result.add('Pins')
    for pin in part.select('Pins/Pin'):
        item = pins.add('Pin')
        set_attribute(item, 'NetId', pin.scalar('NetNumber'))
        if pin.scalar('NoConnect'):
            set_attribute(item, 'NotConnected', True)
    category = project_category(part)
    if category is not None:
        result.append(category)
    return result
