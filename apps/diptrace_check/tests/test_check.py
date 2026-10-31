"""Exercise a real file and the distinction between quantization and drift."""
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib import FormatCapabilities, UnsupportedFileError, new_schematic, serialize
from apps.diptrace_check.check import check_file, main
from apps.diptrace_check.comparison import compare


class CheckTests(unittest.TestCase):
    def test_tolerance_never_hides_integer_settings_text_or_reference_changes(self):
        before = {'count': ('integer', '', 1), 'text': ('text', '', 'A'),
                  'link': ('reference', '', '/A'), 'x': ('number', 'shared length', 0)}
        after = {'count': ('integer', '', 2), 'text': ('text', '', 'B'),
                 'link': ('reference', '', '/B'), 'x': ('number', 'shared length', Decimal('.0001'))}
        result = compare(before, after, tolerance=Decimal(10))
        self.assertEqual(result['counts'], {'data': 3, 'rounding': 1})
        self.assertTrue(result['needs_review'])

    def simulated(self, positions):
        def model(x):
            return SimpleNamespace(x=Decimal(x), references=SimpleNamespace(validate=lambda: None))
        original = model('0')
        rebuilt = [model(x) for x in positions]
        capabilities = FormatCapabilities('asc', 'schematic', (1,), (1,), 1)
        with patch('apps.diptrace_check.check.read', return_value=original), \
             patch('apps.diptrace_check.check.document_family', return_value='schematic'), \
             patch('apps.diptrace_check.check.format_capabilities', return_value=capabilities), \
             patch('apps.diptrace_check.check.serialize', return_value=b'file'), \
             patch('apps.diptrace_check.check.parse', side_effect=rebuilt), \
             patch('apps.diptrace_check.check.snapshot', side_effect=lambda d: {'x': ('number', '', d.x)}):
            return check_file('unused', formats=['asc'], tolerance=Decimal('.001'))[0]

    def test_first_quantization_followed_by_stable_saves_is_rounding(self):
        result = self.simulated(['.0004', '.0004', '.0004'])
        self.assertEqual(result['results'][0]['status'], 'rounding')
        self.assertFalse(result['needs_review'])

    def test_small_changes_cannot_fill_the_examples_and_hide_a_data_change(self):
        before = {f'a{i}': ('number', 'shared length', 0) for i in range(30)}
        after = {name: ('number', 'shared length', Decimal('.0001')) for name in before}
        after['z'] = ('text', '', 'new data')
        result = compare(before, after, tolerance=Decimal('.001'), examples=2)
        self.assertEqual(result['examples'][0]['path'], 'z')
        self.assertTrue(result['needs_review'])

    def test_numeric_maxima_keep_length_and_angle_domains_separate(self):
        before = {'x': ('number', 'shared length', 0), 'angle': ('number', 'radians', 0)}
        after = {'x': ('number', 'shared length', Decimal('.0001')),
                 'angle': ('number', 'radians', Decimal('.0002'))}
        result = compare(before, after, tolerance=Decimal('.001'))
        self.assertEqual(result['maximum_numeric_delta_by_unit'],
                         {'shared length': Decimal('.0001'), 'radians': Decimal('.0002')})

    def test_small_but_accumulating_movement_is_drift(self):
        result = self.simulated(['.0001', '.0002', '.0003'])
        self.assertEqual(result['results'][0]['status'], 'drift')
        self.assertTrue(result['needs_review'])
        self.assertEqual(result['results'][0]['cycles'][-1]['stability']['maximum_numeric_delta_by_unit'],
                         {'unspecified model units': Decimal('.0002')})

    def test_real_cli_preserves_the_input_and_writes_a_machine_readable_report(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source, output = Path(directory)/'design.dch', Path(directory)/'check.json'
            data = serialize(new_schematic(), format='dch')
            source.write_bytes(data)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                status = main([str(source), '--json', str(output)])
            self.assertEqual(status, 0)
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['family'], 'schematic')
            self.assertEqual(len(result['results'][0]['cycles']), 3)
            self.assertEqual(source.read_bytes(), data)

    def test_each_public_schematic_format_can_be_selected_without_a_version_table(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory)/'design.dch'
            source.write_bytes(serialize(new_schematic(), format='dch'))
            result, report = check_file(source, formats=['dch', 'asc', 'dchxml'])
            self.assertEqual([r['format'] for r in result['results']], ['dch', 'asc', 'dchxml'])
            # Other formats can materialize defaults (for example active-sheet
            # selection). Report these initial changes, while requiring later
            # saves to be stable; do not disguise them as numerical rounding.
            self.assertTrue(all(not step['stability']['needs_review']
                for lane in result['results'] for step in lane['cycles'][1:]))

    def test_unavailable_family_uses_the_library_failure(self):
        errors = io.StringIO()
        error = UnsupportedFileError('PCB support is unavailable', family='pcb', reason='family')
        with patch('apps.diptrace_check.check.read', side_effect=error), redirect_stderr(errors):
            self.assertEqual(main(['design.dip']), 1)
        self.assertIn('PCB support is unavailable', errors.getvalue())

    def test_invalid_cycles_and_input_report_collision_are_usage_errors(self):
        for arguments in (['design.dch', '--cycles', '1'], ['design.dch', '--json', 'design.dch']):
            with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main(arguments)
            self.assertEqual(stopped.exception.code, 2)

    def test_invalid_output_format_and_version_are_usage_errors(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory)/'design.dch'
            source.write_bytes(serialize(new_schematic(), format='dch'))
            for options in (['--format', 'unknown'], ['--version', '999']):
                with self.subTest(options=options), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                    main([str(source), *options])
                self.assertEqual(stopped.exception.code, 2)
