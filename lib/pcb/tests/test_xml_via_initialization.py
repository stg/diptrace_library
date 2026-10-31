"""XML via placements own their pad keys and options independently of templates."""
import unittest
from copy import deepcopy
from decimal import Decimal
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.geometry import transform_point
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.formats.errors import PcbError
from lib.pcb.model.objects import new_net
from lib.pcb.tests.test_xml_via_masks import via_document, configure, facts, COMPONENT, PAD


def source(*, explicit=False, connected=False):
    document = via_document()
    template = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern/Pads/Pad[1]')
    for name, value in dict(Name='Template pad', StringNumber='CUSTOM', X=30,
                            Locked=True, PadCorner=2).items():
        template[name] = value
    pad = document.one(PAD)
    configure(pad)
    if connected:
        pad['Net'] = document.one('/Board/Nets').append(new_net('Signal'))
    root = ElementTree.fromstring(io.serialize(document, format='dipxml', report=ConversionReport()))
    component = root.find('Board/Components/Component')
    if explicit:
        style = root.find('Library/Library/Patterns/Pattern').get('PatternStyle')
        component.set('PatternStyle', style)
    component.find('Pads/Pad').set('Id', '501')
    if connected:
        root.find('Board/Nets/Net/Pads/Item').set('Pad', '501')
    return root


class XmlViaInitializationTests(unittest.TestCase):
    def test_explicit_template_does_not_supply_placed_via_pad_data(self):
        document = io.parse(ElementTree.tostring(source(explicit=True, connected=True)), report=ConversionReport())
        pad = document.one(PAD)
        self.assertEqual((pad['StringNumber'], pad['Name']), ('1', ''))
        component = document.one(COMPONENT)
        # A final body reframe may move its local anchor, but the new via pad
        # starts at the supplied board placement, not at the template pad.
        world = transform_point((pad['X'], pad['Y']), origin=(component['X'], component['Y']),
                                angle=component['Angle'])
        self.assertAlmostEqual(world[0], 30, places=12)
        self.assertAlmostEqual(world[1], 60, places=12)
        self.assertFalse(pad['Locked'])
        self.assertEqual(pad['PadCorner'], 0)
        self.assertIsNone(pad.get('Id'))
        self.assertEqual(pad['Net']['Name'], 'Signal')
        self.assertIs(document.one('/Board/Nets/Net/Pads/Item')['Pad'], pad)
        template = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern/Pads/Pad[1]')
        self.assertEqual((template['Name'], template['X']), ('Template pad', 30))
        document.references.validate()

    def test_implicit_via_accepts_an_independent_public_pad_key(self):
        report = ConversionReport()
        document = io.parse(ElementTree.tostring(source(connected=True)), report=report)
        self.assertEqual(document.one(PAD)['Net']['Name'], 'Signal')
        self.assertTrue(any(notice.rule == 'xml-via-pad-initialization' for notice in report.infos))
        output = ElementTree.fromstring(io.serialize(document, format='dipxml', report=ConversionReport()))
        self.assertNotIn('PatternStyle', output.find('Board/Components/Component').attrib)
        self.assertEqual(output.find('Board/Components/Component/Pads/Pad').get('Id'), '1')
        self.assertEqual(output.find('Board/Nets/Net/Pads/Item').get('Pad'), '1')

    def test_unconnected_pad_without_a_public_key_still_has_current_identity(self):
        root = source()
        root.find('Board/Components/Component/Pads/Pad').attrib.pop('Id')
        document = io.parse(ElementTree.tostring(root), report=ConversionReport())
        self.assertEqual(document.one(PAD)['StringNumber'], '1')
        self.assertIsNone(document.one(PAD)['Net'])
        document.references.validate()

    def test_duplicate_public_pad_keys_are_rejected(self):
        root = source()
        pads = root.find('Board/Components/Component/Pads')
        pads.append(deepcopy(pads.find('Pad')))
        with self.assertRaisesRegex(PcbError, 'duplicate placed via pad'):
            io.parse(ElementTree.tostring(root), report=ConversionReport())

    def test_missing_style_uses_xml_initialization_defaults(self):
        root = source(explicit=True)
        root.find('Board/Components/Component').attrib.pop('ViaStyle')
        document = io.parse(ElementTree.tostring(root), report=ConversionReport())
        pad = document.one(PAD)
        self.assertEqual((pad['PadWidth_New'], pad['PadHeight_New']), (None, None))
        self.assertEqual((pad['PadHole'], pad['PadHoleH']), (Decimal('.5'), Decimal('.5')))
        self.assertIsNone(document.one(COMPONENT)['Via'])

    def test_export_warns_about_pad_data_xml_initialization_replaces(self):
        document = via_document()
        pad = document.one(PAD)
        configure(pad)
        options = facts(pad)
        for name, value in dict(Name='Local pad', StringNumber='CUSTOM', X=3,
                                Locked=True, PadAngle=Decimal('.75')).items():
            pad[name] = value
        before = model_text(document, preserve=False)
        for version in FORMATS['dipxml'].write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                data = io.serialize(document, format='dipxml', version=version, report=report)
                notices = [notice for notice in report.warnings if notice.rule == 'xml-via-pad-data']
                self.assertEqual(len(notices), 1)
                self.assertEqual(notices[0].paths, (pad.path,))
                rebuilt = io.parse(data, report=ConversionReport())
                current = rebuilt.one(PAD)
                self.assertEqual((current['StringNumber'], current['Name'], current['X'], current['PadAngle']),
                                 ('1', '', 0, 0))
                self.assertFalse(current['Locked'])
                self.assertEqual(facts(current), options)
                self.assertEqual(model_text(document, preserve=False), before)
                rebuilt.references.validate()


if __name__ == '__main__':
    unittest.main()
