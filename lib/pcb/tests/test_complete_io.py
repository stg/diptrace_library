"""Full PCB imports and partial assembly use the shared completeness contract."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lib.common.conversion import ConversionReport
from lib.common.model import IncompleteDocumentError
from lib.pcb.formats import io
from lib.pcb.formats.dip.decode import decode
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.tests.test_dip_output import configured_document


class CompletePcbIoTests(unittest.TestCase):
    def test_full_import_and_syntax_conversion_are_complete(self):
        source = configured_document()
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                data = io.serialize(source, format=format, report=ConversionReport())
                current = io.parse(data, report=ConversionReport())
                self.assertTrue(current.complete)
                self.assertNotIn('PCB import assembly is incomplete', current.diagnostics)
                self.assertTrue(current.clone().complete)
                syntax = io.parse_source(data, report=ConversionReport())
                self.assertTrue(syntax.as_pcb(report=ConversionReport()).complete)

    def test_partial_core_is_rejected_by_every_writer_without_changing_output(self):
        data = io.serialize(configured_document(), format='dip', report=ConversionReport())
        partial = assemble_core(decode(data)).document
        self.assertFalse(partial.complete)
        with TemporaryDirectory() as folder:
            path = Path(folder)/'existing.design'
            for format in ('dip', 'asc', 'dipxml'):
                with self.subTest(format=format):
                    report = ConversionReport()
                    with self.assertRaises(IncompleteDocumentError):
                        io.serialize(partial, format=format, report=report)
                    self.assertEqual([(n.operation, n.format) for n in report.errors], [('export', format)])
                    path.write_bytes(b'keep existing file')
                    with self.assertRaises(IncompleteDocumentError):
                        io.write(partial, path, format=format, report=ConversionReport())
                    self.assertEqual(path.read_bytes(), b'keep existing file')

    def test_explicitly_incomplete_model_does_not_become_complete_by_cloning(self):
        source = configured_document()
        source.complete = False
        copied = source.as_pcb(report=ConversionReport())
        self.assertFalse(copied.complete)
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format), self.assertRaises(IncompleteDocumentError):
                io.serialize(copied, format=format, report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
