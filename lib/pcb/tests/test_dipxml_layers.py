"""PCB XML source IDs and explicit stack spans become ordinary model links."""
from decimal import Decimal
import unittest

from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.tests.test_dipxml_components import SOURCE
from lib.pcb.tests.test_dipxml_electrical import NETS, prepared


LAYERS = '''<CopperLayers>
  <Lay Id="30" Color="19"><Name>Top</Name></Lay>
  <Lay Id="8" Type="Plane" PlanePad="Fixed Ring" PlaneRing="0.25" NetId="7">
    <Name>Inner</Name></Lay>
  <Lay Id="91"><Name>Bottom</Name></Lay>
</CopperLayers>
<LayerStackName>Custom</LayerStackName><LayerStackItems>
  <LayerStackItem Lay="30"><Material Type="Conductor" Thickness="0.035">
    <Name>Copper</Name></Material></LayerStackItem>
  <LayerStackItem Lay="8"><Material Type="Plane" Thickness="0.07" Constant="1">
    <Name>Plane copper</Name></Material></LayerStackItem>
  <LayerStackItem Lay="91"><Material Type="Conductor" Thickness="0.035">
    <Name>Copper</Name></Material></LayerStackItem>
</LayerStackItems>
<ViaStyles>
  <ViaStyle Id="62" Size="0.6" HoleSize="0.3"><Name>Through</Name></ViaStyle>
  <ViaStyle Id="17" Lay1="0" Lay2="1" Size="0.5" HoleSize="0.2"><Name>Blind</Name></ViaStyle>
  <ViaStyle Id="24" Lay1="0" Lay2="2" Size="0.7" HoleSize="0.4"><Name>Outside span</Name></ViaStyle>
</ViaStyles>'''


def source():
    start = SOURCE.index('<CopperLayers>')
    stop = SOURCE.index('</CopperLayers>', start)+len('</CopperLayers>')
    text = SOURCE[:start]+LAYERS+SOURCE[stop:]
    nets = NETS.replace('Lay="0"', 'Lay="30"').replace('Lay="1"', 'Lay="91"')
    nets = nets.replace('Point Id="40"', 'Point ViaStyle="17" Id="40"')
    text = text.replace('</Components></Board>', '</Components>'+nets+'</Board>')
    return text.replace('<TeardropParams Smd=', '''<CustomSpokes>
      <CustomSpoke Lay="8" Type="1" Spoke="4" Width="0.15"/>
      </CustomSpokes><TeardropParams Smd=''', 1)


class PcbXmlLayerTests(unittest.TestCase):
    def test_ids_are_resolved_before_rule_assembly_and_not_retained_as_model_keys(self):
        result = assemble_rules(prepared(source()))
        doc, board = result.document, result.document.one('/Board')
        top, inner, bottom = board.one('Layers').children()
        point = result.routing.traces[7, 91].one('Points/Point[1]')
        thermal = result.routing.core.pads[8, 1].one('CustomSpokes/CustomSpoke')
        self.assertIs(point['Layer'], top)
        self.assertIs(point['Via'], result.via_styles[1])
        self.assertIs(thermal['Layer'], inner)
        self.assertEqual(thermal['Width'], Decimal('0.45'))
        self.assertEqual(inner['HoleRing'], Decimal('0.75'))
        self.assertIs(inner['Net'], result.routing.core.nets[7])
        self.assertEqual((top['Number'], inner['Number'], bottom['Number']), (0, 1, 2))
        stack = board.select('LayerStackItems/LayerStackItem')
        self.assertEqual([row['Layer'] for row in stack], [top, inner, bottom])
        self.assertEqual(stack[1].one('Material')['Thickness'], Decimal('0.21'))
        self.assertEqual(stack[1].one('Material')['Type'], inner['Type'])
        self.assertFalse(doc.complete)

    def test_via_span_uses_stack_positions_and_full_span_remains_dynamic(self):
        result = assemble_rules(prepared(source()))
        layers = result.document.one('/Board/Layers').children()
        through, blind, outside = result.via_styles.values()
        self.assertIsNone(through['Span'])
        self.assertEqual(blind['Span'], tuple(layers[:2]))
        self.assertIsNone(outside['Span'])
        # A stable identity remains the target when an unrelated style moves.
        point = result.routing.traces[7, 91].one('Points/Point[1]')
        through.move_to(through.parent, 2)
        self.assertIs(point['Via'], blind)
        self.assertEqual(point['ViaStyle'], 0)

    def test_unknown_or_duplicate_keys_and_unimplemented_span_attributes_fail(self):
        for before, after in (('Lay Id="8"', 'Lay Id="30"'),
                              ('Point ViaStyle="17"', 'Point ViaStyle="18"'),
                              ('CustomSpoke Lay="8"', 'CustomSpoke Lay="88"'),
                              ('LayerStackItem Lay="91"', 'LayerStackItem Lay="99"'),
                              ('ViaStyle Id="17"', 'ViaStyle Id="62"'),
                              ('Lay Id="91"', 'Lay Id="-1"'),
                              ('ViaStyle Id="62"', 'ViaStyle Through="N" Id="62"')):
            with self.subTest(after=after), self.assertRaises(ValueError):
                prepared(source().replace(before, after))


if __name__ == '__main__':
    unittest.main()
