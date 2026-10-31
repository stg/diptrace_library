"""XML symbol output follows edited identities rather than saved positions."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.common.xml import set_attribute
from lib.pcb.formats.dipxml.pattern_output import project_pattern
from lib.pcb.formats import io
from lib.pcb.formats.dipxml.symbol_output import project_symbol
from lib.pcb.formats.dipxml.syntax import dumps, loads
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read, source


PATH = '/Board/CacheLib/Slots/Slot/Definition'


def reopen(document, *, units='mm'):
    definition = document.one(PATH)
    physical = project_pattern(definition.one('Pattern'), style='P', units=XmlUnits(units), report=ConversionReport())
    symbol = project_symbol(definition.one('Part'), units=XmlUnits(units), pad_keys=physical.pad_keys,
                            pattern_style='P', connections=physical.connections, report=ConversionReport())
    wrapper = loads(source())
    library = wrapper.one('/Source/Library')
    set_attribute(library, 'Units', units)
    library.one('Components/Component/Part').detach()
    library.one('Components/Component').append(symbol)
    inner = library.one('Library')
    set_attribute(inner, 'Units', units)
    inner.one('PadStyles').detach()
    inner.one('Patterns').detach()
    inner.append(physical.styles)
    inner.add('Patterns').append(physical.element)
    # This is a library-section check. An unrelated placed component from the
    # input fixture must not retain selectors into its former physical style.
    root = wrapper.one('/Source')
    root.one('Board').detach()
    board = root.add('Board')
    layers = board.add('CopperLayers')
    for index, name in enumerate(('Top', 'Bottom')):
        layer = layers.add('Lay')
        set_attribute(layer, 'Id', index)
        layer.add('Name', name)
    board.add('Components')
    board.add('Nets')
    return read(dumps(wrapper), report=ConversionReport()), symbol


class XmlSymbolOutputTests(unittest.TestCase):
    def test_cached_drawing_flags_warn_without_discarding_the_drawing(self):
        for flags in (('ShowPart',), ('MarkingGenerated',), ('ShowPart', 'MarkingGenerated')):
            with self.subTest(flags=flags):
                document = read(source(), report=ConversionReport())
                part = document.one(PATH+'/Part')
                shape = part.one('Shapes/Shape')
                shape['Type'], shape['PenWidth'] = 10, 0
                shape.one('TextLine').add('pt', 'unplaced text')
                for flag in flags:
                    shape[flag] = True
                before = model_text(document, preserve=False)
                report = ConversionReport()
                rebuilt = io.parse(io.serialize(document, format='dipxml', report=report), report=ConversionReport())
                output = rebuilt.one(PATH+'/Part/Shapes/Shape')
                self.assertEqual(output.one('TextLine/pt').values, ('unplaced text',))
                self.assertEqual([point.values for point in output.select('Points_New/pt')],
                                 [point.values for point in shape.select('Points_New/pt')])
                self.assertFalse(output['ShowPart'])
                self.assertFalse(output['MarkingGenerated'])
                self.assertEqual(len([n for n in report.warnings if n.rule == 'cached-drawing-flags']), 1)
                self.assertEqual(report.errors, [])
                self.assertEqual(model_text(document, preserve=False), before)

    def test_inactive_unreferenced_group_is_omitted_on_a_detached_projection(self):
        document = read(source(), report=ConversionReport())
        part = document.one(PATH+'/Part')
        inactive = document.copy(part.one('Groups/pt'), index=0)
        inactive['Enabled'] = False
        before = model_text(document, preserve=False)
        report = ConversionReport()
        rebuilt = io.parse(io.serialize(document, format='dipxml', report=report), report=ConversionReport())
        result = rebuilt.one(PATH+'/Part')
        self.assertEqual(len(result.select('Groups/pt')), 1)
        self.assertIs(result.one('Pins/Pin')['Group'], result.one('Groups/pt'))
        self.assertIs(result.one('Shapes/Shape')['Group'], result.one('Groups/pt'))
        self.assertIn('local-group-normalization', [notice.rule for notice in report.infos])
        self.assertEqual(report.errors, [])
        self.assertEqual(model_text(document, preserve=False), before)

    def test_verification_states_warn_and_use_xml_defaults_on_reimport(self):
        document = read(source(), report=ConversionReport())
        part = document.one(PATH+'/Part')
        part['Verification'] = (True,)*7
        report = ConversionReport()
        rebuilt = io.parse(io.serialize(document, format='dipxml', report=report), report=ConversionReport())
        self.assertEqual(rebuilt.one(PATH+'/Part')['Verification'], (False,)*7)
        self.assertEqual(rebuilt.one(PATH+'/Part')['Name'], part['Name'])
        self.assertEqual(part['Verification'], (True,)*7)
        self.assertEqual(len([notice for notice in report.warnings if notice.rule == 'symbol-verification']), 1)
        self.assertEqual(report.errors, [])

    def test_numbered_pins_without_physical_pads_keep_their_numbers(self):
        for number in (0, 7):
            with self.subTest(number=number):
                wrapper = loads(source())
                wrapper.one('/Source/Library/Library/Patterns/Pattern/Pads').detach()
                symbol = wrapper.one('/Source/Library/Components/Component/Part')
                set_attribute(symbol.one('Pins/Pin'), 'PadId', number)
                symbol.one('InternalConnections').detach()
                # The fixture's placed component is unrelated to this unplaced
                # symbol; it cannot use the now empty physical definition.
                wrapper.one('/Source/Board/Components').detach()
                wrapper.one('/Source/Board/Nets').detach()
                document = read(dumps(wrapper), report=ConversionReport())
                before = signature(document.one(PATH+'/Part'))
                rebuilt, xml = reopen(document)
                self.assertEqual(xml.one('Pins/Pin')['PadId'], number)
                part = rebuilt.one(PATH+'/Part')
                self.assertEqual(signature(part), before)
                self.assertFalse(rebuilt.references.outgoing(part, role='symbol-pin-pad'))

    def test_pin_and_drawing_groups_survive_pad_and_group_reordering(self):
        document = read(source(), report=ConversionReport())
        definition = document.one(PATH)
        part, pattern = definition.one('Part'), definition.one('Pattern')
        assigned = pattern.one('Pads/Pad[1]')
        assigned.move_to(pattern.one('Pads'))
        document.copy(part.one('Groups/pt'), index=0)
        before = model_text(document, preserve=False)
        rebuilt, xml = reopen(document)
        self.assertEqual(xml.one('Pins/Pin')['PadId'], 17)
        self.assertEqual(xml.one('Pins/Pin')['Group'], 1)
        self.assertEqual(xml.one('Shapes/Shape')['Group'], 1)
        self.assertEqual(signature(rebuilt.one(PATH+'/Part')), signature(part))
        target = rebuilt.references.outgoing(rebuilt.one(PATH+'/Part'), role='symbol-pin-pad')[0].target
        self.assertEqual(target['Id'], 17)
        self.assertEqual(target['Index'], 1)
        self.assertEqual(signature(reopen(rebuilt)[0].one(PATH+'/Part')), signature(part))
        self.assertEqual(model_text(document, preserve=False), before)

    def test_zero_public_pad_key_is_not_confused_with_an_unassigned_pin(self):
        document = read(source(), report=ConversionReport())
        document.one(PATH+'/Pattern/Pads/Pad[1]')['Id'] = 0
        rebuilt, xml = reopen(document)
        self.assertEqual(xml.one('Pins/Pin')['PadId'], 0)
        part = rebuilt.one(PATH+'/Part')
        self.assertEqual(part.one('Pins/Pin')['Number'], 1)
        self.assertEqual(rebuilt.references.outgoing(part, role='symbol-pin-pad')[0].target['Id'], 0)

    def test_fractional_text_and_pin_fonts_keep_physical_width_across_units(self):
        document = read(source(), report=ConversionReport())
        part = document.one(PATH+'/Part')
        pin, drawing = part.one('Pins/Pin'), part.one('Shapes/Shape')
        pin['NameFontSize'], pin['NameFontMono'], pin['NameFontWidth'] = Decimal('6.25'), True, Decimal('.4572')
        pin['SignalDelay'] = Decimal('1.125')
        drawing['Type'], drawing['FontSize'], drawing['FontMono'] = 10, Decimal('7.125'), True
        drawing['FontWidth'], drawing['TextAngle'] = Decimal('.4572'), Decimal('.375')
        # Pen width belongs to line geometry, not the new text variant.
        drawing['PenWidth'] = 0
        drawing.one('TextLine').add('pt', 'first')
        drawing.one('TextLine').add('pt', 'second')
        before = signature(part)
        for units in ('mm', 'mil', 'inch'):
            with self.subTest(units=units):
                current = document
                for _ in range(3):
                    current, _ = reopen(current, units=units)
                    actual = signature(current.one(PATH+'/Part'))
                    self.assertEqual(actual.keys(), before.keys())
                    for path, value in before.items():
                        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                            self.assertLessEqual(abs(Decimal(str(actual[path]))-Decimal(str(value))), Decimal('1e-28'), path)
                        else:
                            self.assertEqual(actual[path], value, path)

    def test_missing_physical_key_and_unknown_content_fail_without_source_changes(self):
        document = read(source(), report=ConversionReport())
        part = document.one(PATH+'/Part')
        before = model_text(document, preserve=False)
        with self.assertRaisesRegex(PcbError, 'no physical XML key'):
            project_symbol(part, units=XmlUnits('mm'), pad_keys={}, report=ConversionReport())
        self.assertEqual(model_text(document, preserve=False), before)
        part.add('Unmapped', 1)
        with self.assertRaisesRegex(PcbError, 'no PCB DIPXML projection'):
            project_symbol(part, units=XmlUnits('mm'), report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
