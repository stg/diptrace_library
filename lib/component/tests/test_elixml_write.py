"""Standalone XML output shares symbol, pad and physical identity projections."""
from pathlib import Path
import unittest

from lib.common.conversion import ConversionReport
from lib.common.errors import UnsupportedFileError
from lib.component.formats.elixml.read import parse
from lib.component.formats.elixml.write import dumps
from lib.component.formats.eli.read import parse as parse_binary
from lib.component.model import new_library, new_component, new_part, new_group
from .test_asc_read import facts

FIXTURES = Path(__file__).with_name('fixtures')


class ComponentXmlWriteTests(unittest.TestCase):
    def assertFacts(self, before, after):
        self.assertEqual(before.keys(), after.keys())
        for key, value in before.items():
            if isinstance(value, float):
                self.assertAlmostEqual(value, after[key], delta=1e-9, msg=key)
            else:
                self.assertEqual(value, after[key], key)

    def test_parameters_and_links_match_current_binary_data(self):
        for name in ('parameters.eli', 'multipart_33.eli', 'connections_33.eli'):
            with self.subTest(input=name):
                document = parse_binary((FIXTURES/name).read_bytes())
                before = facts(document)
                result = parse(dumps(document, report=ConversionReport()))
                self.assertFacts(before, facts(result))
                self.assertEqual(before, facts(document))
                result.validate()

    def test_group_and_absent_organization_spelling_matches_receiver_profiles(self):
        from lib.component.formats.elixml.write import project_document
        document = parse_binary((FIXTURES/'parameters.eli').read_bytes())
        component = document.one('/Library/Components/Component')
        part = component.one('Parts/Part')
        group = part.one('Groups').append(new_group())
        for pin in part.select('Pins/Pin'):
            pin['Group'] = group
        for version in ('4.3.0.5', '4.9.5.0', '5.3.5.1'):
            with self.subTest(version=version):
                plan = project_document(document, version=version, report=ConversionReport())
                part = plan.child('Components').child('Component').child('Part')
                row = part.child('Groups').child('Group')
                self.assertEqual(version=='5.3.5.1', 'Enabled' in dict(row.attributes))
                self.assertEqual(version!='5.3.5.1', 'SubFolderIndex' in dict(part.attributes))
                physical = plan.child('Library').child('Patterns').child('Pattern')
                self.assertEqual(version!='5.3.5.1', physical.child('Category') is not None)

    def test_text_does_not_acquire_an_inactive_geometric_line_width(self):
        document = parse_binary((FIXTURES/'text_33.eli').read_bytes())
        for shape in document.select('/Library/Components/Component/Parts/Part/Shapes/Shape'):
            self.assertIsNone(shape.child('PenWidth'))
        result = parse(dumps(document))
        self.assertFacts(facts(document), facts(result))

    def test_authored_symbol_text_stays_independent_of_descriptions(self):
        document = parse((FIXTURES/'text_input.elixml').read_bytes())
        component = document.one('/Library/Components/Component')
        component['Name'] = 'New description'
        before = facts(document)
        result = parse(dumps(document))
        self.assertFacts(before, facts(result))
        self.assertTrue(all(row['Text'].startswith('Authored-') for row in result.select(
            '/Library/Components/Component/Parts/Part/Shapes/Shape/TextLine/pt')))

    def test_connections_groups_and_reordered_pads_use_current_targets(self):
        document = parse((FIXTURES/'connections_input.elixml').read_bytes())
        component = document.one('/Library/Components/Component')
        part = component.select('Parts/Part')[0]
        group = part.one('Groups').append(new_group())
        part.select('Pins/Pin')[0]['Group'] = group
        pads = component.select('Pattern/Pads/Pad')
        pads[1].move_to(component.one('Pattern/Pads'), index=0)
        before = facts(document)
        result = parse(dumps(document))
        self.assertFacts(before, facts(result))

    def test_previous_profiles_project_sizes_and_links_with_warnings(self):
        document = parse_binary((FIXTURES/'parameters.eli').read_bytes())
        before = facts(document)
        for version in ('4.3.0.5', '4.9.5.0'):
            with self.subTest(version=version):
                report = ConversionReport()
                result = parse(dumps(document, version=version, report=report))
                pin = result.select('/Library/Components/Component/Parts/Part/Pins/Pin')[0]
                self.assertEqual((3, False), (pin['NameFontSize'], pin['NameFontMono']))
                shape = result.one('/Library/Components/Component/Pattern/Shapes/Shape')
                self.assertEqual(7, shape['FontSize'])
                self.assertEqual(-1 if version=='4.3.0.5' else 2, shape['PadId'])
                rules = {notice.rule for notice in report.warnings}
                self.assertIn('fractional-font-size', rules)
                self.assertIn('monospaced-font', rules)
                self.assertEqual(version=='4.3.0.5', 'drawing-pad-reference' in rules)
                self.assertEqual(before, facts(document))

    def test_verification_and_extra_supplier_content_are_reported(self):
        document = parse_binary((FIXTURES/'parameters.eli').read_bytes())
        component = document.one('/Library/Components/Component')
        component.one('Parts/Part')['Verification'] = (True,)*7
        component.one('Suppliers')['SourceLocator'] = 'https://example.invalid/offer'
        report = ConversionReport()
        result = parse(dumps(document, report=report))
        self.assertEqual((False,)*7, result.one('/Library/Components/Component/Parts/Part')['Verification'])
        self.assertEqual({'supplier-details','symbol-verification'}, {notice.rule for notice in report.warnings})
        self.assertEqual('https://example.invalid/offer', component.one('Suppliers')['SourceLocator'])

    def test_empty_unattached_and_unicode_content(self):
        document = new_library('Examples Ω')
        self.assertEqual([], parse(dumps(document)).select('/Library/Components/Component'))
        component = document.one('/Library/Components').append(new_component('Example', 'U'))
        component.one('Parts').append(new_part('Gate B'))
        result = parse(dumps(document))
        self.assertEqual(2, len(result.select('/Library/Components/Component/Parts/Part')))
        self.assertEqual([], result.select('/Library/Components/Component/Pattern'))
        self.assertEqual('Examples Ω', result.one('/Library')['Name'])

    def test_units_and_repeated_round_trips_do_not_accumulate_drift(self):
        document = parse((FIXTURES/'parameters_input.elixml').read_bytes())
        before = facts(document)
        for units in ('mm', 'inch', 'mil'):
            with self.subTest(units=units):
                result = document
                for _ in range(8):
                    result = parse(dumps(result, units=units))
                self.assertFacts(before, facts(result))
        self.assertEqual(before, facts(document))

    def test_unverified_profile_and_invalid_xml_characters_fail(self):
        document = new_library()
        with self.assertRaises(UnsupportedFileError):
            dumps(document, version='5.2.0.1')
        document.one('/Library')['Name'] = 'Invalid\x01text'
        report = ConversionReport()
        with self.assertRaises(ValueError):
            dumps(document, report=report)
        self.assertEqual(1, len(report.errors))


if __name__ == '__main__':
    unittest.main()
