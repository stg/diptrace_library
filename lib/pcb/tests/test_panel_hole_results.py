"""Generated panel-hole check selections are separate from saved drawing IDs."""
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import ReferenceError
from lib.pcb.formats import io
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model import drc_results
from lib.pcb.tests.test_drc_result_model import source as decoded_source
from lib.pcb.tests.test_dipxml_library import source as library_source


PATH = '/Board/DesignErrors/DesignError'


def xml_source():
    root = ElementTree.fromstring(library_source())
    errors = ElementTree.SubElement(root.find('Board'), 'DesignErrors')
    ElementTree.SubElement(errors, 'DesignError', dict(
        Id='0', X='1', Y='2', Type='Clearance', Value='0.1', Rule='0.2',
        ObjectType1='PanelHoleKeepout', Object1='3', SubObject1='-1', Point1='-1',
        ObjectType2='PanelHole', Object2='7', SubObject2='-1', Point2='-1'))
    return ElementTree.tostring(root, encoding='unicode')


class PanelHoleResultTests(unittest.TestCase):
    def test_panel_hole_selection_never_binds_a_saved_drawing_with_the_same_key(self):
        @import_diagnostics('dip')
        def read(decoded):
            return assemble_graphics(decoded).document

        for mode in drc_results.PANEL_HOLE_TYPES:
            decoded = decoded_source()
            row = decoded.board.one('DesignErrors/DesignError')
            row.one('ObjectType2').set_values(mode)
            row.one('Object2').set_values(100)  # A real board drawing uses this source key.
            report = ConversionReport()
            document = read(decoded, report=report)
            current = document.one(PATH)
            with self.assertRaises(ReferenceError):
                current['Target2']
            self.assertEqual(current.one('UnresolvedTarget2').values, (100, -1, -1, -1))
            self.assertEqual(document.references.outgoing(current, role='drc-object-2'), [])
            self.assertTrue(any(n.rule == 'generated-panel-hole-targets' for n in report.infos))
            issues = [issue for issue in document.references.issues if issue.source is current]
            self.assertTrue(issues)
            self.assertTrue(all(issue.severity == 'info' for issue in issues))
            with self.assertRaises(ReferenceError):
                current['Target2'] = document.one('/Board/Shapes/Shape[1]')
            self.assertEqual(current['Object2'], 100)
            current['Target2'] = None
            self.assertEqual(current['Object2'], -1)
            self.assertIsNone(current['Target2'])
            document.references.validate()

    def test_all_outputs_keep_generated_selectors_and_measurements_without_geometry(self):
        imported = ConversionReport()
        document = io.parse(xml_source(), report=imported)
        original, before = document.one(PATH), dumps(document, preserve=False)
        values = tuple(original[name] for name in ('X', 'Y', 'Value', 'Rule'))
        self.assertEqual((original['ObjectType1'], original['ObjectType2']), (22, 23))
        self.assertFalse(any(n.rule == 'unresolved-reference' for n in imported.warnings))
        for format, version in (('dip', 54), ('dip', 62), ('asc', 53),
                                ('dipxml', 54), ('dipxml', 62)):
            with self.subTest(format=format, version=version):
                report = ConversionReport()
                data = io.serialize(document, format=format, version=version, report=report)
                current = io.parse(data, report=report)
                row = current.one(PATH)
                self.assertEqual((row['ObjectType1'], row['ObjectType2'], row['Object1'], row['Object2']),
                                 (22, 23, 3, 7))
                self.assertEqual(tuple(row[name] for name in ('X', 'Y', 'Value', 'Rule')), values)
                for side in ('1', '2'):
                    with self.assertRaises(ReferenceError):
                        row['Target'+side]
                    self.assertIsNotNone(row.child('UnresolvedTarget'+side))
                self.assertTrue(any(n.rule == 'generated-panel-hole-targets' and n.operation == 'export'
                                    for n in report.infos))
                self.assertFalse(any(n.rule in ('generated-panel-hole-targets', 'unresolved-design-error-targets',
                                                'unresolved-reference') for n in report.warnings))
                again = io.parse(io.serialize(current, format=format, version=version,
                                              report=ConversionReport()), report=ConversionReport())
                self.assertEqual(again.one(PATH)['Object2'], 7)
                current.references.validate()
                self.assertEqual(dumps(document, preserve=False), before)

    def test_unselected_panel_hole_is_absent_and_unknown_domains_still_fail(self):
        document = io.parse(xml_source().replace('Object1="3"', 'Object1="-1"'),
                            report=ConversionReport())
        row = document.one(PATH)
        self.assertIsNone(row['Target1'])
        self.assertIsNone(row.child('UnresolvedTarget1'))
        with self.assertRaisesRegex(ValueError, 'mapping is not implemented'):
            io.parse(xml_source().replace('ObjectType1="PanelHoleKeepout"', 'ObjectType1="28"'),
                     report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
