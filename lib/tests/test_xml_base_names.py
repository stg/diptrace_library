"""Placed base strings are independent from current labels and cache names."""
import unittest

from lib import ConversionReport, format_capabilities, new_schematic, new_symbol, parse, serialize


def fixture():
    design = new_schematic()
    part = design.one('/Schematic/Components').append(new_symbol('Visible', 'U7'))
    part['BaseName'] = 'OriginalSymbol'
    part['BaseRefDes'] = 'P'
    return design, part


def output(design, format, *, version=None, report=None):
    return serialize(design, format=format, version=version,
                     report=report if report is not None else ConversionReport())


class XmlBaseNameTests(unittest.TestCase):
    def test_missing_placed_xml_fields_do_not_inherit_definition_names(self):
        design, _ = fixture()
        for version in format_capabilities('dchxml', family='schematic').write_versions:
            if version >= 52:
                continue
            with self.subTest(version=version):
                restored = parse(output(design, 'dchxml', version=version))
                part = restored.one('/Schematic/Components/Part')
                self.assertEqual((part['Name'], part['RefDes']), ('Visible', 'U7'))
                self.assertEqual((part['BaseName'], part['BaseRefDes']), ('', ''))
                cached = restored.select('/Schematic/CacheLib/Slots/Slot/Definition/Part')
                self.assertIn('Visible', [item['Name'] for item in cached])

    def test_explicit_current_xml_base_name_is_retained(self):
        design, _ = fixture()
        restored = parse(output(design, 'dchxml', version=52))
        part = restored.one('/Schematic/Components/Part')
        self.assertEqual(part['BaseName'], 'OriginalSymbol')
        self.assertEqual(part['BaseRefDes'], '')
        repeated = parse(output(restored, 'dchxml', version=52))
        self.assertEqual(repeated.one(part.path)['BaseName'], 'OriginalSymbol')

    def test_binary_and_ascii_retain_independent_base_strings(self):
        design, _ = fixture()
        for format, version in (('dch', 46), ('dch', 52), ('asc', 46)):
            with self.subTest(format=format, version=version):
                part = parse(output(design, format, version=version)).one('/Schematic/Components/Part')
                self.assertEqual((part['BaseName'], part['BaseRefDes']), ('OriginalSymbol', 'P'))

    def test_xml_losses_are_reported_without_mutating_the_source(self):
        design, part = fixture()
        control = output(design, 'dch')
        for version in (46, 52):
            report = ConversionReport()
            output(design, 'dchxml', version=version, report=report)
            warnings = {notice.rule for notice in report.warnings}
            self.assertEqual('component-base-name' in warnings, version < 52)
            self.assertIn('component-base-reference', warnings)
        self.assertEqual((part['BaseName'], part['BaseRefDes']), ('OriginalSymbol', 'P'))
        self.assertEqual(output(design, 'dch'), control)

    def test_reconstructable_names_are_info_and_empty_names_are_quiet(self):
        design, part = fixture()
        part['BaseName'], part['BaseRefDes'] = part['Name'], 'U'
        report = ConversionReport()
        output(design, 'dchxml', version=46, report=report)
        infos = {notice.rule for notice in report.infos}
        warnings = {notice.rule for notice in report.warnings}
        self.assertTrue({'component-base-name-default', 'component-base-reference-default'} <= infos)
        self.assertFalse({'component-base-name', 'component-base-reference'} & warnings)
        part['BaseName'], part['BaseRefDes'] = '', ''
        report.clear()
        output(design, 'dchxml', version=46, report=report)
        self.assertFalse(any(notice.rule.startswith('component-base-') for notice in report.notices))


if __name__ == '__main__':
    unittest.main()
