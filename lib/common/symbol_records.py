"""Unplaced component-symbol definitions shared by design document families."""
from .schema import Child, Field, Record


def _required(name, kind):
    return Field(name, kind, required=True)


SYMBOL = Record('CachedPart', {
    'Enabled': _required('Enabled', 'boolean'),
    'PartType': _required('PartType', 'integer'),
    'PartName': _required('PartName', 'text'),
    'ShowNumbers': _required('ShowNumbers', 'integer'),
    'Type': _required('Type', 'integer'),
    'Number1': _required('Number1', 'integer'),
    'Number2': _required('Number2', 'integer'),
    'Width': _required('Width', 'number'),
    'Height': _required('Height', 'number'),
    'Value': Field('Value', 'text', default=''),
    'LockProperties': _required('LockProperties', 'boolean'),
    'Origin_X': _required('Origin_X', 'number'),
    'Origin_Y': _required('Origin_Y', 'number'),
    'ModelType': _required('ModelType', 'integer'),
    'ModelString': _required('ModelString', 'text'),
    'SubfolderIndex': _required('SubfolderIndex', 'integer'),
    'Manufacturer': Field('Manufacturer', 'text', default=''),
    'Component_CategoryName': _required('Component_CategoryName', 'text'),
    'Component_CategoryIndex': _required('Component_CategoryIndex', 'integer'),
    'ModelNote': _required('ModelNote', 'text'),
    'Datasheet': Field('Datasheet', 'text'),
    'Name': Field('Name', 'text', required=True, default=''),
    'RefDes': Field('RefDes', 'text', required=True, default=''),
    'Verification': Field('Verification', 'tuple', required=True, default=(False,)*7,
        item_kind='boolean', length=7,
        description='Seven compatibility verification states in their established order.'),
}, parameters=('Name', 'RefDes'), children={
    name: Child(name, record) for name, record in (
        ('Component_CategoryTypes', 'Classifications'), ('Pins', 'CachedPins'),
        ('Shapes', 'SymbolDrawings'), ('UserFields', 'ComponentUserFields'),
        ('Groups', 'LocalGroups'), ('ModelBody', 'ModelBody'), ('Suppliers', 'Suppliers'))
})

PIN = Record('CachedPin', {
    'Enabled': _required('Enabled', 'boolean'),
    'Locked': _required('Locked', 'boolean'),
    'ModelSig': _required('ModelSig', 'text'),
    'Type': _required('Type', 'integer'),
    'Orientation': _required('Orientation', 'integer'),
    'Number': _required('Number', 'integer'),
    'Length': _required('Length', 'number'),
    'Name': _required('Name', 'text'),
    'StringNumber': _required('StringNumber', 'text'),
    'ShowName': _required('ShowName', 'boolean'),
    **{name: _required(name, 'number') for name in
       ('PinNumXShift', 'PinNumYShift', 'PinNameXShift', 'PinNameYShift')},
    'ElectricType': _required('ElectricType', 'integer'),
    **{name: _required(name, 'number') for name in ('NameFontSize', 'NameFontWidth', 'NameFontScale')},
    'Group': _required('Group', 'integer'),
    'PinNameRotate': _required('PinNameRotate', 'number'),
    'PinNumRotate': _required('PinNumRotate', 'number'),
    'NameFontMono': Field('NameFontMono', 'boolean', default=False),
    'SignalDelay': Field('SignalDelay', 'number'),
    'Index': Field('Index', 'integer', required=True, default=0,
        getter=lambda node: node._ordinal(), ordinal_dependencies=lambda node: (node,)),
    'X': Field('X', 'number', required=True, default=0, unit='shared length'),
    'Y': Field('Y', 'number', required=True, default=0, unit='shared length'),
}, parameters=('Index', 'X', 'Y'), children={'UnresolvedKeys': Child('UnresolvedKeys', 'UnresolvedKeys')})

PINS = Record('CachedPins', {}, children={'Pin': Child('Pin', PIN.name, maximum=None)})

DRAWING = Record('SymbolDrawing', {
    name: Field(name, kind, required=True, unit=unit)
    for name, kind, unit in (
        ('Enabled', 'boolean', ''), ('Type', 'integer', ''), ('FontSize', 'number', ''),
        ('FontColor', 'integer', ''), ('FontType', 'integer', ''), ('FontName', 'text', ''),
        ('PenWidth', 'number', 'shared length'), ('TextAngle', 'number', 'radians'),
        ('TextHorz', 'integer', ''), ('TextVert', 'integer', ''), ('TextAlign', 'integer', ''),
        ('LineSpacing', 'number', ''), ('Group', 'integer', ''), ('ShowPart', 'boolean', ''),
        ('MarkingGenerated', 'boolean', ''), ('Locked', 'boolean', ''),
        ('VectorFont', 'boolean', ''), ('FontWidth', 'number', ''), ('FontScale', 'number', ''))
} | {
    'FontMono': Field('FontMono', 'boolean', default=False),
    'Index': Field('Index', 'integer', required=True, default=0,
        getter=lambda node: node._ordinal(), ordinal_dependencies=lambda node: (node,)),
}, parameters=('Index',), children={
    name: Child(name, record) for name, record in (
        ('Points_New', 'Points'), ('TextLine', 'TextLines'), ('UnresolvedKeys', 'UnresolvedKeys'))
})

DRAWINGS = Record('SymbolDrawings', {}, description='An ordered collection of SymbolDrawing records.',
                  children={'Shape': Child('Shape', DRAWING.name, maximum=None)})
