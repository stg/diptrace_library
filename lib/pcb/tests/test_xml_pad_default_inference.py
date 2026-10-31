"""XML placement declarations, inferred inheritance and via defaults differ."""
import unittest
from xml.etree import ElementTree as ET

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import DIPXML
from lib.pcb.formats.dipxml.versions import XmlVersion
from lib.pcb.tests.test_dipxml_components import SOURCE, prepared
from lib.pcb.tests.test_xml_via_masks import via_document, COMPONENT, PAD


def declaration(value=None, *, listed=True, mask=False):
    root = ET.fromstring(SOURCE)
    template = root.find('Library/Patterns/Pattern/Pads/Pad')
    template.set('DefStyle', 'N')
    placements = root.find('Board/Components/Component/Pads')
    pad = placements.find('Pad')
    if value is not None:
        pad.set('DefStyle', value)
    if mask:
        ET.SubElement(pad, 'MaskPaste', CustomSwell='0')
    if not listed:
        placements.remove(pad)
    return ET.tostring(root, encoding='unicode')


class XmlPadDefaultInferenceTests(unittest.TestCase):
    def test_omitted_placement_declaration_uses_current_geometry_not_style_identity(self):
        patterns, placed = prepared(declaration())
        self.assertFalse(patterns['P'].element.one('Pads/Pad[2]')['Standard'])
        self.assertTrue(placed.component.one('Pattern/Pads/Pad[2]')['Standard'])

    def test_explicit_custom_declaration_and_unlisted_template_pad_are_retained(self):
        for text in (declaration('N'), declaration(listed=False)):
            with self.subTest(text=text):
                _, placed = prepared(text)
                self.assertFalse(placed.component.one('Pattern/Pads/Pad[2]')['Standard'])

    def test_omitted_declaration_includes_placed_mask_overrides(self):
        _, placed = prepared(declaration(mask=True))
        pad = placed.component.one('Pattern/Pads/Pad[2]')
        self.assertFalse(pad['Standard'])
        self.assertEqual(pad['CustomSwell_New'], 0)

    def test_via_without_a_declaration_keeps_constructor_custom_status(self):
        document = via_document()
        document.one(PAD)['Standard'] = True
        root = ET.fromstring(io.serialize(document, format='dipxml', version=62,
                                         report=ConversionReport()))
        root.find('Board/Components/Component/Pads/Pad').attrib.pop('DefStyle')
        rebuilt = io.parse(ET.tostring(root), report=ConversionReport())
        self.assertFalse(rebuilt.one(PAD)['Standard'])
        rebuilt.validate()

    def test_each_destination_reports_only_an_actual_inheritance_change(self):
        for via in (False, True):
            for standard in (False, True):
                document = via_document()
                component = document.one(COMPONENT)
                if not via:
                    component['Via'] = None
                    component.one('Pattern')['Type'] = 14
                document.one(PAD)['Standard'] = standard
                before = model_text(document, preserve=False)
                for version in DIPXML.write_versions:
                    with self.subTest(via=via, standard=standard, version=version):
                        report = ConversionReport()
                        data = io.serialize(document, format='dipxml', version=version, report=report)
                        root = ET.fromstring(data)
                        row = root.find('Board/Components/Component/Pads/Pad')
                        current = XmlVersion.output(version).current_fields
                        self.assertEqual(row.get('DefStyle'), ('Y' if standard else 'N') if current else None)
                        expected = standard if current else not via
                        rebuilt = io.parse(data, report=ConversionReport())
                        self.assertEqual(rebuilt.one(PAD)['Standard'], expected)
                        warnings = {notice.rule for notice in report.warnings}
                        self.assertEqual('pad-style-inheritance' in warnings, expected != standard)
                        self.assertEqual(model_text(document, preserve=False), before)
                        rebuilt.validate()


if __name__ == '__main__':
    unittest.main()
