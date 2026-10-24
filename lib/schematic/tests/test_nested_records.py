"""Nested model fields and derived terminal counts support ordinary data edits."""
import unittest

from lib import ConversionReport, Element, new_schematic, parse, serialize
from lib.schematic.model.refs import bind_schematic_references
from lib.schematic.model.new import fields
from lib.tests.test_cached_properties import sample
from lib.tests.test_route_import import source


class NestedRecordTests(unittest.TestCase):
    def test_page_zone_border_sizes_accept_fractional_lengths(self):
        doc = new_schematic()
        page = doc.one('/Schematic/Pages/Page')
        page['HorzZoneBorder'] = 0.75
        page['VertZoneBorder'] = 1.5
        self.assertEqual(page.schema.field('HorzZoneBorder').unit, 'shared length')
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                loaded = parse(serialize(doc, format=format), format=format)
                current = loaded.one('/Schematic/Pages/Page')
                self.assertEqual(current['HorzZoneBorder'], 0.75)
                self.assertEqual(current['VertZoneBorder'], 1.5)

    def test_wire_points_and_lines_have_named_fields(self):
        doc = source()
        line = doc.one('/Schematic/Nets/Net/Lines/Line')
        point = line.one('Points/pt[1]')
        point['X'] = 12
        point['Dir'] = -1
        line['Selected'] = True
        self.assertEqual(point.values, (12, 0, -1))
        self.assertIs(doc.one('//pt[X=12]'), point)
        self.assertTrue(all(isinstance(item, Element) for item in point.items))
        self.assertEqual(point.schema.field('X').unit, 'shared length')
        with self.assertRaises(TypeError):
            point['Dir'] = 0.5
        self.assertEqual(point['Dir'], -1)

    def test_classification_and_catalog_keys_are_not_collection_positions(self):
        doc, part = sample()
        cache = doc.one('/Schematic/CacheLib')
        entry = cache.one('Categories').add('Category', 'Analog', 40)
        entry.add('Type', 'Amplifier', 70).add('Subtype', 'Precision', 110)
        row = part.one('Component_CategoryTypes').add('CategoryType', 'Amplifier', 'Precision', 70, 110)
        part.set_field('Component_CategoryName', 'Analog')
        part.set_field('Component_CategoryIndex', 40)
        bind_schematic_references(doc)
        self.assertEqual(entry['Index'], 40)
        self.assertEqual(row['TypeIndex'], 70)
        row['SubType'] = 'Low noise'
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                loaded = parse(serialize(doc, format=format, report=ConversionReport()), format=format)
                current = loaded.one('//Definition/Part/Component_CategoryTypes/CategoryType')
                self.assertEqual(current['Type'], 'Amplifier')
                self.assertEqual(current['SubType'], 'Low noise')

    def test_terminal_counts_follow_current_children_without_an_independent_value(self):
        doc, _ = sample()
        pattern = doc.one('//Definition/Pattern')
        terminal = pattern.add('PadTerminal', 0)
        fields(terminal, Type=1, X=0, Y=0, Angle=15, ShapeWidth=3, ShapeHeight=2, ShapeCorner=0)
        terminal.add('ShapePoints')
        bind_schematic_references(doc)
        self.assertEqual(pattern['PadTerminalCount'], 1)
        self.assertIsNone(pattern.child('PadTerminalCount'))
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                loaded = parse(serialize(doc, format=format), format=format)
                current = loaded.one('//Definition/Pattern')
                self.assertEqual(current['PadTerminalCount'], 1)
                self.assertEqual(current.one('PadTerminal')['Angle'], 15)
                self.assertIsNone(current.child('PadTerminalCount'))
        other = pattern.append(terminal.clone())
        self.assertEqual(pattern['PadTerminalCount'], 2)
        self.assertEqual(other['Index'], 1)
        terminal.detach()
        self.assertEqual(pattern['PadTerminalCount'], 1)
        self.assertEqual(other['Index'], 0)
        with self.assertRaises(TypeError):
            pattern['PadTerminalCount'] = 5

    def test_global_user_field_display_choices_are_named(self):
        doc = new_schematic()
        row = doc.one('/Schematic/ShowUserfield_Global').add('pt', 'Supplier', 'Vendor', 1, 2)
        bind_schematic_references(doc)
        row['Show'] = 2
        row['Align'] = 3
        for format in ('dch', 'asc', 'dchxml'):
            loaded = parse(serialize(doc, format=format), format=format)
            choice = loaded.one('/Schematic/ShowUserfield_Global/pt')
            self.assertEqual((choice['Name'], choice['Value'], choice['Show'], choice['Align']),
                             ('Supplier', 'Vendor', 2, 3))
