"""Declared XML dialects retain omitted or explicit component grid alignment."""
import unittest
from xml.etree import ElementTree as ET

import lib
from lib.common.conversion import ConversionReport
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import source


VERSIONS = (('4.3.0.5', 0), ('4.9.5.0', 0), ('5.2.0.1', 0), ('5.3.5.1', 1))


def read(version, alignment=None):
    root = ET.fromstring(source())
    root.set('Version', version)
    component = root.find('Board/Components/Component')
    component.attrib.pop('GridAlign', None)
    if alignment is not None:
        component.set('GridAlign', alignment)
    return lib.parse(ET.tostring(root, encoding='unicode'), report=ConversionReport())


class XmlGridAlignmentTests(unittest.TestCase):
    def test_missing_alignment_uses_the_declared_dialect(self):
        for version, expected in VERSIONS:
            with self.subTest(version=version):
                document = read(version)
                explicit = read(version, 'Origin' if expected else 'Pad')
                self.assertTrue(document.complete)
                self.assertEqual(document.one('/Board/Components/Component')['GsType'], expected)
                self.assertEqual(signature(document.root), signature(explicit.root))
                document.references.validate()

    def test_explicit_names_and_numeric_aliases_override_every_default(self):
        for version, _ in VERSIONS:
            for alignment, expected in (('Pad', 0), ('Origin', 1), ('0', 0), ('1', 1)):
                with self.subTest(version=version, alignment=alignment):
                    document = read(version, alignment)
                    self.assertEqual(document.one('/Board/Components/Component')['GsType'], expected)

    def test_writers_keep_alignment_explicit_and_source_unchanged(self):
        for alignment in ('Pad', 'Origin'):
            document = read('5.3.5.1', alignment)
            before = signature(document.root)
            for version in (54, 58, 60, 62):
                with self.subTest(alignment=alignment, version=version):
                    output = lib.serialize(document, format='dipxml', version=version,
                                           report=ConversionReport())
                    root = ET.fromstring(output)
                    self.assertEqual(root.find('Board/Components/Component').get('GridAlign'), alignment)
                    rebuilt = lib.parse(output, report=ConversionReport())
                    self.assertEqual(rebuilt.one('/Board/Components/Component')['GsType'],
                                     document.one('/Board/Components/Component')['GsType'])
                    self.assertEqual(signature(document.root), before)

    def test_binary_and_ascii_keep_the_interpreted_alignment(self):
        for application, expected in (VERSIONS[0], VERSIONS[-1]):
            document = read(application)
            for format in ('dip', 'asc'):
                with self.subTest(application=application, format=format):
                    output = lib.serialize(document, format=format, report=ConversionReport())
                    rebuilt = lib.parse(output, report=ConversionReport())
                    self.assertEqual(rebuilt.one('/Board/Components/Component')['GsType'], expected)

    def test_invalid_explicit_alignment_is_not_replaced_by_a_default(self):
        for version, _ in VERSIONS:
            with self.subTest(version=version), self.assertRaises(ValueError):
                read(version, 'Diagonal')


if __name__ == '__main__':
    unittest.main()
