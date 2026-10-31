"""Implicit via defaults and explicit physical metadata remain distinct."""
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_xml_via_initialization import source
from lib.pcb.tests.test_xml_via_masks import via_document, COMPONENT


PATTERN = COMPONENT+'/Pattern'


class XmlViaMetadataTests(unittest.TestCase):
    def test_missing_and_empty_style_use_through_mounting_without_changing_cache(self):
        for style in (None, ''):
            with self.subTest(style=style):
                root = source()
                if style is not None:
                    root.find('Board/Components/Component').set('PatternStyle', style)
                document = io.parse(ElementTree.tostring(root), report=ConversionReport())
                pattern = document.one(PATTERN)
                self.assertEqual(pattern['Mounting'], 0)
                self.assertFalse(pattern['LockProperties'])
                cached = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
                self.assertEqual(cached['Mounting'], -1)
                document.references.validate()

    def test_explicit_style_retains_each_mounting_choice_and_type_lock(self):
        for mounting, value in (('None', -1), ('Through', 0), ('SMD', 1),
                                ('Chassis', 2), ('Mixed', 3)):
            for locked in (False, True):
                with self.subTest(mounting=mounting, locked=locked):
                    root = source(explicit=True)
                    template = root.find('Library/Library/Patterns/Pattern')
                    template.set('Mounting', mounting)
                    template.set('LockTypeChange', 'Y' if locked else 'N')
                    document = io.parse(ElementTree.tostring(root), report=ConversionReport())
                    pattern = document.one(PATTERN)
                    self.assertEqual((pattern['Mounting'], pattern['LockProperties']),
                                     (value, locked))
                    document.references.validate()

    def test_nonempty_unknown_style_and_missing_ordinary_geometry_still_fail(self):
        for style in ('missing', ' '):
            with self.subTest(style=style):
                root = source()
                root.find('Board/Components/Component').set('PatternStyle', style)
                with self.assertRaisesRegex(PcbError, 'unresolved footprint style'):
                    io.parse(ElementTree.tostring(root), report=ConversionReport())
        root = source()
        component = root.find('Board/Components/Component')
        component.set('PatternStyle', '')
        component.set('Type', 'Free')
        with self.assertRaisesRegex(PcbError, 'geometry requires a footprint style'):
            io.parse(ElementTree.tostring(root), report=ConversionReport())

    def test_compact_output_requires_all_implicit_physical_defaults(self):
        for mounting, locked in ((0, False), (-1, False), (1, False), (3, True), (0, True)):
            document = via_document()
            pattern = document.one(PATTERN)
            pattern['Mounting'], pattern['LockProperties'] = mounting, locked
            before = model_text(document, preserve=False)
            for version in FORMATS['dipxml'].write_versions:
                with self.subTest(mounting=mounting, locked=locked, version=version):
                    current = document
                    for _ in range(2):
                        data = io.serialize(current, format='dipxml', version=version,
                                            report=ConversionReport())
                        placed = ElementTree.fromstring(data).find('Board/Components/Component')
                        self.assertEqual('PatternStyle' in placed.attrib, (mounting, locked) != (0, False))
                        current = io.parse(data, report=ConversionReport())
                        actual = current.one(PATTERN)
                        self.assertEqual((actual['Mounting'], actual['LockProperties']),
                                         (mounting, locked))
                        current.references.validate()
                    self.assertEqual(model_text(document, preserve=False), before)

    def test_implicit_mounting_survives_every_binary_ascii_and_xml_profile(self):
        document = via_document()
        before = model_text(document, preserve=False)
        for format, support in FORMATS.items():
            for version in support.write_versions:
                with self.subTest(format=format, version=version):
                    data = io.serialize(document, format=format, version=version,
                                        report=ConversionReport())
                    current = io.parse(data, report=ConversionReport())
                    self.assertEqual(current.one(PATTERN)['Mounting'], 0)
                    current.references.validate()
                    self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
