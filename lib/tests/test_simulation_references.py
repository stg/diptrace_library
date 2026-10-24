"""Simulator links follow object identities without rewriting display labels."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import Document, ReferenceError, parse_dchxml, parse_dch, new_schematic, DchXmlExportContext
from lib.schematic.model.refs import (bind_schematic_references)
from lib.schematic.model.objects import (new_symbol)
from lib.schematic.formats.dchxml.import_nets import (read_nets)
from lib.schematic.formats.dchxml.import_values import (XmlRecord)
from lib.schematic.formats.dchxml.units import (DchXmlUnits)
from lib.schematic.layout.markings import (MarkingStyle)


def schematic():
    document = Document()
    document.root.add('Source', 'DipTrace-Schematic', 46)
    design = document.root.add('Schematic')
    for container, kind in (('Components', 'Part'), ('Nets', 'Net')):
        rows = design.add(container)
        for number in range(2):
            rows.add(kind).add('Number', number)
    simulator = design.add('ssimulator')
    simulator.add('tp', 0)  # Inactive configuration still has object links.
    simulator.add('gndnum', 0)
    simulator.add('gndname', 'User ground label')
    signals = simulator.add('signals')
    for kind, number in ((0, 0), (1, 1)):
        signal = signals.add('signal')
        signal.add('signal_tp', kind)
        signal.add('signal_num', number)
        signal.add('signal_display_name', 'User label')
    return document


class SimulationReferencesTests(unittest.TestCase):
    def test_authored_simulator_survives_xml_normalization_and_binary_output(self):
        document = new_schematic()
        owner = document.one('/Schematic')
        for index in range(2):
            part = owner.one('Components').append(new_symbol('Probe', 'P'+str(index)))
            part.set_field('Number', index)
        public = parse_dchxml('''<Source Type="DipTrace-Schematic"><Schematic><Nets>
        <Net Id="10"><Name>Ground</Name></Net><Net Id="20"><Name>Output</Name></Net>
        </Nets></Schematic></Source>''')
        read_nets(XmlRecord(public.one('/Source/Schematic')), owner, units=DchXmlUnits('mm'), sheets={0: 0}, classes={0: 0})
        for index, net in enumerate(owner.select('Nets/Net')):
            net.set_field('Number', index)
        simulator = owner.one('ssimulator')
        simulator.set_field('tp', 9)
        simulator.set_field('gndnum', 0)
        for kind, number in ((0, 0), (1, 1)):
            signal = simulator.one('signals').add('signal')
            for name, value in (('signal_tp', kind), ('signal_num', number),
                                ('signal_display_name', 'Own plot'), ('signal_visible', True),
                                ('signal_plotted', True), ('signal_color', 0x123456)):
                signal.add(name, value)
        bind_schematic_references(document)
        context = DchXmlExportContext(units='mm', grid_snap=True, marking_style=MarkingStyle(font_name='Arial'))
        shared = parse_dchxml(document.to_dchxml_bytes(context=context)).as_schematic()
        for name in ('Components', 'Nets'):
            rows = shared.one('/Schematic/'+name)
            rows.children()[0].move_to(rows, 1)
        data = shared.to_dch_bytes()
        reloaded = parse_dch(data)
        self.assertEqual(reloaded.references.issues, [])
        self.assertEqual(reloaded.to_dch_bytes(), data)
        self.assertEqual(reloaded.one('/Schematic/ssimulator').scalar('gndnum'), 1)
        self.assertEqual([item.scalar('signal_num') for item in reloaded.select('/Schematic/ssimulator/signals/signal')], [1, 0])

    def test_current_voltage_and_ground_follow_their_own_collections(self):
        document = schematic()
        bind_schematic_references(document)
        for name in ('Components', 'Nets'):
            rows = document.one('/Schematic/'+name)
            rows.children()[0].move_to(rows, 1)
        document.rebuild()
        simulator = document.one('/Schematic/ssimulator')
        self.assertEqual([item.scalar('signal_num') for item in simulator.select('signals/signal')], [1, 0])
        self.assertEqual(simulator.scalar('gndnum'), 1)
        self.assertEqual(simulator.scalar('gndname'), 'User ground label')
        self.assertEqual([item.scalar('signal_display_name') for item in simulator.select('signals/signal')], ['User label']*2)
        simulator.one('signals/signal[1]/signal_tp').set_values(1)
        with self.assertRaises(ReferenceError):
            document.rebuild()

    def test_public_xml_signal_keys_follow_key_edits(self):
        document = parse_dchxml('''<Source Type="DipTrace-Schematic"><Schematic>
        <Components><Part Id="12"/></Components><Nets><Net Id="90"/></Nets>
        <Simulator Type="Transient" GndNetId="90"><GndNetName>ground</GndNetName><Signals>
        <Signal Type="Current" Id="12"><DisplayName>i</DisplayName></Signal>
        <Signal Type="Voltage" Id="90"><DisplayName>v</DisplayName></Signal>
        </Signals></Simulator></Schematic></Source>''')
        self.assertEqual(document.references.issues, [])
        document.one('/Source/Schematic/Components/Part/Id').set_values(120)
        document.one('/Source/Schematic/Nets/Net/Id').set_values(900)
        document.rebuild()
        simulator = document.one('/Source/Schematic/Simulator')
        self.assertEqual(simulator.scalar('GndNetId'), 900)
        self.assertEqual([item.scalar('Id') for item in simulator.select('Signals/Signal')], [120, 900])
        self.assertEqual(parse_dchxml(document.to_dchxml_bytes()).references.issues, [])

    def test_unknown_signal_kind_protects_only_possible_target_collections(self):
        document = schematic()
        document.one('/Schematic/ssimulator/signals/signal[1]/signal_tp').set_values(9)
        pages = document.one('/Schematic').add('Pages')
        pages.add('Page', 'A')
        pages.add('Page', 'B')
        bind_schematic_references(document)
        self.assertEqual(len(document.references.issues), 1)
        pages.children()[0].move_to(pages, 1)
        document.rebuild()
        parts = document.one('/Schematic/Components')
        with self.assertRaises(ReferenceError):
            parts.children()[0].move_to(parts, 1)
        document.validate()


if __name__ == '__main__':
    unittest.main()
