"""Serialize standalone component libraries from their current editable model."""
from ....common import footprint_objects
from ....common.catalog_codec import write_category_types
from ....common.conversion import export_diagnostics, warn
from ....common.drawing_codec import write_text_properties
from ....common.font_codec import compatibility_size
from ....common.footprint_codec import write_parameters, write_pattern_authoring
from ....common.library_model import write_library_model
from ....common.library_physical_output import write_library_pads, write_library_graphics, write_library_groups
from ....common.library_versions import library_text_layout
from ....common.symbol_codec import write_symbol_parameters, write_pin_parameters, PIN_FONT
from ..export_view import prepare_export, library_omissions
from .writer import Writer


def _physical(writer, part, pattern, *, layout):
    writer.rows(pattern.child('InternalConnections'), 'IntCon', 'integer integer')
    write_parameters(writer, pattern)
    writer.fields(part, 'number', 'Origin_X Origin_Y')
    writer.rows(pattern.child('PadPoints'), 'pt', 'number number')
    write_pattern_authoring(writer, pattern)
    write_library_pads(writer, pattern)
    write_library_graphics(writer, pattern, drawing_pad_links=writer.version >= 32,
                           extended_fonts=writer.version >= 33)
    write_library_groups(writer, pattern.child('Pattern_Groups'), layout=layout)
    writer.rows(pattern.child('UserFields'), 'UserField', 'text text integer')
    write_library_model(writer, pattern, variable_filename=True, authoring_properties=True, keep_pins=True)
    writer.field(pattern, 'Mounting', 'integer')
    writer.field(pattern, 'Pattern_CategoryName', 'text')
    writer.field(pattern, 'Pattern_CategoryIndex', 'integer')
    write_category_types(writer, pattern, 'Pattern_CategoryTypes')
    writer.rows(pattern.child('PossibleNames'), 'PossibleName', 'text')


def _pins(writer, part):
    pins = part.select('Pins/Pin')
    writer.integer(len(pins))
    for pin in pins:
        write_pin_parameters(writer, pin)
        writer.fields(pin, 'integer', 'PinNumRotate PinNameRotate ElectricType')
        writer.field(pin, 'Locked', 'boolean')
        writer.field(pin, 'ModelSig', 'text')
        for name, codec in PIN_FONT:
            writer.field(pin, name, codec)
        writer.number(pin.get('SignalDelay', 0))
        writer.field(pin, 'Group', 'integer')
        if writer.version >= 33:
            writer.boolean(pin.get('NameFontMono', False))
            writer.field(pin, 'NameFontSize', 'number')


def _drawings(writer, part):
    drawings = part.select('Shapes/Shape')
    writer.integer(len(drawings))
    for shape in drawings:
        writer.field(shape, 'Enabled', 'boolean')
        writer.fields(shape, 'integer', 'Type FontSize')
        writer.field(shape, 'FontColor', 'color')
        writer.field(shape, 'FontType', 'integer')
        writer.field(shape, 'FontName', 'text')
        writer.field(shape, 'PenWidth', 'number')
        writer.rows(shape.child('Points_New'), 'pt', 'number number')
        writer.fields(shape, 'boolean', 'Locked VectorFont')
        writer.fields(shape, 'number', 'FontWidth FontScale')
        write_text_properties(writer, shape)
        writer.field(shape, 'Group', 'integer')
        if writer.version >= 33:
            writer.boolean(shape.get('FontMono', False))
            writer.field(shape, 'FontSize', 'number')


def _metadata(writer, part, component, *, primary, layout):
    write_library_groups(writer, part.child('Groups'), layout=layout)
    writer.rows(component.child('UserFields') if primary else None, 'UserField', 'text text integer')
    writer.field(part, 'ModelType', 'integer')
    writer.field(part, 'ModelString', 'text')
    writer.rows(part.child('ModelBody'), 'Line', 'text')
    writer.field(part, 'SubfolderIndex', 'integer')
    states = part['Verification']
    writer.integer(len(states))
    for state in states:
        writer.boolean(state)
    writer.fields(part, 'text', 'Datasheet Manufacturer Component_CategoryName')
    writer.field(part, 'Component_CategoryIndex', 'integer')
    write_category_types(writer, component if primary else part, 'Component_CategoryTypes')
    supplier = component.child('Suppliers') if primary else None
    for name in ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'Currency'):
        writer.text(supplier.get(name, '') if supplier is not None else '')


def _adapt_revision(document, writer):
    if writer.version >= 33:
        return
    for component in document.select('/Library/Components/Component'):
        if writer.version < 32 and (pattern := component.child('Pattern')) is not None:
            selected = [shape for shape in pattern.select('Shapes/Shape') if shape['PadId'] >= 0]
            if selected:
                warn(writer.report, 'drawing-pad-reference', 'eli',
                     'This ELI revision omits drawing-to-pad associations.', selected)
        sizes = [(pin, 'NameFontSize', 'NameFontMono') for pin in component.select('Parts/Part/Pins/Pin')]
        sizes.extend((shape, 'FontSize', 'FontMono') for shape in component.select('Parts/Part/Shapes/Shape'))
        if (pattern := component.child('Pattern')) is not None:
            sizes.extend((node, 'FontSize', 'FontMono') for path in ('Shapes/Shape', 'Dimensions/Dimension')
                         for node in pattern.select(path))
        for node, size, mono in sizes:
            rounded = compatibility_size(node[size])
            if node[size] != rounded:
                node[size] = rounded
                warn(writer.report, 'fractional-font-size', 'eli',
                     'Destination font sizes are rounded to integral values.', (node,))
            if node.get(mono, False):
                node[mono] = False
                warn(writer.report, 'monospaced-font', 'eli',
                     'Destination omits monospaced vector-font selection.', (node,))


@export_diagnostics('eli')
def encode(document, *, version=None, report=None, text_layout=None):
    writer = Writer(version, report=report)
    document = prepare_export(document, destination='eli', report=report)
    library_omissions(document, destination='eli', report=writer.report)
    _adapt_revision(document, writer)
    layout = text_layout if text_layout is not None else library_text_layout(current=writer.version >= 33)
    library = document.one('/Library')
    components = library.select('Components/Component')
    writer.container(library, len(components))
    for component in components:
        parts = component.select('Parts/Part')
        writer.integer(len(parts))
        for ordinal, part in enumerate(parts):
            write_symbol_parameters(writer, part)
            pattern = component.child('Pattern') if ordinal == 0 else None
            _physical(writer, part, pattern if pattern is not None else footprint_objects.new_pattern(), layout=layout)
            _pins(writer, part)
            _drawings(writer, part)
            _metadata(writer, part, component, primary=ordinal == 0, layout=layout)
    return bytes(writer.buffer)
