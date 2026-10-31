"""XML identities normalize into the existing PCB electrical/routing graph."""
from types import SimpleNamespace
from decimal import Decimal
import unittest

from lib.common.model import Element
from lib.common.units import XmlUnits
from lib.common.xml_records import XmlRecord
from lib.pcb.formats.dipxml.syntax import loads
from lib.pcb.formats.dipxml.patterns import read_patterns
from lib.pcb.formats.dipxml.electrical import read_electrical
from lib.pcb.formats.dipxml.document_settings import read_document_settings
from lib.pcb.formats.dipxml.versions import XmlVersion
from lib.pcb.formats.assembly.routing import assemble_routing
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_dipxml_components import SOURCE


NETS = '''<Nets><Net Id="7" MeanderGap="0.3"><Name>Supply</Name>
  <Pads><Item Comp="8" Pad="17"/></Pads>
  <Traces>
    <Trace Id="91" Connected1="Pad" Object1="8" SubObject1="17" Point1="-1" Connected2="Free">
      <Points><Point Id="40" X="1" Y="-2" Lay="0" Width="0.3"/>
              <Point Id="90" X="3" Y="4" Lay="1" Width="0.6" Arc="Y"/></Points>
      <ConnectedTeardrops><Item>77</Item></ConnectedTeardrops>
    </Trace>
    <Trace Id="13" Connected1="Trace" Object1="7" SubObject1="91" Point1="1" Connected2="Free">
      <Points><Point Id="50" X="3" Y="4" Lay="1" Width="0.6"/>
              <Point Id="60" X="5" Y="6" Lay="1" Width="0.6"/></Points>
    </Trace>
  </Traces>
  <Teardrops><Teardrop Id="77" Lay="0" DrawX="1" DrawY="2"><Points>
    <Point X="1" Y="2"/><Point X="3" Y="4"/><Point X="5" Y="6"/>
  </Points></Teardrop></Teardrops>
</Net></Nets>'''


def prepared(text=None):
    syntax = loads(text or SOURCE.replace('</Components></Board>', '</Components>'+NETS+'</Board>'))
    source = syntax.one('/Source')
    units = XmlUnits(source.scalar('Units'))
    patterns, _ = read_patterns(XmlRecord(source.one('Library')), units=units)
    root = Element('')
    root.add('Units', units.units)
    board = root.add('Board')
    board.add('DesignCache_Count', -1)
    record = XmlRecord(source.one('Board'))
    read_document_settings(record, root, board, units=units, application_version=source.scalar('Version', ''))
    upgrades = read_electrical(record, board, patterns=patterns, units=units,
                              version=XmlVersion.parse(source.scalar('Version', '')))
    record.finish()
    return SimpleNamespace(root=root, board=board, upgrades=upgrades)


class PcbXmlElectricalTests(unittest.TestCase):
    def test_route_modes_accept_the_public_labels_and_equivalent_numeric_aliases(self):
        from lib.pcb.formats.dipxml.nets import ROUTE_MODES
        for mode, name in enumerate(ROUTE_MODES):
            for value in (name, str(mode)):
                with self.subTest(value=value):
                    text = SOURCE.replace('</Components></Board>', '</Components>'+NETS+'</Board>')
                    text = text.replace('Net Id="7"', f'Net Id="7" RouteMode="{value}"')
                    result = assemble_routing(prepared(text))
                    self.assertEqual(result.core.nets[7]['RouteMode'], mode)

    def test_static_via_uses_named_style_geometry_and_enters_the_same_net_graph(self):
        via = '''<Component Id="19" Type="Via" ViaStyle="62" X="2" Y="-3">
          <Name>Static Via</Name><RefDes>V1</RefDes>
          <Pads><Pad Id="1" NetId="7"><CustomSpokes>
            <CustomSpoke Lay="-1" Type="0" Spoke="0" Width="0.5"/>
          </CustomSpokes></Pad></Pads></Component>'''
        text = SOURCE.replace('</Components></Board>', via+'</Components>'+NETS+'</Board>')
        text = text.replace('<Board>', '''<Board><ViaStyles>
          <ViaStyle Id="62" Size="0.6" HoleSize="0.3"><Name>Fine</Name></ViaStyle>
          </ViaStyles>''')
        text = text.replace('<Pads><Item Comp="8" Pad="17"/></Pads>',
                            '<Pads><Item Comp="8" Pad="17"/><Item Comp="19" Pad="1"/></Pads>')
        result = assemble_routing(prepared(text))
        component, pad = result.core.components[19], result.core.pads[19, 1]
        self.assertEqual((component['X'], component['Y'], component['MarkingFontSize']), (6, 9, 5))
        self.assertEqual(component['RefDes_SilkShow'], 0)
        self.assertEqual(component['Datasheet_AssyAlign'], 0)
        self.assertEqual(component.one('Pattern')['Type'], 16)
        self.assertEqual((pad['PadWidth_New'], pad['PadHeight_New'], pad['PadHole']),
                         (Decimal('1.8'), Decimal('1.8'), Decimal('0.9')))
        self.assertIs(pad['Net'], result.core.nets[7])
        self.assertEqual(pad.one('CustomSpokes/CustomSpoke').values, (-1, 0, 0, Decimal('1.5')))
        self.assertEqual(component.one('ViaStyle').values, (0,))

    def test_missing_static_via_style_does_not_invent_geometry(self):
        text = SOURCE.replace('PatternStyle="P" X=', 'Type="Via" ViaStyle="99" X=')
        with self.assertRaisesRegex(PcbError, 'unresolved via style 99'):
            prepared(text)

    def test_public_keys_are_consumed_into_the_shared_identity_graph(self):
        result = assemble_routing(prepared())
        doc, net = result.document, result.core.nets[7]
        first, other = result.traces[7, 91], result.traces[7, 13]
        self.assertIs(first['Target1'], result.core.pads[8, 1])
        self.assertIsNone(first['Target2'])
        self.assertIs(other['Target1'], first.one('Points/Point[2]'))
        self.assertEqual(other['Point1'], 1)
        self.assertEqual(net['MeanderGap'], Decimal('0.9'))
        self.assertEqual(first.one('Points/Point[2]')['Y'], -12)
        self.assertTrue(first.one('Points/Point[2]')['Arc'])
        self.assertEqual(net.one('Teardrops/Teardrop/DrawY').values, (-6,))
        self.assertEqual(first.one('ConnectedTeardrops/Item').values, (77,))
        self.assertFalse(doc.complete)

    def test_reorder_and_connection_edits_use_existing_pcb_constraints(self):
        result = assemble_routing(prepared())
        first, other = result.traces[7, 91], result.traces[7, 13]
        target = other['Target1']
        first.move_to(first.parent, 1)
        self.assertIs(other['Target1'], target)
        self.assertEqual(other['SubObject1'], 1)
        other['Target1'] = first.one('Points/Point[1]')
        self.assertEqual(other['Point1'], 0)
        first['Target1'] = None
        self.assertEqual(first['Connected1'], 'Free')

    def test_duplicate_missing_and_unsupported_references_fail(self):
        original = SOURCE.replace('</Components></Board>', '</Components>'+NETS+'</Board>')
        for before, after in (
                ('Comp="8" Pad="17"', 'Comp="8" Pad="99"'),
                ('Object1="8" SubObject1="17"', 'Object1="8" SubObject1="99"'),
                ('Point1="1"', 'Point1="99"'),
                ('Trace Id="13"', 'Trace Id="91"'),
                ('Connected1="Trace"', 'Connected1="2"')):
            with self.subTest(after=after), self.assertRaises(PcbError):
                prepared(original.replace(before, after))


if __name__ == '__main__':
    unittest.main()
