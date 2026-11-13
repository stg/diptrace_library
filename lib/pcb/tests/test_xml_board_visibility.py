"""Board-outline display choices remain separate from XML outline geometry."""
import unittest
from xml.etree import ElementTree

import lib
from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.pcb.formats.export_context import ExportContext
from lib.pcb.model.settings_records import LAYER_PANEL
from lib.pcb.tests.test_dip_output import configured_document


RULE = 'xml-board-outline-visibility'


class XmlBoardVisibilityTests(unittest.TestCase):
    def test_hidden_board_warns_and_xml_carries_all_other_display_choices(self):
        document = configured_document()
        panel = document.one('/Board/Settings/LayerPanel')
        panel['Board'] = False
        before = model_text(document, preserve=False)
        for version in lib.format_capabilities('dipxml', family='pcb').write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                raw = lib.serialize(document, format='dipxml', version=version, report=report)
                root = ElementTree.fromstring(raw)
                choices = root.find('Board/Settings/LayerPanel')
                self.assertEqual(set(choices.attrib), set(LAYER_PANEL.fields)-{'Board'})
                self.assertNotIn('BoardOutline', choices.attrib)
                self.assertIsNotNone(root.find('Board/BoardOutline'))
                notices = [n for n in report.notices if n.rule == RULE]
                self.assertEqual([n.severity for n in notices], ['warning'])
                self.assertIn('/Board[1]/Settings[1]/LayerPanel[1]/Board[1]', notices[0].paths)
                rebuilt = lib.parse(raw, report=ConversionReport())
                self.assertIsNone(rebuilt.one('/Board/Settings/LayerPanel').child('Board'))
                self.assertEqual(model_text(document, preserve=False), before)

    def test_visible_choice_is_informational_and_does_not_add_an_xml_attribute(self):
        document = configured_document()
        document.one('/Board/Settings/LayerPanel')['Board'] = True
        report = ConversionReport()
        root = ElementTree.fromstring(lib.serialize(document, format='dipxml', report=report))
        self.assertNotIn('Board', root.find('Board/Settings/LayerPanel').attrib)
        self.assertEqual([n.severity for n in report.notices if n.rule == RULE], ['info'])
        self.assertTrue(document.one('/Board/Settings/LayerPanel')['Board'])

    def test_missing_choice_stays_absent_in_the_model_across_display_units(self):
        document = configured_document()
        panel = document.one('/Board/Settings/LayerPanel')
        del panel['Board']
        for units in ('mm', 'mil', 'inch'):
            with self.subTest(units=units):
                report = ConversionReport()
                raw = lib.serialize(document, format='dipxml', context=ExportContext(units=units), report=report)
                self.assertNotIn('Board', ElementTree.fromstring(raw).find('Board/Settings/LayerPanel').attrib)
                self.assertFalse(any(n.rule == RULE for n in report.warnings))
                self.assertIsNone(panel.child('Board'))

    def test_dip_asc_and_supplied_optional_xml_values_remain_readable(self):
        document = configured_document()
        document.one('/Board/Settings/LayerPanel')['Board'] = False
        for format in ('dip', 'asc'):
            with self.subTest(format=format):
                report = ConversionReport()
                rebuilt = lib.parse(lib.serialize(document, format=format, report=report), report=ConversionReport())
                self.assertFalse(rebuilt.one('/Board/Settings/LayerPanel')['Board'])
                self.assertFalse(any(n.rule == RULE for n in report.notices))
        root = ElementTree.fromstring(lib.serialize(document, format='dipxml', report=ConversionReport()))
        root.find('Board/Settings/LayerPanel').set('Board', 'N')
        supplied = lib.parse(ElementTree.tostring(root), report=ConversionReport())
        self.assertFalse(supplied.one('/Board/Settings/LayerPanel')['Board'])


if __name__ == '__main__':
    unittest.main()
