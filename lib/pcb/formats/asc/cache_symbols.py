"""PCB ASC cached symbol data over the shared symbol and drawing schemas."""
from ....common.asc_model_body import project_model_body
from ....common.conversion import info, warn
from ....common.supplier_conversion import report_supplier_omissions
from ....common.model import Element
from ....common import drawing_records, library_metadata, supplier_records
from ...model import library_records as model
from ..errors import PcbError
from .cache_values import prefix, groups, classifications, user_field_rows
from .footprint_projection import points
from .projection import check, collection, fields, flag, value
from ..local_group_projection import selection as group_selection
from ..symbol_pin_projection import number as pin_number


def _pin(pin, report):
    check(pin, model.PIN)
    if pin.child('UnresolvedKeys') is not None:
        raise PcbError(f'{pin.path}: unresolved cached pin extensions need an ASC mapping')
    output = Element('Pin', pin['Index'], pin['X'], pin['Y'])
    fields(pin, output, exclude=(*pin.schema.parameters, 'Number', 'NameFontMono', 'SignalDelay', 'UnresolvedGroupId'),
           names={'PinNameXShift':'PinNamexShift'})
    output.add('Number', pin_number(pin, destination='asc', report=report))
    output.add('Group', group_selection(pin, destination='asc', report=report))
    if value(pin, 'NameFontMono') or pin.get('SignalDelay', 0):
        warn(report, 'cached-pin-options', 'asc', 'ASC omits cached pin monospace or signal-delay settings', (pin,))
    elif pin.child('SignalDelay') is not None:
        info(report, 'cached-pin-default-delay', 'asc', 'ASC omits a cached pin zero-delay field', (pin,))
    return output


def _drawing(shape, report):
    check(shape, model.DRAWING)
    if shape.child('UnresolvedKeys') is not None:
        raise PcbError(f'{shape.path}: unresolved cached drawing extensions need an ASC mapping')
    output = Element('Shape', shape['Index'])
    fields(shape, output, exclude=('ShowPart','MarkingGenerated','FontMono','UnresolvedGroupId'),
           names={'PenWidth':'Width', 'TextAngle':'Orientation'})
    output.add('Group', group_selection(shape, destination='asc', report=report))
    lines = collection(shape, 'TextLine', drawing_records.TEXT_LINES, drawing_records.TEXT_LINE)
    output.add('Name', lines[0]['Text'] if lines else '')
    text = output.add('TextLines')
    for line in lines:
        text.add('TextLine', line['Text'])
    geometry = shape.child('Points_New')
    output.append(points(geometry, kind='Points') if geometry is not None else Element('Points'))
    if any(value(shape, name) for name in ('ShowPart','MarkingGenerated','FontMono')):
        warn(report, 'cached-symbol-drawing-options', 'asc',
             'ASC omits cached symbol drawing visibility, generation or monospace settings', (shape,))
    return output


def project_symbol(part, *, report=None):
    check(part, model.SYMBOL)
    output = Element('Part', part['Name'], part['RefDes'])
    fields(part, output, exclude=('Name','RefDes','Verification','Datasheet'), names={
        'Origin_X':'OriginX', 'Origin_Y':'OriginY',
        'Component_CategoryName':'CategoryName', 'Component_CategoryIndex':'CategoryIndex'})
    output.add('Verification', *(flag(item) for item in part['Verification']))
    pins = output.add('Pins')
    for pin in collection(part, 'Pins', model.PINS, model.PIN):
        pins.append(_pin(pin, report))
    shapes = output.add('Shapes')
    for shape in collection(part, 'Shapes', model.DRAWINGS, model.DRAWING):
        shapes.append(_drawing(shape, report))
    output.append(groups(part, 'Groups'))
    output.append(classifications(part, 'Component'))
    output.append(user_field_rows(part, symbol=True))
    body = part.child('ModelBody')
    if body is not None:
        check(body, library_metadata.MODEL_BODY)
        output.append(project_model_body(body))
    else:
        output.add('ModelBody')
    prefix(output)
    supplier = part.child('Suppliers')
    if supplier is not None:
        check(supplier, supplier_records.SUPPLIERS)
        target = output.add('Suppliers')
        fields(supplier, target, exclude=('SourceLocator', 'MainSupplier'))
        collection(supplier, 'Prices', supplier_records.PRICES, supplier_records.QUOTE)
        report_supplier_omissions((part,), destination='asc', report=report, omit_preference=True)
    return output
