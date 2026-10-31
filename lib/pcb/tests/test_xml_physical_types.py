"""XML library pattern types and PCB placement kinds have separate vocabularies."""
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.common.xml_footprint_vocabulary import PATTERN_TYPES
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.formats.dipxml.pattern_output import project_pattern
from lib.pcb.tests.test_dipxml_library import read, source
from lib.pcb.tests.test_xml_via_masks import via_document, COMPONENT


RULE = 'xml-physical-pattern-type'


class XmlPhysicalTypeTests(unittest.TestCase):
    def test_known_placement_kinds_use_the_library_vocabulary_without_changing_locks(self):
        document = read(source(), report=ConversionReport())
        pattern = document.one(COMPONENT+'/Pattern')
        for kind in (0, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20):
            for locked in (False, True):
                with self.subTest(kind=kind, locked=locked):
                    pattern['Type'], pattern['LockProperties'] = kind, locked
                    before, report = model_text(document, preserve=False), ConversionReport()
                    output = project_pattern(pattern, style='Physical', units=XmlUnits('mm'), report=report).element
                    self.assertEqual(output['Type'], PATTERN_TYPES[kind] if kind < len(PATTERN_TYPES) else 'Free')
                    self.assertEqual(output['LockTypeChange'], locked)
                    self.assertEqual(any(notice.rule == RULE for notice in report.infos), kind >= len(PATTERN_TYPES))
                    self.assertFalse(any(notice.rule == RULE for notice in report.warnings))
                    self.assertEqual(model_text(document, preserve=False), before)

    def test_real_pad_and_explicit_via_placements_keep_their_kind_in_every_xml_profile(self):
        for kind, label in ((14, 'Pad'), (16, 'Via')):
            for locked in (False, True):
                document = via_document()
                component = document.one(COMPONENT)
                if kind == 14:
                    component['Via'] = None
                pattern = component.one('Pattern')
                pattern['Type'], pattern['LockProperties'] = kind, locked
                # A named physical definition differs from the implicit via
                # recipe, so both lock choices exercise the explicit style.
                pattern['Name'] = 'Standalone physical'
                before = model_text(document, preserve=False)
                for version in FORMATS['dipxml'].write_versions:
                    with self.subTest(kind=kind, locked=locked, version=version):
                        current = document
                        for _ in range(2):
                            report = ConversionReport()
                            data = io.serialize(current, format='dipxml', version=version, report=report)
                            root = ElementTree.fromstring(data)
                            placed = root.find('Board/Components/Component')
                            style = next(p for p in root.findall('Library/Library/Patterns/Pattern')
                                         if p.get('PatternStyle') == placed.get('PatternStyle'))
                            self.assertEqual(placed.get('Type'), label)
                            self.assertEqual(style.get('Type'), 'Free')
                            self.assertEqual(style.get('LockTypeChange'), 'Y' if locked else 'N')
                            self.assertTrue(any(n.rule == RULE for n in report.infos))
                            current = io.parse(data, report=ConversionReport())
                            physical = current.one(COMPONENT+'/Pattern')
                            self.assertEqual((physical['Type'], physical['LockProperties']), (kind, locked))
                            current.references.validate()
                        self.assertEqual(model_text(document, preserve=False), before)

    def test_unplaced_definition_reports_the_classification_it_cannot_retain(self):
        document = read(source(), report=ConversionReport())
        pattern = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        for kind in (14, 16, 20):
            with self.subTest(kind=kind):
                pattern['Type'] = kind
                before, report = model_text(document, preserve=False), ConversionReport()
                output = project_pattern(pattern, style='Cached', units=XmlUnits('mm'), report=report).element
                self.assertEqual(output['Type'], 'Free')
                warnings = [notice for notice in report.warnings if notice.rule == RULE]
                self.assertEqual(len(warnings), 1)
                self.assertEqual(warnings[0].paths, (pattern.path,))
                self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
