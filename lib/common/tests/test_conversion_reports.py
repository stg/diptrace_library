"""Report attribution locates declared paths for functions and bound methods."""
import unittest

from lib.common.conversion import ConversionReport, export_diagnostics


class ReportAttributionTests(unittest.TestCase):
    def test_bound_method_finds_its_path_without_treating_the_document_as_one(self):
        class Writer:
            @export_diagnostics()
            def write(self,document,path,*,report=None,label=None):
                raise ValueError('controlled failure')
        report = ConversionReport()
        with self.assertRaisesRegex(ValueError,'controlled failure'):
            Writer().write(object(),'output.lib',report=report,label='entry')
        self.assertEqual(1,len(report.errors))
        self.assertEqual(('output.lib','lib','entry'),
                         (report.errors[0].file,report.errors[0].format,report.errors[0].label))


if __name__=='__main__':
    unittest.main()
