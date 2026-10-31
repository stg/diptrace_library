"""PCB conversion uses one editable model and coherent I/O/report conventions."""
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lib
from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.errors import UnsupportedFileError
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import ASC, DIP, DIPXML, XML_APPLICATION_VERSIONS
from lib.pcb.formats.export_context import ExportContext
from lib.pcb.formats.import_context import ImportContext
from lib.pcb.formats.dipxml.versions import CURRENT_APPLICATION
from lib.pcb.model.document import Document
from lib.pcb.tests.test_dip_output import configured_document
from lib.pcb.tests.test_dipxml_library import source as library_source


FORMATS = ('dip', 'asc', 'dipxml')
PART = '/Board/Components/Component[1]'


class PcbIoTests(unittest.TestCase):
    def test_all_format_combinations_share_editable_identity_and_connections(self):
        source = configured_document()
        before = dumps(source, preserve=False)
        for input_format in FORMATS:
            initial = io.parse(io.serialize(source, format=input_format, report=ConversionReport()),
                               report=ConversionReport())
            self.assertIsInstance(initial, Document)
            self.assertEqual(initial.representation, 'pcb')
            initial.one(PART)['RefDes'] = 'Z901'
            for output_format in FORMATS:
                with self.subTest(input=input_format, output=output_format):
                    rebuilt = io.parse(io.serialize(initial, format=output_format, report=ConversionReport()),
                                       report=ConversionReport())
                    self.assertEqual(rebuilt.one(PART)['RefDes'], 'Z901')
                    self.assertEqual(len(rebuilt.select('/Board/Nets/Net')),
                                     len(initial.select('/Board/Nets/Net')))
                    rebuilt.references.validate()
        self.assertEqual(dumps(source, preserve=False), before)

    def test_file_read_detects_content_and_does_not_discover_companions(self):
        document = configured_document()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'misleading.unknown'
            for format in FORMATS:
                path.write_bytes(io.serialize(document, format=format, report=ConversionReport()))
                with self.subTest(format=format), patch.object(Path, 'glob', side_effect=AssertionError('companion scan')):
                    current = io.read(path, report=ConversionReport())
                    self.assertEqual(current.one(PART)['RefDes'], document.one(PART)['RefDes'])
                    self.assertTrue(current.complete)

    def test_optional_contexts_share_fallbacks_and_overrides_without_source_changes(self):
        document = configured_document()
        board = document.one('/Board')
        for node, names in ((board, ('CompFontSize', 'PatternFontVector')),
                            (board.one('Settings'), ('GridSize',)),
                            (board.one('SheetSettings'), ('SheetWidth', 'SheetHeight'))):
            for name in names:
                if node.child(name) is not None:
                    del node[name]
        before = dumps(document, preserve=False)
        context = ExportContext(units='inch', project_dir='project', font_size=3,
                                vector_font=False, grid_size=Decimal('.75'), sheet_size=(900, 600))
        for format in FORMATS:
            with self.subTest(format=format):
                current = io.parse(io.serialize(document, format=format, context=context, report=ConversionReport()),
                                   context=ImportContext(), report=ConversionReport())
                self.assertEqual(current.root['Units'], 'inch')
                self.assertEqual(current.one('/Board')['CompFontSize'], 3)
                self.assertFalse(current.one('/Board')['PatternFontVector'])
                self.assertEqual(current.one('/Board/Settings')['GridSize'], Decimal('.75'))
                self.assertEqual(current.one('/Board/SheetSettings')['SheetWidth'], 900)
        self.assertEqual(dumps(document, preserve=False), before)

    def test_capability_queries_and_adapter_versions_have_one_policy(self):
        document = configured_document()
        self.assertEqual(CURRENT_APPLICATION,
                         tuple(map(int, XML_APPLICATION_VERSIONS[DIPXML.default_write_version].split('.'))))
        for format, capability in (('dip', DIP), ('asc', ASC), ('dipxml', DIPXML)):
            self.assertIs(io.format_capabilities('.'+format.upper()), capability)
            for version in capability.write_versions:
                with self.subTest(format=format, version=version):
                    data = io.serialize(document, format=format, version=version, report=ConversionReport())
                    io.parse(data, report=ConversionReport()).references.validate()
            with self.assertRaises(UnsupportedFileError) as found:
                io.serialize(document, format=format, version=999, report=ConversionReport())
            self.assertEqual((found.exception.format, found.exception.family, found.exception.version,
                              found.exception.reason), (format, 'pcb', 999, 'version'))

    def test_a_shared_report_keeps_file_label_direction_and_failure_scope(self):
        from .test_xml_via_masks import via_document
        document, report = via_document(), ConversionReport()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'output.dipxml'
            io.write(document, path, report=report, label='save')
            saved = path.read_bytes()
            io.read(path, report=report, label='load')
            with self.assertRaises(UnsupportedFileError):
                io.write(document, path, version=999, report=report, label='bad save')
            self.assertEqual(path.read_bytes(), saved)
            self.assertEqual(len(report.errors), 1)
            error = report.errors[0]
            self.assertEqual((error.operation, error.format, error.file, error.label),
                             ('export', 'dipxml', str(path), 'bad save'))
            self.assertTrue(any(n.operation == 'import' and n.file == str(path) and n.label == 'load'
                                for n in report.notices))
            self.assertTrue(all(n.file == str(path) for n in report.notices))

    def test_unknown_inputs_and_other_families_have_structured_unsupported_errors(self):
        for data, family in ((b'not a design', None), (b'\x07DTSCHEM'+(1000052).to_bytes(3, 'big'), 'schematic')):
            report = ConversionReport()
            with self.subTest(data=data), self.assertRaises(UnsupportedFileError) as found:
                io.parse(data, report=report)
            self.assertEqual(found.exception.family, family)
            self.assertEqual(len(report.errors), 1)
        with self.assertRaises(UnsupportedFileError) as found:
            io.parse('(Source "DipTrace-PCBN" 999) (Units mm) (Board)', report=ConversionReport())
        self.assertEqual((found.exception.reason, found.exception.version), ('version', 999))

    def test_text_encodings_preserve_unicode_or_report_the_ansi_projection(self):
        document = configured_document()
        document.one(PART)['Value'] = 'Omega \u03a9 and \x81'
        report = ConversionReport()
        data = io.serialize(document, format='asc', report=report)
        self.assertEqual(io.parse(data, report=ConversionReport()).one(PART)['Value'], 'Omega O and \x81')
        self.assertIn('asc-text-encoding', {n.rule for n in report.warnings})
        data = io.serialize(document, format='asc', encoding='utf-8-sig', report=ConversionReport())
        self.assertEqual(io.parse(data, report=ConversionReport()).one(PART)['Value'], 'Omega \u03a9 and \x81')
        self.assertEqual(document.one(PART)['Value'], 'Omega \u03a9 and \x81')

    def test_document_output_methods_use_the_same_adapters(self):
        document = configured_document()
        for format in FORMATS:
            with self.subTest(format=format):
                data = getattr(document, 'to_'+format+'_bytes')(report=ConversionReport())
                self.assertEqual(data, io.serialize(document, format=format, report=ConversionReport()))
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder)/'forced-output.dat'
                    getattr(document, 'save_'+format)(path, report=ConversionReport())
                    self.assertEqual(path.read_bytes(), data)
        self.assertEqual(document.as_asc(report=ConversionReport()).representation, 'asc')
        self.assertEqual(document.as_dipxml(report=ConversionReport()).representation, 'dipxml')

    def test_family_and_generic_capabilities_share_the_same_adapter(self):
        self.assertIs(lib.format_capabilities('dip'), DIP)
        self.assertIs(lib.pcb.format_capabilities('dip'), DIP)

    def test_wrong_context_types_are_reported_consistently_for_every_adapter(self):
        document = configured_document()
        for format in FORMATS:
            data = io.serialize(document, format=format, report=ConversionReport())
            for operation in ('import', 'export'):
                report = ConversionReport()
                with self.subTest(format=format, operation=operation), self.assertRaises(TypeError):
                    if operation == 'import':
                        io.parse(data, context=ExportContext(), report=report)
                    else:
                        io.serialize(document, format=format, context=ImportContext(), report=report)
                self.assertEqual([(n.operation, n.format) for n in report.errors], [(operation, format)])

    def test_explicit_format_overrides_reach_the_selected_decoder(self):
        document = configured_document()
        for actual, selected in (('asc', 'dipxml'), ('dipxml', 'asc')):
            report = ConversionReport()
            data = io.serialize(document, format=actual, report=ConversionReport())
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                io.parse(data, format=selected, report=report)
            self.assertEqual([(n.operation, n.format) for n in report.errors], [('import', selected)])

    def test_text_exports_do_not_invent_binary_cache_envelopes(self):
        document = configured_document(library_source())
        slot = document.one('/Board/CacheLib/Slots/Slot')
        first = slot.one('Definition')
        second = slot.add('Definition', 0)
        document.copy(first.one('Part'), parent=second)
        before = [row.child('Pattern') is None for row in document.select('/Board/CacheLib/Slots/Slot/Definition')]
        self.assertIn(True, before)
        for format in ('asc', 'dipxml'):
            current = io.parse(io.serialize(document, format=format, report=ConversionReport()),
                               report=ConversionReport())
            after = [row.child('Pattern') is None for row in current.select('/Board/CacheLib/Slots/Slot/Definition')]
            with self.subTest(format=format):
                self.assertEqual(after, before)
