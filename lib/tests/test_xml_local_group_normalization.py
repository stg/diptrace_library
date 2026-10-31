"""XML group activation modernizes into current membership on schematic import."""
import unittest
from xml.etree import ElementTree

from lib import ConversionReport, new_schematic, parse, serialize


class XmlLocalGroupNormalizationTests(unittest.TestCase):
    def test_inactive_group_is_removed_and_active_membership_is_compacted(self):
        # Use an ordinary empty design for unrelated required editor settings.
        root = ElementTree.fromstring(serialize(new_schematic(), format='dchxml', report=ConversionReport()))
        components = root.find('Library/Components')
        component = ElementTree.fromstring('''<Component ComponentStyle="C"><Part><Name>Device</Name>
            <Groups><Item Id="31" Enabled="N" X="1" Y="2"/>
              <Item Id="41" Enabled="Y" X="3" Y="4"/></Groups>
            <Pins><Pin X="0" Y="0" PadId="-1" Group="31"/></Pins>
            <Shapes><Shape Type="Line" Group="41"><Points>
              <Item X="0" Y="0"/><Item X="1" Y="1"/></Points></Shape></Shapes>
          </Part></Component>''')
        components.append(component)
        report = ConversionReport()
        document = parse(ElementTree.tostring(root, encoding='unicode'), report=report)
        part = document.one('/Schematic/CacheLib/Slots/Slot/Definition/Part')
        self.assertEqual([group.values for group in part.select('Groups/pt')], [(True, 0, 9, -12)])
        self.assertEqual(part.one('Pins/Pin')['Group'], -1)
        self.assertEqual(part.one('Shapes/Shape')['Group'], 0)
        self.assertFalse(part.select('//UnresolvedKeys'))
        self.assertIn('local-group-normalization', [notice.rule for notice in report.infos])
        self.assertEqual(report.errors, [])
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                reopened = parse(serialize(document, format=format, report=ConversionReport()), report=ConversionReport())
                current = reopened.one('/Schematic/CacheLib/Slots/Slot/Definition/Part')
                self.assertEqual(current.one('Pins/Pin')['Group'], -1)
                self.assertEqual(current.one('Shapes/Shape')['Group'], 0)


if __name__ == '__main__':
    unittest.main()
