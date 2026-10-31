"""Cached binary definitions share codecs without losing PCB-owned identities."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.font_codec import read_font_properties, write_font_properties
from lib.common.footprint_codec import read_pattern_extensions, read_pad_mask_states
from lib.common.model import Element
from lib.common.supplier_codec import read_supplier
from lib.common.symbol_codec import read_symbol_extensions
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.dip.cache import read_cache
from lib.pcb.formats.dip.modern import read_pin_rotations
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.formats.dip.write_cache import (DefinitionOutput, write_cache, write_cache_masks,
    write_cache_extensions, write_cache_pin_rotations, cache_font_records,
    write_cache_model_options, write_cache_suppliers, write_cache_paths, write_cache_shields)
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import design, signature, syntax
from lib.pcb.tests.test_dimension_projection import dimension


def sections(document, *, report=None):
    writer, board = Writer(report=report), document.one('/Board')
    writer.header()
    outputs = write_cache(writer, board)
    write_cache_masks(writer, outputs)
    write_cache_extensions(writer, outputs)
    write_cache_pin_rotations(writer, outputs)
    write_cache_model_options(writer, outputs)
    write_cache_suppliers(writer, outputs)
    write_cache_paths(writer, board)
    write_cache_shields(writer, outputs)
    write_font_properties(writer, cache_font_records(outputs))
    return bytes(writer.buffer)


def read_sections(document, *, report=None):
    data = sections(document, report=report)
    reader, board = Reader(data+b'\0'), Element('Board')
    cached = read_cache(reader, board)
    for item in cached:
        for pad in item.definition.select('Pattern/Pads/Pad'):
            read_pad_mask_states(reader, pad, extended=True)
    for item in cached:
        read_pattern_extensions(reader, item.definition.one('Pattern'))
        read_symbol_extensions(reader, item.definition.one('Part'))
    read_pin_rotations(reader, cached)
    for item in cached:
        reader.field(item.definition.one('Pattern/Model3D'), 'KeepPins', 'boolean')
    for item in cached:
        read_supplier(reader, item.definition.one('Part'), prices=False)
    for slot in board.select('CacheLib/Slots/Slot'):
        reader.field(slot, 'VariablePath', 'text')
        definitions = slot.children('Definition')
        owner = definitions[0].one('Pattern/Model3D') if definitions else slot
        reader.field(owner, 'Model3DFile_Variable', 'text')
    for item in cached:
        for shape in item.definition.select('Pattern/Shapes/Shape'):
            reader.field(shape, 'ShieldGroup', 'integer')
    outputs = tuple(DefinitionOutput(item.definition,
        tuple(item.definition.select('Pattern/Pads/Pad')),
        tuple(item.definition.select('Pattern/Shapes/Shape')),
        tuple(item.definition.select('Pattern/Holes/Hole'))) for item in cached)
    read_font_properties(reader, cache_font_records(outputs))
    if reader.pos != len(data):
        raise AssertionError('cached definition section boundary differs')
    return board, data


def reopen(document, *, report=None):
    raw, _ = read_sections(document, report=report)
    prepared = prepare_core(dumps(syntax(document, report=ConversionReport()), preserve=False))
    for row in tuple(raw.children()):
        if (previous := prepared.board.child(row.kind)) is not None:
            previous.detach()
        row.move_to(prepared.board)
    return assemble_graphics(prepared).document


class DipCacheOutputTests(unittest.TestCase):
    def test_shared_symbol_footprint_catalogues_and_literal_paths_reopen(self):
        document = design()
        expected, before = signature(document.one('/Board/CacheLib')), dumps(document, preserve=False)
        report = ConversionReport()
        rebuilt = reopen(document, report=report)
        self.assertEqual(signature(rebuilt.one('/Board/CacheLib')), expected)
        self.assertEqual(signature(reopen(rebuilt).one('/Board/CacheLib')), expected)
        self.assertEqual(sections(rebuilt), sections(document))
        self.assertEqual(dumps(document, preserve=False), before)
        self.assertEqual(report.notices, [])
        rebuilt.references.validate()

    def test_current_pad_slot_and_group_positions_generate_cache_selectors(self):
        document = design()
        board = document.one('/Board')
        slot = board.one('CacheLib/Slots/Slot')
        pattern = slot.one('Definition/Pattern')
        pattern.one('Pads/Pad[1]').move_to(pattern.one('Pads'))
        document.copy(slot.one('Definition/Part/Groups/pt'), index=0)
        empty = slot.parent.add('Slot', 0, 'empty.eli')
        empty['VariablePath'] = ''
        empty.move_to(slot.parent, 0)
        raw, _ = read_sections(document)
        saved = raw.one('CacheLib/Slots/Slot[2]/Definition/Part/Pins/Pin')
        self.assertEqual((saved['Number'], saved['Group']), (2, 1))
        self.assertEqual(raw.one('DesignCache_Links/Link').values, (1,))
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt.one('/Board/CacheLib')), signature(board.one('CacheLib')))

    def test_full_font_angles_multiline_text_masks_shields_and_model_placement_survive(self):
        document = design()
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
        shape = definition.one('Part/Shapes/Shape')
        shape['TextAngle'], shape['FontSize'], shape['FontMono'] = Decimal('8.25'), Decimal('1.375'), True
        shape.one('TextLine').add('pt', '')
        shape.one('TextLine').add('pt', 'Second line')
        definition.one('Part/Pins/Pin')['NameFontMono'] = True
        definition.one('Part/Pins/Pin')['NameFontSize'] = Decimal('6.125')
        pattern = definition.one('Pattern')
        pattern.one('Pads/Pad[1]')['DisableTopMask'] = 1
        pattern.one('Shapes/Shape')['ShieldGroup'] = 7
        pattern.one('Shapes/Shape')['FontMono'] = True
        pattern.one('Model3D/Rotate')['Z'] = Decimal('38.25')
        pattern.one('Model3D/Offset')['X'] = Decimal('1.25')
        expected = signature(document.one('/Board/CacheLib'))
        self.assertEqual(signature(reopen(document).one('/Board/CacheLib')), expected)

    def test_unprepared_section_writer_does_not_silently_retarget_pin_domains(self):
        document = design()
        slot = document.one('/Board/CacheLib/Slots/Slot')
        original = slot.one('Definition')
        second = slot.add('Definition', 0)
        document.copy(original.one('Part'), parent=second)
        document.copy(original.one('Pattern'), parent=second)
        original.move_to(slot)
        before = dumps(document, preserve=False)
        with self.assertRaisesRegex(PcbError, 'first definition'):
            sections(document)
        self.assertEqual(dumps(document, preserve=False), before)

    def test_cached_holes_dimensions_terminals_and_paste_follow_current_references(self):
        document = design()
        pattern = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        group = pattern.one('Pattern_Groups').add('pt')
        group['Enabled'], group['X'], group['Y'] = True, 2, 3
        hole = pattern.one('Holes').add('Hole', True, False, 7, 8, 3, 1)
        hole['Group'] = group
        document.copy(hole, parent=hole.parent)['X'] = 9
        pad = pattern.one('Pads/Pad[1]')
        pad['Group'], pad['PadShape_New'] = group, 3
        pad.one('PadPoints_New').add('pt', 5, 6)
        for owner in (pattern, pad):
            terminal = owner.add('PadTerminal', 0)
            for name, current in dict(Type=3, X=1, Y=2, Angle=Decimal('.4'), ShapeWidth=3,
                                      ShapeHeight=4, ShapeCorner=5).items():
                terminal.add(name, current)
            terminal.add('ShapePoints').add('pt', 1, 2)
            owner.one('PadMask_TopSegments').add('pt', 1, 2, 3, 4)
        source = syntax(document)
        target = source.one('/Board/CacheLib/cl_Components/cl_Component/cl_Pattern')
        row = dimension(target.one('cl_Dimensions'), Connected1=0, Object1=0, SubObject1=1, Point1=0,
                        Connected2=2, Object2=0, SubObject2=1, Point2=0, Group=0)
        for name in ('NonSignal', 'PanelExclude'):
            row.one(name).detach()
        for child in row.walk(include_self=True):
            child.kind = 'cl_'+child.kind
        document = assemble_graphics(prepare_core(dumps(source, preserve=False))).document
        pattern = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        pattern.one('Pads/Pad[1]').move_to(pattern.one('Pads'))
        pattern.one('Holes/Hole[1]').move_to(pattern.one('Holes'))
        expected = signature(pattern)
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt.one(pattern.path)), expected)
        self.assertEqual(signature(reopen(rebuilt).one(pattern.path)), expected)

    def test_known_template_omissions_warn_and_leave_authored_data_untouched(self):
        document = design()
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
        definition.one('Pattern')['Value'] = 'Template value'
        definition.one('Part/Pins/Pin')['SignalDelay'] = Decimal('.5')
        before, report = dumps(document, preserve=False), ConversionReport()
        sections(document, report=report)
        self.assertEqual({notice.rule for notice in report.warnings}, {'cached-pattern-metadata', 'cached-pin-delay'})
        self.assertEqual(dumps(document, preserve=False), before)

    def test_unmapped_cached_data_fails_without_altering_the_model(self):
        document = design()
        document.one('/Board/CacheLib/Slots/Slot/Definition/Part/Pins/Pin').add('Unmapped', 3)
        before = dumps(document, preserve=False)
        with self.assertRaises(PcbError):
            sections(document)
        self.assertEqual(dumps(document, preserve=False), before)

    def test_absent_optional_paste_groups_and_terminal_contours_write_empty_arrays(self):
        document = design()
        pattern = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        for owner in (pattern, *pattern.select('Pads/Pad')):
            for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
                self.assertFalse(owner.one(name).children())
                owner.one(name).detach()
        self.assertFalse(pattern.one('Pattern_Groups').children())
        pattern.one('Pattern_Groups').detach()
        terminal = pattern.add('PadTerminal', 0)
        for name, value in dict(Type=0, X=0, Y=0, Angle=0, ShapeWidth=1, ShapeHeight=1, ShapeCorner=0).items():
            terminal[name] = value
        before = dumps(document, preserve=False)
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt.one(pattern.path)), signature(pattern))
        self.assertEqual(sections(rebuilt), sections(document))
        self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
