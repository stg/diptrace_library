"""Discarded binary compatibility slots do not compete with design facts."""
import unittest
import xml.etree.ElementTree as ET

from lib.design import ExportReport, new_schematic, parse


def schematic():
    root = ET.fromstring(new_schematic().to_dchxml_bytes())
    owner = root.find('Schematic')
    owner.append(ET.fromstring('''<Nets><Net Id="0" NetClass="0"><Name>Signal</Name>
      <Wires><Wire Id="0" Sheet="0" Connected1="Free" Connected2="Free" Selected="Y">
      <Points><Point X="0" Y="0" Dir="0"/><Point X="3" Y="0" Dir="0"/></Points>
      </Wire></Wires></Net></Nets>'''))
    owner.append(ET.fromstring('''<Buses><Bus Id="0"><Name>Data</Name>
      <Nets><Net NetId="0" ConnectionNumber="7"/></Nets></Bus></Buses>'''))
    return parse(ET.tostring(root), format='dchxml')


class ConnectionPrefixTests(unittest.TestCase):
    def test_nondefault_discarded_slots_normalize_without_model_backups(self):
        original = schematic()
        for version in (46, 47, 48):
            with self.subTest(version=version):
                canonical = original.to_dch_bytes(version=version, report=ExportReport())
                loaded = parse(canonical, format='dch')
                changed = bytearray(canonical)
                for kind, integer_offset in (('Net', 13), ('Bus', 14)):
                    path = '/Schematic/'+('Nets' if kind == 'Net' else 'Buses')+'/'+kind
                    node = loaded.one(path)
                    self.assertIsNone(node.child('StoredData'))
                    self.assertIsNone(node.child('Selected'))
                    start = node.source.start
                    self.assertEqual(changed[start+1], 0)
                    self.assertEqual(changed[start+integer_offset:start+integer_offset+3],
                                     (999_999).to_bytes(3, 'big'))
                    changed[start+1] = 1
                    changed[start+integer_offset:start+integer_offset+3] = (1_000_027).to_bytes(3, 'big')
                current = parse(bytes(changed), format='dch')
                self.assertTrue(current.complete)
                self.assertEqual(current.references.issues, [])
                self.assertEqual(current.to_dch_bytes(version=version, report=ExportReport()), canonical)
                self.assertEqual(loaded.one('/Schematic/Nets/Net').values, ('Signal',))
                self.assertEqual(current.one('/Schematic/Buses/Bus').values, ('Data',))

    def test_wire_selection_is_current_data_across_all_formats(self):
        current = schematic()
        for destination in ('dch', 'asc', 'dchxml'):
            with self.subTest(destination=destination):
                data = getattr(current, 'to_'+destination+'_bytes')(report=ExportReport())
                result = parse(data, format=destination)
                self.assertTrue(result.one('/Schematic/Nets/Net/Lines/Line').scalar('Selected'))
                for path in ('/Schematic/Nets/Net', '/Schematic/Buses/Bus'):
                    self.assertIsNone(result.one(path).child('StoredData'))


if __name__ == '__main__':
    unittest.main()
