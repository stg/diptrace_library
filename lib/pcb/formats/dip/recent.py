"""Later PCB identity, shielding, picture and font records."""
from ....common.font_codec import read_font_properties
from .preamble import _fields


def _pair_shields(reader, pair, *, separate):
    for segment in pair.select('Segments/Segment'):
        for center in segment.select('CenterPoints/CenterPoint'):
            _fields(reader, center, 'integer', 'PosShieldGroup NegShieldGroup')
            for collection, kind in (('PosPoints', 'PosPoint'), ('NegPoints', 'NegPoint')):
                for point in center.select(collection+'/'+kind):
                    reader.field_into(point, 'ShieldGroup', 'integer')
    if separate:
        for collection, kind in (('PosSeparateTraces', 'PosTrace'), ('NegSeparateTraces', 'NegTrace')):
            for point in pair.select(collection+'/'+kind+'/Points/Point'):
                reader.field_into(point, 'ShieldGroup', 'integer')


def _shields(reader, board, cached_definitions):
    for component in board.select('Components/Component'):
        reader.field_into(component, 'ShieldGroup', 'integer')
        for collection, kind in (('Pads', 'Pad'), ('Shapes', 'Shape')):
            for node in component.select('Pattern/'+collection+'/'+kind):
                reader.field_into(node, 'ShieldGroup', 'integer')
    for point in board.select('Nets/Net/Traces/Trace/Points/Point'):
        reader.field_into(point, 'ShieldGroup', 'integer')
    for pair in board.select('DifferentialPairs/DifferentialPair'):
        _pair_shields(reader, pair, separate=True)
    for pair in board.select('RemovedDifferentialPairs/RemovedDifferentialPair'):
        _pair_shields(reader, pair, separate=False)
    for pour in board.select('CopperPours/CopperPour'):
        reader.field_into(pour, 'ShieldGroup', 'integer')
    reader.field_into(board, 'ShieldGroup', 'integer')
    for cached in cached_definitions:
        for shape in cached.definition.select('Pattern/Shapes/Shape'):
            reader.field_into(shape, 'ShieldGroup', 'integer')


def _pattern_fonts(pattern):
    for collection, kind in (('Shapes', 'Shape'), ('Dimensions', 'Dimension')):
        for node in pattern.select(collection+'/'+kind):
            yield node, 'FontSize', 'FontMono'


def _font_records(board, cached_definitions):
    for component in board.select('Components/Component'):
        yield component, 'MarkingFontSize', None
        yield from _pattern_fonts(component.one('Pattern'))
    for collection, kind in (('Shapes', 'Shape'), ('Dimensions', 'Dimension')):
        for node in board.select(collection+'/'+kind):
            yield node, 'FontSize', 'FontMono'
    for table in board.select('Tables/Table'):
        yield table, 'FontSize', 'DefFontMono'
        for cell in table.select('Cells/Cell'):
            yield cell, 'FontSize', 'FontMono'
    yield board, 'CompFontSize', 'CompFontMono'
    yield board.one('SheetSettings/BorderZones'), 'FontSize', None
    for title in board.select('SheetSettings/TitleBlocks/TitleBlock'):
        for cell in title.select('Contents/Content'):
            yield cell, 'FontSize', 'FontMono'
    for cached in cached_definitions:
        for pin in cached.definition.select('Part/Pins/Pin'):
            yield pin, 'NameFontSize', 'NameFontMono'
        for shape in cached.definition.select('Part/Shapes/Shape'):
            yield shape, 'FontSize', 'FontMono'
        yield from _pattern_fonts(cached.definition.one('Pattern'))


def read_recent_extensions(reader, board, cached_definitions):
    version = reader.header.version
    if version > 54:
        _fields(reader, board.one('Panel'), 'number', 'LeftGap RightGap TopGap BottomGap')
    if version > 55:
        for net in board.select('Nets/Net'):
            reader.field_into(net, 'HiddenId', 'integer')
    if version > 56:
        _shields(reader, board, cached_definitions)
    if version > 57:
        for pour in board.select('CopperPours/CopperPour'):
            reader.field_into(pour, 'TraceShieldGroup', 'integer')
    if version > 58:
        for shape in board.select('Shapes/Shape'):
            reader.field_into(shape, 'PictureFlipped', 'boolean')
    if version > 59:
        reader.field_into(board, 'SchemNetClasses', 'boolean')
    else:
        reader.add_into(board, 'SchemNetClasses', False)
    if version > 60:
        read_font_properties(reader, _font_records(board, cached_definitions))
    if version > 61:
        for net in board.select('Nets/Net'):
            reader.field_into(net, 'AllowLoops', 'boolean')
