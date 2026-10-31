"""Static-via mask/paste settings belong to XML placement, not its recipe."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.pad_masks import MASK_DATA_FIELDS, MASK_COLLECTIONS
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.tests.test_dipxml_library import source
from lib.pcb.tests.test_xml_component_output import reopen


COMPONENT = '/Board/Components/Component'
PAD = COMPONENT+'/Pattern/Pads/Pad'


def via_document():
    root = ElementTree.fromstring(source())
    board = root.find('Board')
    style = ElementTree.SubElement(ElementTree.SubElement(board, 'ViaStyles'), 'ViaStyle',
                                  Id='5', Size='0.6', HoleSize='0.3', Lay1='0', Lay2='-1')
    ElementTree.SubElement(style, 'Name').text = 'Through'
    component = board.find('Components/Component')
    component.attrib.pop('PatternStyle')
    component.set('Type', 'Via')
    component.set('ViaStyle', '5')
    component.find('Pads').clear()
    ElementTree.SubElement(component.find('Pads'), 'Pad', Id='1', NetId='-1')
    board.find('Nets').clear()
    return io.parse(ElementTree.tostring(root, encoding='unicode'), report=ConversionReport())


def configure(pad):
    for name, value in dict(DisableTopMask=2, DisableBottomMask=1, DisableTopPaste=3,
            DisableBottomPaste=0, CustomSwell_New=Decimal('.0762'), CustomShrink_New=0,
            PadMask_Percent=Decimal('25.5'), PadMask_EdgeGap=Decimal('.2286'),
            PadMask_SegmentGap=Decimal('.0762'), PadMask_SegmentSide=Decimal('.1524')).items():
        pad[name] = value
    pad.one('PadMask_TopSegments').add('pt', Decimal('.0762'), Decimal('.1524'),
                                     Decimal('.2286'), Decimal('.3048'))
    pad.one('PadMask_BotSegments').add('pt', Decimal('-.1524'), 0, Decimal('.0762'), 0)


def facts(pad):
    return ({name: pad[name] for name in MASK_DATA_FIELDS},
            {name: [row.values for row in pad.one(name).children()] for name in MASK_COLLECTIONS})


class XmlViaMaskTests(unittest.TestCase):
    def test_mask_edits_keep_the_implicit_via_in_every_xml_profile(self):
        document = via_document()
        configure(document.one(PAD))
        expected, before = facts(document.one(PAD)), model_text(document, preserve=False)
        for version in FORMATS['dipxml'].write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                payload = io.serialize(document, format='dipxml', version=version, report=report)
                placed = ElementTree.fromstring(payload).find('Board/Components/Component')
                self.assertNotIn('PatternStyle', placed.attrib)
                self.assertIsNotNone(placed.find('Pads/Pad/MaskPaste'))
                rebuilt = io.parse(payload, report=ConversionReport())
                self.assertEqual(facts(rebuilt.one(PAD)), expected)
                self.assertIsNotNone(rebuilt.one(COMPONENT)['Via'])
                self.assertFalse(report.errors)
                self.assertEqual(model_text(document, preserve=False), before)

    def test_repeated_unit_conversions_preserve_masks_without_new_physical_styles(self):
        document = via_document()
        configure(document.one(PAD))
        expected = facts(document.one(PAD))
        for units in ('mil', 'mm', 'mil'):
            document, output = reopen(document, units=units)
            placed = output.one('/Source/Board/Components/Component')
            self.assertIsNone(placed.child('PatternStyle'))
            self.assertEqual(facts(document.one(PAD)), expected)
            if units == 'mil':
                self.assertEqual(placed.one('Pads/Pad/MaskPaste')['Segment_Side'], 2)
                self.assertEqual(placed.one('Pads/Pad/MaskPaste/TopSegments/Item')['Y1'], -2)


if __name__ == '__main__':
    unittest.main()
