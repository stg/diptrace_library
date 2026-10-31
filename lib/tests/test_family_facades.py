"""Family namespaces retain the generic API and each family's own model."""
import subprocess
import sys
import unittest

import lib
import lib.schematic as schematic
import lib.pcb as pcb
from lib.common.model import Document as BaseDocument


class FamilyFacadeTests(unittest.TestCase):
    def test_models_and_contexts_belong_to_their_family(self):
        self.assertIs(schematic.Document, lib.Document)
        self.assertIs(schematic.ImportContext, lib.ImportContext)
        for family, package in [('schematic', schematic), ('pcb', pcb)]:
            with self.subTest(family=family):
                document = package.new_document()
                self.assertIsInstance(document, BaseDocument)
                self.assertIsInstance(document, package.Document)
                self.assertEqual(lib.document_family(document), family)

    def test_scoped_asc_capabilities_never_prefer_another_family(self):
        for family, package in [('schematic', schematic), ('pcb', pcb)]:
            self.assertEqual(package.format_capabilities('asc').family, family)
        with self.assertRaises(ValueError):
            lib.format_capabilities('asc')

    def test_scoped_and_generic_buffers_use_the_same_current_model(self):
        for family, package in [('schematic', schematic), ('pcb', pcb)]:
            with self.subTest(family=family):
                data = package.serialize(package.new_document(), format='asc', report=lib.ConversionReport())
                self.assertTrue(package.parse(data, report=lib.ConversionReport()).complete)
                self.assertEqual(lib.document_family(lib.parse(data, report=lib.ConversionReport())), family)

    def test_lazy_schematic_exports_work_during_a_fresh_import(self):
        result = subprocess.run([sys.executable, '-c',
            'from lib.schematic import Document, read, new_document; '
            'import lib; assert Document is lib.Document; '
            'assert new_document().representation == "schematic"'],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
