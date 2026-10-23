"""Footprint names are editable text, not ownership or content filters."""
from decimal import Decimal
import unittest
import xml.etree.ElementTree as ET

from lib.design import ExportReport, new_schematic, parse
from lib.design.asc_import_graphics import empty_pad
from lib.design.schematic_objects import new_pattern_shape, new_pin, new_symbol
from lib.design.schematic_refs import bind_schematic_references


PATTERN = '/Schematic/Components/Part/Pattern'


def source():
    current = new_schematic()
    part = current.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
    part.one('Pins').append(new_pin())
    part.one('Pins/Pin').set_field('Number', 1)
    pattern = part.one('Pattern')
    pattern.set_field('Name_Description', 'Unnamed edited footprint')
    pattern.set_field('Pattern_Manufacturer', 'Example')
    pattern.set_field('Width', 12)
    pattern.set_field('Height', 6)
    pattern.set_field('OriginX', Decimal('.5'))
    pattern.one('Model3D').set_field('Model3DFile', 'body.step')
    for index, x in ((1, -2), (2, 2)):
        pad = pattern.one('Pads').insert(empty_pad(index), index)
        pad.annotations.clear()
        pad.set_values(index, str(index), '', x, 0)
        for name, value in (('Number_New', index), ('PadWidth_New', 1), ('PadHeight_New', 2)):
            pad.set_field(name, value)
    drawing = pattern.one('Shapes').insert(new_pattern_shape(1, kind=1), 1)
    drawing.one('Points_New').add('pt', -6, -3)
    drawing.one('Points_New').add('pt', 6, 3)
    bind_schematic_references(current)
    return current


def facts(pattern):
    return (pattern.values[0], pattern.scalar('Name_Description'), pattern.scalar('Pattern_Manufacturer'),
            pattern.scalar('OriginX'), pattern.one('Model3D').scalar('Model3DFile'),
            [(pad.values[1], pad.values[3:], pad.scalar('PadWidth_New'), pad.scalar('PadHeight_New'))
             for pad in pattern.select('Pads/Pad')[1:-1]],
            [point.values for point in pattern.select('Shapes/Shape[2]/Points_New/pt')])


class UnnamedPatternTests(unittest.TestCase):
    def test_no_pad_domain_keeps_unused_pin_numbers_literal_regardless_of_name(self):
        for name in ('', 'No pads'):
            current = new_schematic()
            part = current.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
            part.one('Pattern').set_values(name)
            pin = part.one('Pins').append(new_pin())
            pin.set_field('Number', 5)
            bind_schematic_references(current)
            self.assertEqual(current.references.issues, [])
            self.assertEqual(current.references.outgoing(part, role='symbol-pin-pad'), [])
            for destination in ('dch', 'asc', 'dchxml'):
                with self.subTest(name=name, destination=destination):
                    loaded = parse(getattr(current, 'to_'+destination+'_bytes')(report=ExportReport()), format=destination)
                    self.assertEqual(loaded.references.issues, [])
                    self.assertEqual(loaded.one('/Schematic/Components/Part/Pins/Pin').scalar('Number'), 5)

    def test_unnamed_geometry_and_settings_survive_every_format_pair(self):
        original = source()
        expected = facts(original.one(PATTERN))
        for first in ('dch', 'asc', 'dchxml'):
            current = parse(getattr(original, 'to_'+first+'_bytes')(report=ExportReport()), format=first)
            for second in ('dch', 'asc', 'dchxml'):
                with self.subTest(first=first, second=second):
                    converted = parse(getattr(current, 'to_'+second+'_bytes')(report=ExportReport()), format=second)
                    self.assertEqual(facts(converted.one(PATTERN)), expected)
                    pin = converted.one('/Schematic/Components/Part/Pins/Pin')
                    assignment = converted.references.outgoing(pin.parent.parent, role='symbol-pin-pad')
                    self.assertEqual(len(assignment), 1)
                    self.assertIs(assignment[0].target, converted.one(PATTERN+'/Pads/Pad[2]'))
        self.assertEqual(facts(original.one(PATTERN)), expected)

    def test_clearing_the_name_does_not_change_definition_content(self):
        current = source()
        pattern = current.one(PATTERN)
        pattern.set_values('Before')
        loaded = parse(current.to_dchxml_bytes(), format='dchxml')
        pattern = loaded.one(PATTERN)
        pattern.set_values('')
        expected = facts(pattern)
        for _ in range(3):
            data = loaded.to_dchxml_bytes()
            loaded = parse(data, format='dchxml')
            self.assertEqual(facts(loaded.one(PATTERN)), expected)
            self.assertEqual(loaded.to_dchxml_bytes(), data)

    def test_equal_names_do_not_merge_different_placed_and_cached_patterns(self):
        current = source()
        part = current.one('/Schematic/Components/Part')
        slot = current.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
        slot.add('VariablePath', '')
        definition = slot.add('Definition', 0)
        definition.append(new_symbol('Cached device', '', placed=False))
        cached = definition.append(part.one('Pattern').clone())
        cached.set_field('Name_Description', 'Independent definition')
        bind_schematic_references(current)
        tree = ET.fromstring(current.to_dchxml_bytes())
        patterns = tree.findall('Library/Library/Patterns/Pattern')
        self.assertEqual(len(patterns), 2)
        self.assertEqual({p.findtext('Name', '') for p in patterns}, {''})
        loaded = parse(ET.tostring(tree), format='dchxml')
        self.assertEqual(loaded.one(PATTERN).scalar('Name_Description'), 'Unnamed edited footprint')
        self.assertIn('Independent definition', [p.scalar('Name_Description')
                      for p in loaded.select('/Schematic/CacheLib/Slots/Slot/Definition/Pattern')])

    def test_missing_name_value_is_invalid_instead_of_silently_omitting_the_pattern(self):
        current = source()
        current.one(PATTERN).set_values()
        report = ExportReport()
        with self.assertRaisesRegex(ValueError, 'requires one name string'):
            current.to_dchxml_bytes(report=report)
        self.assertEqual(len(report.errors), 1)


if __name__ == '__main__':
    unittest.main()
