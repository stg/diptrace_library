"""SPICE model text uses flat ASC strings and shared editable Line records."""
import unittest

from lib.design import ExportReport, new_schematic, parse_dch, parse_dchxml
from lib.design.schematic_objects import new_pattern, new_symbol
from lib.design.schematic_refs import bind_schematic_references


LINES = ('.SUBCKT Buffer IN OUT', '', 'R1 IN OUT 10k', '.ENDS Buffer', '')


def source():
    document = new_schematic()
    part = document.one('/Schematic/Components').append(new_symbol('Buffer', 'U1'))
    slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
    slot.add('VariablePath', '')
    definition = slot.add('Definition', 0)
    cached = definition.append(new_symbol('Buffer', 'U', placed=False))
    definition.append(new_pattern())
    for symbol in (part, cached):
        symbol.set_field('ModelType', 1)
        for text in LINES:
            symbol.one('ModelBody').add('Line', text)
    bind_schematic_references(document)
    return parse_dch(document.to_dch_bytes())


class ModelBodyTests(unittest.TestCase):
    def test_flat_asc_spelling_preserves_model_lines_and_blank_entries(self):
        document = source()
        before = document.to_dch_bytes()
        raw = document.as_asc(report=ExportReport())
        bodies = raw.select('//ModelBody') + raw.select('//cl_ModelBody')
        self.assertEqual(len(bodies), 2)
        for body in bodies:
            self.assertEqual(body.values, LINES)
            self.assertEqual(body.children(), [])
        text = raw.to_asc_bytes().decode('cp1252')
        self.assertIn('(ModelBody\r\n        ".SUBCKT Buffer IN OUT"\r\n        ""', text)
        self.assertIn('(cl_ModelBody\r\n            ".SUBCKT Buffer IN OUT"\r\n            ""', text)
        imported = raw.as_schematic()
        for body in imported.select('//ModelBody'):
            self.assertEqual(tuple(line.values[0] for line in body.children('Line')), LINES)
        self.assertEqual(imported.to_asc_bytes(report=ExportReport()).decode('cp1252'), text)
        self.assertEqual(document.to_dch_bytes(), before)

    def test_model_text_survives_repeated_shared_format_cycles(self):
        document = source()
        stable = None
        for _ in range(3):
            document = document.as_asc(report=ExportReport()).as_schematic()
            document = parse_dchxml(document.to_dchxml_bytes(report=ExportReport())).as_schematic()
            document = parse_dch(document.to_dch_bytes(report=ExportReport()))
            bodies = document.select('//ModelBody')
            self.assertEqual(len(bodies), 2)
            for body in bodies:
                self.assertEqual(tuple(line.values[0] for line in body.children('Line')), LINES)
            output = document.to_dch_bytes()
            if stable is None:
                stable = output
            self.assertEqual(output, stable)

    def test_invalid_mixed_asc_body_is_rejected_without_losing_text(self):
        raw = source().as_asc(report=ExportReport())
        body = raw.one('/Schematic/Components/Part/ModelBody')
        body.add('Line', 'Ambiguous extra text')
        with self.assertRaisesRegex(ValueError, 'flat model text strings'):
            raw.as_schematic()
        self.assertEqual(body.values, LINES)
        self.assertEqual(body.one('Line').values, ('Ambiguous extra text',))


if __name__ == '__main__':
    unittest.main()
