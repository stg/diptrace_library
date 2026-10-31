"""XML rule tables use the existing editable layer/class identity records."""
from decimal import Decimal
import unittest

from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_dipxml_classes import source as class_source
from lib.pcb.tests.test_dipxml_electrical import prepared


DRC = '''<DRC AllLayers="N" CheckClearance="Y" CheckSize="N" CheckJumpers="Y"
      CheckCopperPours="Y" CheckClassToClass="Y" CheckSilk="N" CheckLength="Y"
      CheckKeepouts="Y" CheckSameNet="N" CheckSameComponentPads="Y" CheckCourtyard="Y"
      SilkClearance="0.2"><Name>Fine rules</Name>
  <ShowList>Y</ShowList><RealTimeMode>2</RealTimeMode><DRCDone>N</DRCDone>
  <LayClearances>
    <LayClearance Lay="91" SameSmdToVia="0.3"><ClearanceDetails TraceToBoard="0.4"/></LayClearance>
    <LayClearance Lay="30"><ClearanceDetails TraceToTrace="0.1"/></LayClearance>
    <LayClearance Lay="8"><ClearanceDetails DrillToDrill="0.2"/></LayClearance>
  </LayClearances>
  <LaySizes><LaySize Lay="8" MinTrace="0.2"/><LaySize Lay="91" MinDrill="0.3"/>
    <LaySize Lay="30" MaxRing="0.4"/></LaySizes>
</DRC>'''
CLASS_CLEARANCES = '''<ClassToClass Enabled="Y"><CTC_Cells>
  <Cell NetClass1="4" NetClass2="4" Clearance="-1"/>
  <Cell NetClass1="4" NetClass2="70"><LayerClearances>
    <LayerClearance Id="91" Clearance="0.2"/><LayerClearance Id="30" Clearance="-1"/>
  </LayerClearances></Cell>
  <Cell NetClass1="70" NetClass2="70" Clearance="0.25"/>
</CTC_Cells></ClassToClass>'''


def source():
    return class_source().replace('</Board>', DRC+CLASS_CLEARANCES+'</Board>')


def design(text=None):
    return assemble_rules(prepared(source() if text is None else text))


class PcbXmlDesignRuleTests(unittest.TestCase):
    def test_current_checks_metadata_and_physical_dimensions_are_named(self):
        result = design()
        drc = result.document.one('/Board/DRC')
        self.assertEqual(drc['Name'], 'Fine rules')
        self.assertEqual((drc['CheckClearance'], drc['CheckSize'], drc['CheckJumpers']), (True, False, True))
        self.assertTrue(drc['CheckCopperPours'])
        self.assertTrue(drc['CheckCourtyard'])
        self.assertTrue(drc['CheckKeepouts'])
        self.assertEqual((drc['ShowList'], drc['RealTimeMode'], drc['DRCDone']), (True, 2, False))
        self.assertEqual(drc['SilkClearance'], Decimal('.6'))
        rows = drc.select('LayClearances/LayClearance')
        self.assertEqual([row['Layer'] for row in rows], list(result.layers.values()))
        self.assertEqual(rows[2]['SameSmdToVia'], Decimal('.9'))
        self.assertEqual(rows[0]['SameSmdToVia'], 0)
        self.assertEqual(rows[0].one('ClearanceDetails')['TraceToTrace'], Decimal('.3'))
        self.assertEqual(rows[2].one('ClearanceDetails')['TraceToBoard'], Decimal('1.2'))
        self.assertEqual(rows[1].one('ClearanceDetails')['DrillToDrill'], Decimal('.6'))
        self.assertEqual(rows[0].one('ClearanceDetails')['DrillToBoard'], -1)
        sizes = drc.select('LaySizes/LaySize')
        self.assertEqual([row['Layer'] for row in sizes], list(result.layers.values()))
        self.assertEqual(sizes[0]['MaxRing'], Decimal('1.2'))
        self.assertIsNone(result.document.one('/Board').child('LastDRC'))
        result.document.references.validate()

    def test_symmetric_class_pairs_and_inherited_per_layer_clearances(self):
        result = design()
        board = result.document.one('/Board')
        self.assertTrue(board['ClassToClass'])
        cells = board.select('ClassClearances/Cell')
        self.assertEqual([(cell['NetClass1'], cell['NetClass2']) for cell in cells], [(0, 0), (1, 0), (1, 1)])
        self.assertIsNone(cells[0]['Clearance'])
        self.assertEqual(cells[2]['Clearance'], Decimal('.75'))
        self.assertIs(cells[1]['Class1'], result.classes[1])
        self.assertIs(cells[1]['Class2'], result.classes[0])
        rows = cells[1].select('LayerClearances/LayerClearance')
        self.assertEqual([row['Layer'] for row in rows], list(result.layers.values()))
        self.assertEqual([row['Clearance'] for row in rows], [None, None, Decimal('.6')])
        self.assertFalse(cells[1]['AllLayers'])

    def test_layer_and_class_edits_follow_their_targets_and_clones(self):
        result = design()
        cell = result.document.one('/Board/ClassClearances/Cell[2]')
        bottom = result.layers[2]
        drc_row = result.document.one('/Board/DRC/LayClearances/LayClearance[3]')
        class_row = cell.one('LayerClearances/LayerClearance[3]')
        result.classes[1].move_to(result.classes[1].parent, 0)
        bottom.move_to(bottom.parent, 1)
        self.assertEqual((cell['NetClass1'], cell['NetClass2']), (0, 1))
        self.assertIs(drc_row['Layer'], bottom)
        self.assertEqual(class_row['Lay'], 1)
        class_row['Clearance'] = Decimal('.8')
        self.assertEqual(class_row['Clearance'], Decimal('.8'))
        clone = result.document.clone()
        other = clone.one('/Board/ClassClearances/Cell[2]/LayerClearances/LayerClearance[3]')
        self.assertIsNot(other['Layer'], bottom)
        with self.assertRaises(ReferenceError):
            other['Layer'] = bottom
        result.document.references.validate()
        clone.references.validate()

    def test_uniform_and_last_used_rules_remain_distinct(self):
        last = '''<LastDRC AllLayers="Y" CheckClearance="N"><Name>Previous rules</Name>
          <ShowList>N</ShowList><RealTimeMode>9</RealTimeMode><DRCDone>Y</DRCDone>
          <LayClearances><LayClearance Lay="0"><ClearanceDetails TraceToVia="0.7"/>
          </LayClearance></LayClearances><LaySizes><LaySize Lay="0" MinTrace="0.1"/></LaySizes></LastDRC>'''
        document = design(source().replace('</Board>', last+'</Board>')).document
        current, previous = document.one('/Board/DRC'), document.one('/Board/LastDRC')
        self.assertTrue(current['CheckClearance'])
        self.assertFalse(previous['CheckClearance'])
        self.assertEqual(previous['Name'], 'Previous rules')
        for name in ('ShowList', 'RealTimeMode', 'DRCDone'):
            self.assertIsNone(previous.child(name))
        self.assertEqual(current['RealTimeMode'], 2)
        row = previous.one('LayClearances/LayClearance')
        self.assertIsNone(row['Layer'])
        self.assertEqual(row.one('ClearanceDetails')['TraceToVia'], Decimal('2.1'))
        self.assertIsNone(previous.one('LaySizes/LaySize')['Layer'])

    def test_legacy_pour_spelling_is_selected_at_its_real_version_boundary(self):
        for version, spelling in (('4.3.0.3', 'CheckCoperPours'), ('4.3.0.4', 'CheckCopperPours')):
            with self.subTest(version=version):
                text = source().replace('Version="5.3"', f'Version="{version}"')
                text = text.replace('CheckCopperPours', spelling)
                self.assertTrue(design(text).document.one('/Board/DRC')['CheckCopperPours'])

    def test_invalid_selectors_duplicate_rules_and_unmapped_fields_fail_explicitly(self):
        for before, after in (('NetClass1="4" NetClass2="70"', 'NetClass1="4" NetClass2="71"'),
                              ('Lay="91" MinDrill', 'Lay="99" MinDrill'),
                              ('Id="91" Clearance', 'Id="30" Clearance'),
                              ('NetClass1="70" NetClass2="70"', 'NetClass1="70" NetClass2="4"'),
                              ('SilkClearance="0.2"', 'SilkClearance="0.2" Unexpected="1"')):
            with self.subTest(after=after), self.assertRaises((PcbError, ValueError)):
                design(source().replace(before, after))


if __name__ == '__main__':
    unittest.main()
