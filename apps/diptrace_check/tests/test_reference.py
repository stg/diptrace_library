"""Reference accuracy is independent from self-consistency and drift."""
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from lib import ConversionReport, new_schematic, new_symbol, parse, read, serialize
from lib.pcb.tests.test_dip_output import configured_document
from apps.diptrace_check.check import check_file, main
from apps.diptrace_check.comparison import compare, compare_ordered
from apps.diptrace_check.reference import source_document, source_rows, source_snapshot


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def pair(self, family='schematic', format='dchxml', version=52, units='mm'):
        if family == 'schematic':
            from lib.schematic import ExportContext
            document = new_schematic()
            part = document.one('/Schematic/Components').append(new_symbol('Resistor', 'R1'))
            part['Value'] = '10k'
            native, native_version = 'dch', 46
        else:
            from lib.pcb import ExportContext
            document = configured_document()
            native, native_version = 'dip', 54
        source = self.root / ('source.'+native)
        source.write_bytes(serialize(document, format=native, version=native_version, report=ConversionReport()))
        original = read(source, report=ConversionReport())
        reference = self.root / 'reference.data'  # Content identifies the format.
        reference.write_bytes(serialize(original, format=format, version=version,
            context=ExportContext(units=units), report=ConversionReport()))
        return source, reference

    def reference_result(self, source, reference, **options):
        result, _ = check_file(source, references=[reference], report=ConversionReport(), **options)
        return result, next(item for lane in result['results'] for item in lane['references'])

    def test_lean_syntax_keeps_all_comparison_facts_including_unknown_fields(self):
        for family, format, version in (('schematic', 'asc', 46), ('schematic', 'dchxml', 52),
                                       ('pcb', 'asc', 53), ('pcb', 'dipxml', 54)):
            with self.subTest(family=family, format=format):
                _, reference = self.pair(family, format, version)
                data = reference.read_bytes()
                if format == 'asc':
                    data += b'\n(Extra_Field "unknown text" 1.2500 (Nested_Scalar "%"))\n'
                else:
                    extension = b'<Extra_Field Flag="unknown"><Nested>1.2500</Nested>tail</Extra_Field>'
                    data = data.rsplit(b'</Source>', 1)[0] + extension + b'</Source>'
                detailed = source_document(data, format=format, family=family, retain_source=True)
                lean = source_document(data, format=format, family=family)
                self.assertEqual(source_snapshot(lean), source_snapshot(detailed))
                self.assertEqual(list(source_rows(lean)), sorted(source_snapshot(lean).items()))
                if format == 'asc':
                    self.assertTrue(any(node.source is not None for node in detailed.root.walk()))
                else:
                    self.assertTrue(any('xml_line' in node.annotations for node in detailed.root.walk()))
                    self.assertFalse(any('xml_line' in node.annotations for node in lean.root.walk()))
                self.assertTrue(all(node.source is None for node in lean.root.walk()))
                self.assertTrue(any('Extra_Field' in path for path in source_snapshot(lean)))

    def test_matching_asc_and_xml_exports_use_their_version_and_units_for_both_families(self):
        for family, format, version in (('schematic', 'asc', 46), ('schematic', 'dchxml', 52),
                                       ('pcb', 'asc', 53), ('pcb', 'dipxml', 54)):
            with self.subTest(family=family, format=format):
                source, reference = self.pair(family, format, version, 'mil')
                before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (source, reference)]
                result, comparison = self.reference_result(source, reference, formats=[format])
                self.assertEqual(comparison['status'], 'clean')
                self.assertEqual(comparison['version'], version)
                self.assertFalse(comparison['model']['counts'])
                self.assertFalse(comparison['serialized']['counts'])
                self.assertEqual(result['results'][0]['version'], version)
                self.assertEqual([(p.read_bytes(), p.stat().st_mtime_ns) for p in (source, reference)], before)

    def test_reference_data_change_is_reported_even_when_our_round_trips_are_stable(self):
        source, reference = self.pair()
        document = read(reference, report=ConversionReport())
        document.one('/Schematic/Components/Part')['Value'] = '22k'
        reference.write_bytes(serialize(document, format='dchxml', version=52, report=ConversionReport()))
        result, comparison = self.reference_result(source, reference, formats=['dchxml'])
        self.assertTrue(result['needs_review'])
        self.assertEqual(comparison['status'], 'review')
        self.assertTrue(comparison['model']['needs_review'])
        self.assertTrue(comparison['serialized']['needs_review'])
        self.assertTrue(all(not step['stability']['needs_review']
                            for step in result['results'][0]['cycles']))

    def test_raw_comparison_exposes_data_a_semantic_reader_ignores(self):
        source, reference = self.pair()
        original = reference.read_bytes()
        reference.write_bytes(original.replace(b'<Source ', b'<Source ProbeUnknown="authored" ', 1))

        def blind_reader(data, **options):
            return parse(data.replace(b' ProbeUnknown="authored"', b''), **options)

        with patch('apps.diptrace_check.reference.parse', side_effect=blind_reader):
            _, comparison = self.reference_result(source, reference, formats=['dchxml'])
        self.assertEqual(comparison['model']['counts'], {})
        self.assertTrue(comparison['serialized']['needs_review'])
        self.assertEqual(comparison['status'], 'review')
        self.assertTrue(any('ProbeUnknown' in item['path'] for item in comparison['serialized']['examples']))

    def test_unimportable_reference_still_has_a_direct_comparison_and_json_report(self):
        source, reference = self.pair()
        reference.write_bytes(reference.read_bytes().replace(b'<Source ', b'<Source ProbeUnknown="authored" ', 1))
        output = self.root/'check.json'
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status = main([str(source), '--format', 'dchxml', '--reference', str(reference), '--json', str(output)])
        self.assertEqual(status, 1)
        result = json.loads(output.read_text())
        comparison = result['results'][0]['references'][0]
        self.assertIsNone(comparison['model'])
        self.assertTrue(comparison['model_error'])
        self.assertTrue(comparison['serialized']['needs_review'])

    def test_multiple_references_infer_formats_and_keep_version_profiles_separate(self):
        source, older = self.pair(version=46)
        older = older.rename(self.root/'older.xml')
        _, newer = self.pair(version=52)
        result, _ = check_file(source, references=[older, newer], report=ConversionReport())
        self.assertEqual([(lane['format'], lane['version']) for lane in result['results']],
                         [('dch', 46), ('dchxml', 46), ('dchxml', 52)])
        self.assertTrue(all(item['status'] == 'clean' for lane in result['results'] for item in lane['references']))

    def test_report_cannot_replace_a_reference_including_a_hard_link_alias(self):
        source, reference = self.pair()
        alias = self.root/'alias.json'
        alias.hardlink_to(reference)
        before = reference.read_bytes()
        for output in (reference, alias):
            with self.subTest(output=output), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main([str(source), '--reference', str(reference), '--json', str(output)])
            self.assertEqual(stopped.exception.code, 2)
            self.assertEqual(reference.read_bytes(), before)

    def test_wrong_family_and_unsupported_reference_version_are_explicit_failures(self):
        source, reference = self.pair('pcb', 'dipxml', 54)
        schematic = self.root/'source.dch'
        schematic.write_bytes(serialize(new_schematic(), format='dch', report=ConversionReport()))
        with self.assertRaisesRegex(ValueError, 'reference family'):
            check_file(schematic, references=[reference], report=ConversionReport())
        reference.write_bytes(reference.read_bytes().replace(b'4.3.0.5', b'4.3.0.3'))
        with self.assertRaisesRegex(ValueError, 'no output schema'):
            check_file(source, references=[reference], report=ConversionReport())

    def test_explicit_version_must_match_the_reference(self):
        source, reference = self.pair(version=52)
        with self.assertRaisesRegex(ValueError, 'does not match reference'):
            check_file(source, formats=['dchxml'], version=46, references=[reference], report=ConversionReport())

    def test_format_aliases_do_not_repeat_the_same_conversion(self):
        source, reference = self.pair()
        result, _ = check_file(source, formats=['.DCHXML', 'dchxml'], references=[reference], report=ConversionReport())
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(len(result['results'][0]['references']), 1)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status = main([str(source), '--format', '.DCHXML', '--format', 'dchxml',
                           '--version', '52', '--reference', str(reference)])
        self.assertIn(status, (0, 1))


class SourceComparisonTests(unittest.TestCase):
    def facts(self, text):
        return source_snapshot(source_document(text.encode(), format='dchxml', family='schematic'))

    def test_streamed_paths_keep_lexical_ordinals_attributes_arguments_and_unknown_content(self):
        bodies = (
            ('asc', (b'(Repeated '+b' '.join(str(i).encode() for i in range(12))+b') ')*12),
            ('dchxml', b'<Source Type="DipTrace-Schematic" Version="5.3.5.1" Units="mm">'
             b'<!-- note --><Comment>authored</Comment><?probe preserved?>'
             + b'<Repeated unknown="yes">before<Nested/>after</Repeated>'*12 + b'</Source>'))
        for format, data in bodies:
            with self.subTest(format=format):
                document = source_document(data, format=format, family='schematic')
                expected = source_snapshot(document)
                rows = list(source_rows(document))
                self.assertEqual(rows, sorted(expected.items()))
                self.assertEqual(len(rows), len(dict(rows)))
                self.assertEqual(compare_ordered(iter(rows), iter(rows), tolerance=0)['counts'], {})
                self.assertTrue(any('[12]' in key for key, value in rows))
                if format == 'asc':
                    self.assertTrue(any(key.endswith('/@10') for key, value in rows))
                else:
                    self.assertTrue(any(value[2] == 'authored' for key, value in rows))

    def test_xml_attribute_order_indentation_comments_and_numeric_spelling_are_ignored(self):
        a = '<Source Type="DipTrace-Schematic" Version="5.3.5.1" Units="mm"><Point X="1.00" Y="2"/></Source>'
        b = '<Source Units="mm" Version="5.3.5.1" Type="DipTrace-Schematic">\n<!-- note -->\n<Point Y="2.0" X="1"/>\n</Source>'
        self.assertEqual(self.facts(a), self.facts(b))

    def test_empty_records_and_child_order_remain_visible(self):
        prefix = '<Source Type="DipTrace-Schematic" Version="5.3.5.1" Units="mm">'
        a = self.facts(prefix+'<First/><Second/></Source>')
        for body in ('<First/>', '<Second/><First/>'):
            with self.subTest(body=body):
                self.assertTrue(compare(a, self.facts(prefix+body+'</Source>'), tolerance=0)['needs_review'])

    def test_reference_tolerance_does_not_hide_integer_changes(self):
        before = {'id': ('serialized-number', '', 1), 'x': ('serialized-number', '', Decimal('1.0'))}
        after = {'id': ('serialized-number', '', 2), 'x': ('serialized-number', '', Decimal('1.001'))}
        result = compare(before, after, tolerance=Decimal('.01'))
        self.assertEqual(result['counts'], {'data': 1, 'rounding': 1})

    def test_top_level_asc_record_order_remains_visible(self):
        before = source_snapshot(source_document(b'(First) (Second)', format='asc', family='schematic'))
        after = source_snapshot(source_document(b'(Second) (First)', format='asc', family='schematic'))
        self.assertTrue(compare(before, after, tolerance=0)['needs_review'])


if __name__ == '__main__':
    unittest.main()
