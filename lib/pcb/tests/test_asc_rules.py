"""Compact ASC rules become the same editable identities as other PCB inputs."""
from decimal import Decimal
import unittest

from lib.common.asc import loads, dumps
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_asc_core import fixture as core_fixture


RULES = '''(Layers
  (Name Top (Number 0) (Enabled "Y") (Type 0) (NetNumber -1) (HoleSize 1.2) (HoleRing 0.6) (Locked "N"))
  (Name Plane (Number 1) (Enabled "Y") (Type 1) (NetNumber 73) (HoleSize 1.2) (HoleRing 0.6) (Locked "N"))
  (Name Bottom (Number 2) (Enabled "Y") (Type 0) (NetNumber -1) (HoleSize 1.2) (HoleRing 0.6) (Locked "N")))
(ViaStyles (ViaStyle "Through" "Y" 2 1 0 2) (ViaStyle "Blind" "N" 1 0.5 0 1))
(NetClasses
  (NetClass "Default" (AllLayers "Y") (RouteParity "N") (ParityValue 0)
    (LayProperties
      (LayProperty (Width 0.6) (Clearance 0.9) (MinWidth 300) (MaxWidth 0.03)
        (ClearDetails (pt 1 2 3 4 5) (pt -1 6 7 8 9) (pt -1 -1 10 11 12) (pt -1 -1 -1 13 14)))
      (LayProperty (Width 99)))
    (ViaStyle) (RouteLayers))
  (NetClass "Signal" (AllLayers "N") (RouteParity "Y") (ParityValue 2)
    (LayProperties (LayProperty (Width 1)) (LayProperty (Width 2)) (LayProperty (Width 3)))
    (ViaStyle (pt 1)) (RouteLayers (pt "Y") (pt "N") (pt "Y"))))
(ClassToClass "Y")
(CTC_Cells 2
  (Cell 0 0 "Y" (pt -1)) (Cell 0 1 "N" (pt 91) (pt 92) (pt 93))
  (Cell 1 0 "N" (pt 0.1) (pt 0.2) (pt 0.3)) (Cell 1 1 "Y" (pt 0.7)))
(LayerStack "Three copper layers" 7
  (pt -1 "Mask" 2 "Y" 0.03 3.5 0)
  (pt 0 "Copper" 0 "N" 0.1 0 0.6)
  (pt -1 "Dielectric" 2 "Y" 2 4.6 0)
  (pt 1 "Copper" 1 "N" 0.1 0 0.6)
  (pt -1 "Dielectric" 2 "Y" 2 4.6 0)
  (pt 2 "Copper" 0 "N" 0.1 0 0.6)
  (pt -1 "Mask" 2 "Y" 0.03 3.5 0))'''


def fixture():
    source = loads(core_fixture())
    board = source.one('/Board')
    board.one('Components/Component').add('ConnectedLayer', 1)
    board.one('Components/Component').add('ViaStyle', 1)
    board.one('Nets/Net').add('NetClass', 1)
    for node in tuple(loads(RULES).root.children()):
        node.move_to(board)
    return dumps(source, preserve=False)


def settings_fixture():
    source = loads(fixture())
    settings = source.one('/Board').add('Settings')
    for name, value in {'TraceWidth': Decimal('0.8'), 'TraceClearance': Decimal('0.7'),
                        'GridEnabled': 'Y', 'DRC_Name': 'N', 'DRC_AllLayers': 'Y',
                        'DRC_CheckPours': 'Y', 'DRC_ClassToClass': 'Y', 'DRC_OnlineMode': 2,
                        'DRC_Done': 'N', 'DRC_CheckSameComponent': 'Y',
                        'Connectivity_Traces': 'Y', 'Connectivity_Shapes': 'N',
                        'Connectivity_Pours': 'Y'}.items():
        settings.add(name, value)
    clearances = settings.add('DRC_LayClearances')
    sizes = settings.add('DRC_LaySizes')
    for layer in range(2):
        row = clearances.add('DRC_LayClearance')
        row.add('DRC_SameTraceToTrace', Decimal('0.4'))
        for first in range(6):
            row.add('pt', *(100*layer + 10*first + second + 1 for second in range(7)))
        sizes.add('DRC_LaySize', *(10*layer + index for index in range(1, 7)))
    return dumps(source, preserve=False)


class AscRuleTests(unittest.TestCase):
    def test_layer_name_space_spelling_is_specific_to_layer_names(self):
        for spelling, expected in (('Inner!!Layer!', 'Inner  Layer '),
                                   ('"Inner!!Layer!"', '"Inner  Layer "')):
            with self.subTest(spelling=spelling):
                source = fixture().replace('(Name Top', '(Name '+spelling)
                source = source.replace('"Through"', '"Through!Via"')
                result = assemble_rules(prepare_core(source))
                self.assertEqual(result.layers[0]['Name'], expected)
                self.assertEqual(result.via_styles[0]['Name'], 'Through!Via')

    def test_layers_vias_classes_and_stack_share_editable_identity_links(self):
        result = assemble_rules(prepare_core(fixture()))
        board, document = result.document.one('/Board'), result.document
        top, plane, bottom = result.layers.values()
        through, blind = result.via_styles.values()
        default, signal = result.classes.values()
        component, net = result.routing.core.components[17], result.routing.core.nets[73]
        self.assertIs(component['Layer'], plane)
        self.assertIs(component['Via'], blind)
        self.assertIs(plane['Net'], net)
        self.assertIs(net['Class'], signal)
        self.assertIsNone(through['Span'])
        self.assertEqual(blind['Span'], (top, plane))
        self.assertIs(signal.one('AllowedVias/ViaStyle')['Via'], blind)
        rows = signal.select('LayProperties/LayProperty')
        self.assertEqual([row['Layer'] for row in rows], [top, plane, bottom])
        flags = signal.select('RouteLayers/Item')
        self.assertEqual([flag['Layer'] for flag in flags], [top, plane, bottom])
        self.assertEqual([flag['Enabled'] for flag in flags], [True, False, True])
        self.assertTrue(signal['RoutePriority'])
        self.assertEqual(signal['PriorityValue'], 2)
        copper = board.one('LayerStackItems/LayerStackItem[4]')
        self.assertIs(copper['Layer'], plane)
        self.assertEqual(copper.one('Material')['Type'], 1)
        bottom.move_to(bottom.parent, 1)
        self.assertEqual((component['ConnectedLayer'], rows[1]['Lay'], copper['Lay']), (2, 2, 2))
        signal.move_to(signal.parent, 0)
        self.assertEqual(net['NetClass'], 0)
        self.assertFalse(document.complete)
        for node, field in ((plane, 'Number'), (plane, 'NetNumber'), (component, 'ConnectedLayer'),
                            (component, 'ViaStyle'), (net, 'NetClass'), (copper, 'Lay')):
            self.assertIsNone(node.child(field))

    def test_matrix_dimension_is_not_cell_count_and_only_current_symmetric_rules_remain(self):
        result = assemble_rules(prepare_core(fixture()))
        cells = result.document.select('/Board/ClassClearances/Cell')
        self.assertEqual(len(cells), 3)
        default, signal = result.classes.values()
        self.assertEqual([(c['Class1'], c['Class2']) for c in cells],
                         [(default, default), (signal, default), (signal, signal)])
        self.assertIsNone(cells[0]['Clearance'])
        self.assertEqual(cells[2]['Clearance'], Decimal('0.7'))
        layer_rows = cells[1].select('LayerClearances/LayerClearance')
        self.assertEqual([row['Clearance'] for row in layer_rows], list(map(Decimal, ('0.1', '0.2', '0.3'))))
        self.assertEqual([row['Layer'] for row in layer_rows], list(result.layers.values()))
        self.assertTrue(all(not cell.values and cell.child('Values') is None for cell in cells))
        signal.move_to(signal.parent, 0)
        self.assertEqual((cells[1]['NetClass1'], cells[1]['NetClass2']), (0, 1))

    def test_uniform_class_details_and_redundant_layer_diameter_are_normalized(self):
        result = assemble_rules(prepare_core(fixture()))
        rows = result.classes[0].select('LayProperties/LayProperty')
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['Layer'])
        self.assertEqual(rows[0].one('ClearanceDetails')['TraceToSmd'], 4)
        self.assertEqual(rows[0].one('ClearanceDetails')['SmdToCopper'], 14)
        self.assertEqual((rows[0]['MinWidth'], rows[0]['MaxWidth']), (Decimal('0.03'), 300))
        self.assertIsNone(rows[0].child('ClearDetails'))
        self.assertEqual(result.layers[0]['HoleRing'], Decimal('0.6'))
        self.assertIsNone(result.layers[0].child('HoleSize'))

    def test_bad_compact_records_fail_instead_of_guessing(self):
        source = fixture()
        for before, after, message in (
            ('(CTC_Cells 2', '(CTC_Cells 3', 'dimension does not match'),
            ('(Cell 1 1', '(Cell 0 0', 'duplicate class-clearance'),
            ('(Cell 1 1', '(Cell 2 1', 'coordinates'),
            ('"Blind" "N"', '"Blind" "unknown"', 'boolean'),
            ('"N" 1 0.5 0 1', '"N" 1 0.5 0.2 1', 'via value'),
            ('(HoleSize 1.2)', '(HoleSize "unknown")', 'one hole dimension'),
            ('"Three copper layers" 7', '"Three copper layers" 6', 'count does not match'),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(PcbError, message):
                prepare_core(source.replace(before, after))

    def test_layer_hole_spellings_update_one_dimension_in_source_order(self):
        source = fixture()
        for before, after, expected in (
            ('(HoleSize 1.2)', '(HoleSize 3)', Decimal('0.6')),
            ('(HoleSize 1.2)', '', Decimal('0.6')),
            ('(HoleRing 0.6)', '', Decimal('0.6')),
        ):
            with self.subTest(after=after):
                result = assemble_rules(prepare_core(source.replace(before, after)))
                self.assertEqual(result.layers[0]['HoleRing'], expected)
                self.assertIsNone(result.layers[0].child('HoleSize'))
        syntax = loads(source)
        layer = syntax.one('/Board/Layers/Name[1]')
        diameter = layer.one('HoleSize')
        diameter.set_values(3)
        diameter.move_to(layer)
        result = assemble_rules(prepare_core(dumps(syntax, preserve=False)))
        self.assertEqual(result.layers[0]['HoleRing'], Decimal('1.5'))

    def test_unresolved_style_selection_is_an_error(self):
        with self.assertRaisesRegex(PcbError, 'unresolved allowed via style 9'):
            assemble_rules(prepare_core(fixture().replace('(pt 1)', '(pt 9)')))

    def test_routing_defaults_and_drc_use_shared_rules_without_flat_duplicates(self):
        result = assemble_rules(prepare_core(settings_fixture()))
        board = result.document.one('/Board')
        settings = board.one('Settings')
        row = result.classes[0].one('LayProperties/LayProperty')
        self.assertEqual((row['Width'], row['Clearance']), (Decimal('0.8'), Decimal('0.7')))
        self.assertIsNone(settings.child('TraceWidth'))
        self.assertIsNone(settings.one('Routing').child('TraceWidth'))
        settings.one('Routing')['TraceWidth'] = Decimal('0.9')
        self.assertEqual(row['Width'], Decimal('0.9'))
        self.assertTrue(settings['GridEnabled'])
        drc = board.one('DRC')
        self.assertEqual(drc['Name'], 'N')  # Authored strings retain their meaning.
        self.assertTrue(drc['CheckCopperPours'])
        self.assertTrue(drc['CheckClassToClass'])
        self.assertTrue(drc['CheckSameComponentPads'])
        self.assertFalse(drc['DRCDone'])
        self.assertEqual(drc['RealTimeMode'], 2)
        self.assertEqual(len(drc.select('LayClearances/LayClearance')), 1)
        clearances = drc.one('LayClearances/LayClearance')
        self.assertIsNone(clearances['Layer'])
        self.assertEqual(clearances['SameTraceToTrace'], Decimal('0.4'))
        self.assertEqual(clearances.one('ClearanceDetails')['TraceToBoard'], 7)
        self.assertEqual(clearances.one('ClearanceDetails')['ViaToVia'], 12)
        self.assertEqual(drc.one('LaySizes/LaySize')['MaxNonPlatedHole'], 6)
        self.assertEqual(board.one('ConnectivityCheck')['CopperPours'], True)
        self.assertEqual(board.one('ConnectivityCheck')['Shapes'], False)
        self.assertFalse(any(child.kind.startswith(('DRC_', 'Connectivity_')) for child in settings.children()))

    def test_ambiguous_and_malformed_drc_fields_fail(self):
        source = loads(settings_fixture())
        settings = source.one('/Board/Settings')
        settings.add('DRC_CheckCopperPours', 'N')
        with self.assertRaisesRegex(PcbError, 'ambiguous CheckCopperPours'):
            prepare_core(dumps(source, preserve=False))
        source = loads(settings_fixture())
        source.one('/Board/Settings/DRC_LayClearances/DRC_LayClearance[1]/pt[1]').set_values(1, 2)
        with self.assertRaisesRegex(PcbError, 'expected 7 pt values'):
            prepare_core(dumps(source, preserve=False))


if __name__ == '__main__':
    unittest.main()
