"""Editable definitions describe current facts in each drawing context."""
import unittest

from lib import ConversionReport, new_schematic, parse, serialize
from lib.schematic.model.objects import new_symbol_shape, new_pattern_shape, new_schematic_shape, new_pin
from lib.schematic.tests.test_named_fields import design
from lib.tests.test_cached_properties import sample
from lib.schematic.model.refs import bind_schematic_references


class DrawingSchemaTests(unittest.TestCase):
    def test_drawing_contexts_expose_their_own_fields(self):
        symbol, pattern, sheet = new_symbol_shape(), new_pattern_shape(), new_schematic_shape()
        self.assertEqual([node.schema.name for node in (symbol, pattern, sheet)],
                         ['SymbolDrawing', 'PatternDrawing', 'SheetDrawing'])
        self.assertIn('PenWidth', symbol.schema.fields)
        self.assertNotIn('Width', symbol.schema.fields)
        self.assertIn('Width', pattern.schema.fields)
        self.assertNotIn('PenWidth', pattern.schema.fields)
        self.assertIn('Picture_File', sheet.schema.fields)
        self.assertNotIn('Picture_File', symbol.schema.fields)
        for node in (symbol, pattern, sheet):
            self.assertNotIn('Name', node.schema.fields)
            self.assertNotIn('Orientation', node.schema.fields)
            self.assertEqual(node.schema.field('TextAngle').unit, 'radians')
            for name, field in node.schema.fields.items():
                if field.required and field.getter is None:
                    self.assertIn(name, node, (node.schema.name, name))
            with self.assertRaises(KeyError):
                node['Orientation'] = 1

    def test_output_only_component_and_pad_fields_are_not_editable_facts(self):
        doc = design()
        part = doc.one('/Schematic/Components/Part')
        self.assertEqual(part.schema.field('Angle').unit, 'degrees')
        for name in ('Orientation', 'FieldIndex1', 'FieldIndex2', 'TextAlign'):
            self.assertNotIn(name, part.schema.fields)
            with self.assertRaises(KeyError):
                part[name] = 0
        pad = part.one('Pattern/Pads/Pad[1]')
        for name in ('Number', 'Inverted', 'PadWidth', 'PadHeight', 'PadShape', 'CustomSwell', 'CustomShrink'):
            self.assertNotIn(name, pad.schema.fields)
        self.assertIn('PadWidth_New', pad.schema.fields)

    def test_imports_choose_definitions_from_ownership(self):
        source = design()
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                doc = parse(serialize(source, format=format, report=ConversionReport()), format=format)
                for drawing in doc.select('//Shape'):
                    owner = drawing.parent.parent
                    expected = {'Part': 'SymbolDrawing', 'Pattern': 'PatternDrawing', 'Schematic': 'SheetDrawing'}[owner.kind]
                    self.assertEqual(drawing.schema.name, expected)

    def test_settings_absent_from_some_formats_are_optional(self):
        doc = new_schematic()
        settings = doc.one('/Schematic/Settings')
        self.assertFalse(settings.schema.field('GridSnap').required)
        self.assertFalse(settings.schema.field('MarkingFontName').required)
        del settings['GridSnap']
        for format in ('dch', 'asc', 'dchxml'):
            serialize(doc, format=format, report=ConversionReport())
        self.assertNotIn('GridSnap', settings)

    def test_pin_construction_supplies_its_declared_font_choice(self):
        for placed in (True, False):
            pin = new_pin(placed=placed)
            self.assertIs(pin['NameFontMono'], False)

    def test_public_library_extensions_are_named_optional_fields(self):
        doc, part = sample()
        part['Datasheet'] = 'symbol reference'
        pin = part.one('Pins').append(new_pin(placed=False))
        pin['SignalDelay'] = 1.25
        pattern = doc.one('//Definition/Pattern')
        pattern['Datasheet'] = 'pattern reference'
        pattern['RefDes'] = 'P'
        pattern['Sided'] = True
        bind_schematic_references(doc)
        restored = parse(serialize(doc, format='dchxml', report=ConversionReport()), format='dchxml')
        cached = restored.one('//Definition/Part')
        self.assertEqual(cached['Datasheet'], 'symbol reference')
        self.assertEqual(cached.one('Pins/Pin')['SignalDelay'], 1.25)
        current = restored.one('//Definition/Pattern')
        self.assertEqual(current['Datasheet'], 'pattern reference')
        self.assertEqual(current['RefDes'], 'P')
        self.assertTrue(current['Sided'])
        for record, name in ((cached, 'Datasheet'), (cached.one('Pins/Pin'), 'SignalDelay'),
                             (current, 'Datasheet'), (current, 'RefDes'), (current, 'Sided')):
            self.assertFalse(record.schema.field(name).required)
