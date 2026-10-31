"""Document-independent constructors for unplaced symbol definitions."""
from .model import Element
from .symbol_records import SYMBOL, PIN, DRAWING


def fields(parent, **values):
    for name, value in values.items():
        parent.add(name, value)
    return parent


def symbol_data(name='', reference=''):
    """Create shared symbol content before choosing its document-specific record."""
    part = Element('Part', name, reference)
    fields(part, Enabled=True, PartType=0, PartName='', ShowNumbers=0, Type=0,
           Number1=0, Number2=0, Width=0, Height=0, Value='', LockProperties=False,
           Origin_X=0, Origin_Y=0, ModelType=0, ModelString='', Manufacturer='',
           Component_CategoryName='', Component_CategoryIndex=-1)
    for key in ('Pins', 'Shapes', 'UserFields', 'ModelBody', 'Component_CategoryTypes'):
        part.add(key)
    supplier = part.add('Suppliers')
    fields(supplier, PartNumber='', Manufacturer='', Pattern='', Supplier='', SourceLocator='', Currency='')
    supplier.one('SourceLocator').annotations['asc_omit'] = 'not present in ASC'
    return part


def new_symbol(name='', reference=''):
    part = symbol_data(name, reference)
    fields(part, SubfolderIndex=-1)
    part.add('Verification', False, False, False, False, False, False, False)
    part.add('Groups')
    part.add('ModelNote', '')
    return part.bind_schema(SYMBOL)


def new_pin(index=0):
    pin = Element('Pin', index, 0, 0)
    fields(pin, Enabled=True, Type=0, Orientation=0, Number=-1, Length=3, Name='',
           StringNumber='', ShowName=True, PinNumXShift=0, PinNumYShift=0,
           PinNameXShift=0, PinNameYShift=0, ElectricType=0, Locked=False, ModelSig='',
           NameFontSize=6, NameFontWidth=-1, NameFontScale=1, Group=-1,
           PinNameRotate=0, PinNumRotate=0, NameFontMono=False)
    return pin.bind_schema(PIN)


def new_drawing(index=0):
    shape = Element('Shape', index)
    fields(shape, Enabled=True, Type=1, FontSize=6, FontColor=0, FontType=0,
           FontName='', PenWidth=.3, TextAngle=0, TextHorz=0, TextVert=0,
           TextAlign=0, LineSpacing=1.2, Group=-1, ShowPart=False, MarkingGenerated=False,
           Locked=False, VectorFont=True, FontWidth=-1, FontScale=1, FontMono=False)
    for name in ('TextLine', 'Points_New'):
        shape.add(name)
    return shape.bind_schema(DRAWING)
