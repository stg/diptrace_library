"""One editable numeric size and optional monospacing choice per font."""
from .traversal import (placed_components, cached_definitions, footprints)


def symbol_fonts(part):
    for pin in part.select('Pins/Pin'):
        yield pin, 'NameFontSize', 'NameFontMono'
    for shape in part.select('Shapes/Shape'):
        yield shape, 'FontSize', 'FontMono'


def pattern_fonts(pattern):
    for collection, kind in (('Shapes', 'Shape'), ('Dimensions', 'Dimension')):
        for node in pattern.select(collection + '/' + kind):
            yield node, 'FontSize', 'FontMono'


def binary_fonts(schematic):
    """Font facts in the order of the schema-52 extension."""
    for part in placed_components(schematic):
        yield part, 'MarkingFontSize', None
        yield from symbol_fonts(part)
        yield from pattern_fonts(part.one('Pattern'))
    for shape in schematic.select('Shapes/Shape'):
        yield shape, 'FontSize', 'FontMono'
    for table in schematic.select('Tables/Table'):
        yield table, 'DefFontSize', 'DefFontMono'
        for cell in table.select('Cells/Cell'):
            yield cell, 'FontSize', 'FontMono'
    settings = schematic.one('Settings')
    yield settings, 'PartFontSize', 'PartFontMono'
    for name in ('PinNumberFont', 'BusConnectionFont', 'NetNameFontSize'):
        yield settings, name, None
    for page in schematic.select('Pages/Page'):
        yield page, 'ZoneFontSize', None
        for content in page.select('TitleBlocks/TitleBlock/Contents/Content'):
            yield content, 'FontSize', 'FontMono'
    for definition in cached_definitions(schematic):
        yield from symbol_fonts(definition.one('Part'))
        yield from pattern_fonts(definition.one('Pattern'))


def all_fonts(schematic):
    yield from binary_fonts(schematic)
    for pattern in schematic.select('CacheLib/Patterns/Pattern'):
        yield from pattern_fonts(pattern)


def complete_fonts(schematic):
    settings = schematic.one('Settings')
    if settings.child('NetNameFontSize') is None:
        settings.add('NetNameFontSize', 4)
    for node, size, mono in all_fonts(schematic):
        if mono and node.child(mono) is None:
            node.add(mono, False)
    for shape in schematic.select('Shapes/Shape'):
        if shape.child('PictureFlipped') is None:
            shape.add('PictureFlipped', False)


def compatibility_size(value):
    """Generate an integral compatibility size from the authoritative number."""
    from decimal import Decimal
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError('font size requires a number')
    return round(value)
