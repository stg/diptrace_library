"""Standalone XML output retains authoring facts and adapts a detached view."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from lib.common.conversion import ConversionReport
from lib.common.errors import UnsupportedFileError
from lib.pattern.formats.lib.read import parse as read_binary
from lib.pattern.formats.libxml.read import parse
from lib.pattern.formats.libxml.write import dumps
from lib.pattern.model import new_library, new_pattern
from lib.pattern.tests.comparison import snapshot, assert_equivalent


FIXTURES = Path(__file__).with_name('fixtures')


class PatternXmlWriteTests(unittest.TestCase):
    assert_equivalent = assert_equivalent

    def test_sparse_catalogue_keys_use_number_while_selections_use_index(self):
        document = new_library()
        library = document.one('/Library')
        category = library.one('Categories').add('Category','Analog',7)
        kind = category.add('Type','Amplifier',11)
        kind.add('Subtype','Low noise',23)
        pattern = library.one('Patterns').append(new_pattern('Example'))
        pattern['Pattern_CategoryName'],pattern['Pattern_CategoryIndex'] = 'Analog',7
        pattern.one('Pattern_CategoryTypes').add('CategoryType','Amplifier','Low noise',11,23)
        before = snapshot(document)
        for version in ('4.3.0.5','4.9.5.0','5.2.0.1','5.3.5.1'):
            with self.subTest(version=version):
                text = dumps(document,version=version)
                root = ET.fromstring(text)
                for path, key in (('Categories/Category',7),
                                  ('Categories/Category/Types/Type',11),
                                  ('Categories/Category/Types/Type/SubTypes/SubType',23)):
                    self.assertEqual({'Number':str(key)},root.find(path).attrib)
                self.assertEqual('7',root.find('Patterns/Pattern/Category').get('Index'))
                self.assert_equivalent(before,parse(text))
        self.assertEqual(before,snapshot(document))

    def test_geometry_and_reordered_relationships_survive_in_each_unit(self):
        document = read_binary((FIXTURES/'geometry.lib').read_bytes())
        pattern = document.one('/Library/Patterns/Pattern')
        pattern.one('Pads/Pad[2]').move_to(pattern.one('Pads'), index=0)
        before = snapshot(document)
        for units in ('mm', 'mil', 'inch'):
            with self.subTest(units=units):
                output = parse(dumps(document, units=units))
                self.assert_equivalent(before, output)
                pattern = output.one('/Library/Patterns/Pattern')
                self.assertIs(pattern.one('Pads/Pad[1]'), pattern.one('Shapes/Shape')['Pad'])
                self.assertIs(pattern.one('Pattern_Groups/pt'), pattern.one('Pads/Pad[2]')['Group'])
                output.validate()
        self.assertEqual(before, snapshot(document))

    def test_text_supplier_and_model_vectors_keep_current_values(self):
        document = read_binary((FIXTURES/'metadata.lib').read_bytes())
        before = snapshot(document)
        output = parse(dumps(document))
        self.assert_equivalent(before, output)
        text = output.one('/Library/Patterns/Pattern/Shapes/Shape')
        self.assertEqual((7.25, True), (text['FontSize'], text['FontMono']))
        self.assertEqual('Demo-456', output.one('/Library/Patterns/Pattern/Suppliers')['PartNumber'])

    def test_older_fonts_report_projection_without_changing_current_data(self):
        document = read_binary((FIXTURES/'metadata.lib').read_bytes())
        text = document.one('/Library/Patterns/Pattern/Shapes/Shape')
        text['FontWidth'] = .6
        before = snapshot(document)
        for version in ('4.3.0.5', '4.9.5.0', '5.2.0.1', '5.3.5.1'):
            with self.subTest(version=version):
                report = ConversionReport()
                output = parse(dumps(document, version=version, units='inch', report=report))
                shape = output.one('/Library/Patterns/Pattern/Shapes/Shape')
                self.assertAlmostEqual(.6, shape['FontWidth'], places=4)
                current = version == '5.3.5.1'
                self.assertEqual((7.25 if current else 7, current), (shape['FontSize'], shape['FontMono']))
                expected = set() if current else {'fractional-font-size', 'monospaced-font'}
                if version == '4.3.0.5':
                    expected.add('drawing-pad-reference')
                    self.assertIsNone(shape['Pad'])
                else:
                    self.assertIsNotNone(shape['Pad'])
                self.assertEqual(expected, {item.rule for item in report.warnings})
        self.assertEqual(before, snapshot(document))

    def test_empty_and_multiple_libraries_with_explicit_empty_template_values(self):
        document = new_library('Examples', hint='Independent Unicode \u03bc examples')
        self.assertFalse(parse(dumps(document)).select('/Library/Patterns/Pattern'))
        for name in ('First', 'Second'):
            pattern = new_pattern(name)
            pattern['Value'], pattern['RefDes'] = '', ''
            document.one('/Library/Patterns').append(pattern)
        output = parse(dumps(document))
        self.assertEqual(['First', 'Second'], [p['Name'] for p in output.select('/Library/Patterns/Pattern')])
        self.assertEqual(['', ''], [p['Value'] for p in output.select('/Library/Patterns/Pattern')])
        self.assertEqual(document.one('/Library')['Hint'], output.one('/Library')['Hint'])

    def test_legacy_custom_pad_uses_an_independent_style(self):
        document = read_binary((FIXTURES/'metadata.lib').read_bytes())
        pad = document.one('/Library/Patterns/Pattern/Pads/Pad[1]')
        pad['Standard'] = False
        output = dumps(document, version='4.3.0.5', report=ConversionReport())
        syntax = ET.fromstring(output)
        pattern = syntax.find('Patterns/Pattern')
        self.assertNotEqual(pattern.find('DefPad').get('Style'), pattern.find('Pads/Pad').get('Style'))
        self.assertFalse(parse(output).one('/Library/Patterns/Pattern/Pads/Pad[1]')['Standard'])

    def test_unsupported_version_and_unmapped_data_fail_explicitly(self):
        report = ConversionReport()
        with self.assertRaises(UnsupportedFileError) as caught:
            dumps(new_library(), version='9.0.0.0', report=report)
        self.assertEqual(('pattern', 'libxml', 'version'),
                         (caught.exception.family, caught.exception.format, caught.exception.reason))
        self.assertEqual(1, len(report.errors))
        document = new_library()
        document.one('/Library').add('UnknownData', 'Keep this')
        with self.assertRaises(NotImplementedError):
            dumps(document)


if __name__ == '__main__':
    unittest.main()
