"""Unavailable targets cannot become unrelated positional output identities."""
import unittest
import xml.etree.ElementTree as ET

from lib.common.conversion import ConversionReport
from lib.component.formats.elixml.read import parse
from lib.component.formats.eli.read import parse as read_binary
from lib.component.formats.eli.write import encode
from lib.component.formats.asc.read import parse as read_asc
from lib.component.formats.asc.write import dumps
from lib.component.formats.elixml.write import dumps as dumps_xml
from .test_elixml_read import source


def unavailable(key):
    root = source()
    part = root.find('Components/Component/Part')
    physical = root.find('Library/Patterns/Pattern')
    for pad, number in zip(physical.findall('Pads/Pad'), (17, 42)):
        pad.set('Id', str(number))
    physical.find('Shapes/Shape').set('PadId', '42')
    pins = part.findall('Pins/Pin')
    pins[0].set('PadId', str(key))
    pins[1].set('PadId', '42')
    groups = ET.SubElement(part, 'Groups')
    ET.SubElement(groups, 'Group', Id='9', X='0', Y='0')
    ET.SubElement(groups, 'Group', Id='12', X='1', Y='1')
    pins[0].set('Group', str(key))
    ET.SubElement(physical.find('Dimensions'), 'Dimension', Connected1='Pad',
                  SubObject1=str(key), Connected2='Pad', SubObject2='42')
    ET.SubElement(ET.SubElement(part, 'InternalConnections'), 'IntCon', X=str(key), Y='42')
    return parse(ET.tostring(root), report=ConversionReport())


def content(document):
    return tuple((node.path, node.values) for node in document.root.walk(include_self=True))


class UnresolvedOutputTests(unittest.TestCase):
    def test_keyed_output_preserves_missing_targets_without_false_bindings(self):
        for key in (1, 999):
            with self.subTest(key=key):
                document = unavailable(key)
                before = content(document)
                result = document
                for _ in range(3):
                    report = ConversionReport()
                    text = dumps_xml(result, report=report)
                    xml = ET.fromstring(text)
                    self.assertNotIn(str(key), [pad.get('Id') for pad in xml.findall('Library/Patterns/Pattern/Pads/Pad')])
                    self.assertNotIn(str(key), [group.get('Id') for group in xml.findall('Components/Component/Part/Groups/Group')])
                    result = parse(text, report=ConversionReport())
                    component = result.one('/Library/Components/Component')
                    pin = component.select('Parts/Part/Pins/Pin')[0]
                    self.assertEqual(key, pin['UnresolvedPadId'])
                    self.assertEqual(key, pin['UnresolvedGroupId'])
                    dimension = component.one('Pattern/Dimensions/Dimension')
                    self.assertEqual(key, dimension['SubObject1'])
                    self.assertEqual([], result.references.outgoing(dimension, role='pattern-dimension-1'))
                    self.assertEqual(key, component.one('Pattern/InternalConnections/IntCon')['UnresolvedX'])
                    self.assertEqual(4, len(result.references.issues))
                    self.assertIn('unresolved-local-reference', {notice.rule for notice in report.warnings})
                    result.validate()
                self.assertEqual(before, content(document))

    def test_positional_outputs_unassign_without_touching_the_source(self):
        for key in (1, 999):
            for destination, write, read in (('eli', encode, read_binary), ('asc', dumps, read_asc)):
                with self.subTest(key=key, destination=destination):
                    document = unavailable(key)
                    before = content(document)
                    issues = tuple(document.references.issues)
                    self.assertEqual(4, len(issues))
                    report = ConversionReport()
                    result = read(write(document, report=report), report=ConversionReport())
                    component = result.one('/Library/Components/Component')
                    pin = component.select('Parts/Part/Pins/Pin')[0]
                    self.assertIsNone(pin['Pad'])
                    self.assertIsNone(pin['Group'])
                    dimension = component.one('Pattern/Dimensions/Dimension')
                    self.assertEqual(-1, dimension['Connected1'])
                    self.assertEqual(0, dimension['Connected2'])
                    self.assertEqual(2, dimension['SubObject2'])
                    self.assertEqual([], component.select('Pattern/InternalConnections/IntCon'))
                    self.assertEqual([], result.references.issues)
                    self.assertEqual({'unresolved-local-reference', 'unresolved-internal-connection'},
                                     {notice.rule for notice in report.warnings if notice.rule.startswith('unresolved-')})
                    self.assertEqual(before, content(document))
                    self.assertEqual(issues, tuple(document.references.issues))
                    document.validate()
                    result.validate()


if __name__ == '__main__':
    unittest.main()
