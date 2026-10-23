"""Bus endpoints use public IDs and editable segment identities."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.design import parse_dchxml
from lib.design.dchxml_buses import project_bus, project_bus_connectors, project_groups
from lib.design.dchxml_units import DchXmlUnits
from lib.design.model import Element


class XmlBusesTests(unittest.TestCase):
    def test_bus_and_connector_ids_follow_edited_targets_and_reversed_segments(self):
        document = parse_dchxml('''<Source Type="DipTrace-Schematic"><Schematic>
        <SheetSettings><Sheets><Sheet><Id>0</Id></Sheet></Sheets></SheetSettings>
        <Groups><Group Id="9"/></Groups>
        <Nets><Net Id="4"><Name>N</Name><Wires><Wire Id="8" Sheet="0" Connected1="Bus" Bus1="3" Object1="7" SubObject1="1" Connected2="Free"/></Wires></Net></Nets>
        <BusConnectors><BusConnector Id="6" Sheet="0" Connected="Y" Group="9"><Name>B</Name></BusConnector></BusConnectors>
        <Buses><Bus Id="3"><Name>DATA</Name><Nets><Net NetId="4" ConnectionNumber="12"/></Nets><Wires>
        <Wire Id="7" Sheet="0" Connected1="Bus Connector" Object1="6" SubObject1="-1" Connected2="Free"><Points><Point X="0" Y="0"/><Point X="10" Y="0"/></Points></Wire>
        <Wire Id="2" Sheet="0" Connected1="Bus Wire" Bus1="-1" Object1="7" SubObject1="1" Connected2="Free"/>
        </Wires></Bus></Buses></Schematic></Source>''')
        self.assertEqual(document.references.issues, [])
        schematic = document.one('/Source/Schematic')
        bus = schematic.one('Buses/Bus')
        route, branch = bus.select('Wires/Wire')
        route.one('Points/Point[1]').move_to(route.one('Points'), 1)
        bus.set_field('Id', 31)
        route.set_field('Id', 71)
        schematic.one('BusConnectors/BusConnector').set_field('Id', 61)
        schematic.one('Nets/Net').set_field('Id', 41)
        schematic.one('Groups/Group').set_field('Id', 91)
        document.rebuild()
        net_wire = schematic.one('Nets/Net/Wires/Wire')
        self.assertEqual((net_wire.scalar('Bus1'), net_wire.scalar('Object1'), net_wire.scalar('SubObject1')), (31, 71, 1))
        self.assertEqual((branch.scalar('Bus1'), branch.scalar('Object1')), (-1, 71))
        self.assertEqual(route.scalar('Object1'), 61)
        self.assertEqual(bus.one('Nets/Net').scalar('NetId'), 41)
        self.assertEqual(schematic.one('BusConnectors/BusConnector').scalar('Group'), 91)
        self.assertEqual(parse_dchxml(document.to_dchxml_bytes()).references.issues, [])

    def test_bus_data_keeps_connection_numbers_and_duplicate_members(self):
        bus = Element('Bus', 'DATA')
        for name, value in dict(Number=3, Enabled=False, Locked=True).items():
            bus.add(name, value)
        members, numbers = bus.add('Nets'), bus.add('Numbers')
        for number in (8, 8):
            members.add('pt', number)
        for number in (4, 7):
            numbers.add('pt', number)
        line = bus.add('Lines').add('Line')
        for name, value in dict(Number=2, Page=0, ConnectMode1=-1, ConnectMode2=4,
            ConnectB1=-1, ConnectB2=-1, Connect1=-1, Connect2=6, ConnectL1=-1, ConnectL2=-1,
            Selected=True, Group=9).items():
            line.add(name, value)
        points = line.add('Points')
        points.add('pt', 3, 6, 1)
        points.add('pt', 9, 12, 0)
        result = project_bus(bus, units=DchXmlUnits('mm'))
        self.assertEqual(result.scalar('Name'), 'DATA')
        self.assertFalse(result.scalar('Enabled'))
        self.assertEqual([(n.scalar('NetId'), n.scalar('ConnectionNumber')) for n in result.select('Nets/Net')], [(8, 4), (8, 7)])
        view = result.one('Wires/Wire')
        self.assertEqual((view.scalar('Connected1'), view.scalar('Connected2')), ('Free', 'Bus Connector'))
        self.assertEqual(tuple(float(view.one('Points/Point[1]').scalar(n)) for n in ('X', 'Y')), (1, -2))
        numbers.children()[0].detach()
        with self.assertRaisesRegex(ValueError, 'one connection number'):
            project_bus(bus, units=DchXmlUnits('mm'))

    def test_disabled_connectors_and_groups_are_public_records(self):
        schematic = Element('Schematic')
        connector = schematic.add('PageConnectors').add('PageConnector', 'PAGE', 3, 6)
        for name, value in dict(Number=6, Page=0, Enabled=False, Connected=False, Group=-1, Selected=True, Locked=False).items():
            connector.add(name, value)
        result = project_bus_connectors(schematic, units=DchXmlUnits('mm')).one('BusConnector')
        self.assertEqual(result.scalar('Name'), 'PAGE')
        self.assertIs(result.scalar('Connected'), False)
        group = schematic.add('Groups').add('Group', 9, 15, 18)
        group.add('Enabled', False)
        group.add('Selected', True)
        public = project_groups(schematic).one('Group')
        self.assertEqual((public.scalar('Id'), public.scalar('Enabled'), public.scalar('Selected')), (9, False, True))


if __name__ == '__main__':
    unittest.main()
