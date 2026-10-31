"""ASC saved checks preserve measurements and current target identities."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.graphic_projection import project_graphics
from lib.pcb.formats.asc.net_projection import project_nets
from lib.pcb.formats.asc.pair_projection import project_pairs
from lib.pcb.formats.asc.result_projection import project_results
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_component_projection import project_input, signature
from lib.pcb.tests.test_graphic_projection import design as graphic_design
from lib.pcb.tests.test_net_projection import design as net_design
from lib.pcb.tests.test_drc_length_targets import read as read_length, source as length_source, error as length_error
from lib.pcb.tests.test_drc_pair_targets import read as read_pair, ERRORS as PAIR_ERROR
from lib.pcb.tests.test_dipxml_pairs import source as pair_source


def error(collection, **changes):
    row = collection.add('DesignError')
    values = dict(Enabled='Y', X=1, Y=2, Value=Decimal('.1'), Rule=Decimal('.2'),
        Type=0, RuleType=0, RuleLayer=1, ObjectNetClass1=-1, ObjectNetClass2=-1,
        ObjectType1=4, Object1=0, SubObject1=1, Point1=-1, ExtObject1=-1,
        ObjectType2=7, Object2=0, SubObject2=-1, Point2=-1, ExtObject2=-1)
    values.update(changes)
    for name,value in values.items():
        row.add(name,value)
    row.add('Layers',2).add('pt','N').parent.add('pt','Y')
    return row


def design(*, unresolved=False):
    document = graphic_design()
    data = project_input(document)
    board = data.one('/Board')
    for row in tuple(project_graphics(document.one('/Board')).children()):
        row.move_to(board)
    board.one('Nets').detach()
    board.append(project_nets(net_design().one('/Board')))
    holes = board.one('Components/Component/Holes')
    holes.add('Hole','Y','N',2,3,4,2,-1).move_to(holes,1)
    polygon = board.one('Nets/Net/Teardrops').add('Teardrop')
    polygon.add('Layer',0)
    points = polygon.add('Points')
    for x,y in ((1,1),(2,1),(2,2)):
        points.add('Point',x,y)
    checks = board.add('DesignErrors')
    first = error(checks, Object2=999 if unresolved else 0,
                  RuleLayer=99 if unresolved else 1, ObjectNetClass2=99 if unresolved else -1)
    if unresolved:
        mask = first.one('Layers')
        mask.set_values(100)
        for index in range(2,100):
            mask.add('pt','Y' if index==99 else 'N')
    error(checks, ObjectType1=5, ObjectType2=2)
    error(checks, ObjectType1=0, SubObject1=0, Point1=1,
          ObjectType2=1, Object2=-1, Point2=1)
    error(checks, ObjectType1=2, Object1=-1, SubObject1=-1, ExtObject1=0, ObjectType2=-1, Object2=-1)
    error(checks, ObjectType1=1, Object1=-1, SubObject1=-1, ObjectType2=-1, Object2=-1)
    error(checks, ObjectType1=21, SubObject1=0, ObjectType2=-1, Object2=-1)
    return assemble_graphics(prepare_core(dumps(data,preserve=False))).document


def reopen(document, *, report=None):
    data = project_input(document,report=report)
    board = data.one('/Board')
    board.one('Nets').detach()
    board.append(project_nets(document.one('/Board'),report=report))
    board.append(project_pairs(document.one('/Board'),report=report))
    for row in tuple(project_graphics(document.one('/Board'),report=report).children()):
        row.move_to(board)
    board.append(project_results(document.one('/Board'),report=report))
    return assemble_graphics(prepare_core(dumps(data,preserve=False))).document


class ResultProjectionTests(unittest.TestCase):
    def test_all_ordinary_target_domains_and_supplied_values_round_trip(self):
        document = design()
        before = dumps(document,preserve=False)
        expected = signature(document.one('/Board/DesignErrors'))
        report = ConversionReport()
        rebuilt = reopen(document,report=report)
        self.assertEqual(signature(rebuilt.one('/Board/DesignErrors')),expected)
        self.assertEqual(signature(reopen(rebuilt).one('/Board/DesignErrors')),expected)
        self.assertEqual(dumps(document,preserve=False),before)
        self.assertEqual(report.notices,[])
        self.assertEqual([row['Target1'].kind for row in rebuilt.select('/Board/DesignErrors/DesignError')],
                         ['Pad','Hole','Point','Component','Board','Teardrop'])
        output = project_results(document.one('/Board'))
        self.assertEqual([row['SubObject1'] for row in output.children()[:2]],[1,1])
        rebuilt.references.validate()

    def test_reorders_generate_current_pad_hole_point_and_layer_numbers(self):
        document = design()
        board = document.one('/Board')
        board.one('Components/Component/Pattern/Pads/Pad[1]').move_to(board.one('Components/Component/Pattern/Pads'))
        board.one('Nets/Net/Traces/Trace/Points/Point[2]').move_to(board.one('Nets/Net/Traces/Trace/Points'))
        board.one('Layers/Layer[2]').move_to(board.one('Layers'),0)
        before = signature(board.one('DesignErrors'))
        output = project_results(board)
        self.assertEqual(output.one('DesignError[1]')['SubObject1'],2)
        self.assertEqual(output.one('DesignError[3]')['Point1'],2)
        self.assertEqual(output.one('DesignError[1]')['RuleLayer'],0)
        self.assertEqual([row.values for row in output.select('DesignError[1]/Layers/pt')],[('Y',),('N',)])
        self.assertEqual(signature(reopen(document).one('/Board/DesignErrors')),before)

    def test_unavailable_targets_classes_and_layer_mask_entries_remain_explicit(self):
        document = design(unresolved=True)
        report = ConversionReport()
        output = project_results(document.one('/Board'),report=report)
        first = output.one('DesignError[1]')
        self.assertEqual((first['Object2'],first['RuleLayer'],first['ObjectNetClass2']),(999,99,99))
        self.assertEqual(first.one('Layers').values,(100,))
        self.assertEqual(first.one('Layers/pt[100]').values,('Y',))
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'unresolved-design-error-targets','unresolved-design-error-layer','unresolved-design-error-class'})
        rebuilt = reopen(document,report=ConversionReport()).one('/Board/DesignErrors/DesignError[1]')
        self.assertEqual(rebuilt.one('UnresolvedTarget2').values,(999,-1,-1,-1))
        self.assertEqual(rebuilt['UnresolvedObjectNetClass2'],99)

    def test_explicit_target_clear_does_not_become_an_unresolved_target_on_import(self):
        document = design()
        for row in document.select('/Board/DesignErrors/DesignError'):
            row['Target1'],row['Target2'] = None,None
        report = ConversionReport()
        rebuilt = reopen(document,report=report)
        self.assertEqual(report.warnings,[])
        self.assertIn('detached-outline-check',[notice.rule for notice in report.infos])
        self.assertTrue(all(row['Target1'] is None and row['Target2'] is None
                            for row in rebuilt.select('/Board/DesignErrors/DesignError')))
        self.assertEqual(rebuilt.references.issues,[])
        self.assertEqual(document.one('/Board/DesignErrors/DesignError[5]')['ObjectType1'],1)

    def test_differential_center_target_survives_output_and_reordered_points(self):
        document = read_pair(pair_source().replace('</Board>',PAIR_ERROR+'</Board>'),report=ConversionReport())
        center = document.one('/Board/DesignErrors/DesignError')['Target1']
        document.copy(center,index=0)
        output = project_results(document.one('/Board'))
        self.assertEqual(output.one('DesignError')['Point1'],1)
        rebuilt = reopen(document,report=ConversionReport())
        row = rebuilt.one('/Board/DesignErrors/DesignError')
        self.assertEqual(row['Target1']._ordinal(),1)
        self.assertEqual((row['X'],row['Y'],row['Value'],row['Rule']),(3,-6,Decimal('.9'),Decimal('1.2')))

    def test_length_targets_and_class_origins_use_the_same_selected_default_export_order(self):
        document = read_length(length_source(length_error(0),length_error(1)),report=ConversionReport())
        board = document.one('/Board')
        first,second = board.select('NetClasses/NetClass')
        first['CheckLength'] = True
        board['DefaultClass'] = second
        row = board.one('DesignErrors/DesignError[2]')
        row['NetClass1'] = second
        self.assertEqual(row['Object1'],1)
        output = project_results(board)
        self.assertEqual((output.one('DesignError[2]')['Object1'],output.one('DesignError[2]')['ObjectNetClass1']),(0,0))
        rebuilt = reopen(document,report=ConversionReport())
        current = rebuilt.one('/Board/DesignErrors/DesignError[2]')
        self.assertEqual(current['NetClass1']['Name'],second['Name'])
        self.assertEqual(current['Target1'].parent.parent.parent['Name'],second['Name'])
        self.assertEqual((current['Value'],current['Rule']),(row['Value'],row['Rule']))

    def test_unknown_extensions_and_unimplemented_target_domains_fail(self):
        for unknown in (True,False):
            document = design()
            row = document.one('/Board/DesignErrors/DesignError[1]')
            if unknown:
                row.add('UnmappedSetting',12)
            else:
                row['Target1'] = None
                row['ObjectType1'] = 28
            before = dumps(document,preserve=False)
            with self.subTest(unknown=unknown),self.assertRaises(PcbError):
                project_results(document.one('/Board'))
            self.assertEqual(dumps(document,preserve=False),before)

    def test_previous_rule_snapshot_omission_warns_without_mutation(self):
        document = design()
        board = document.one('/Board')
        snapshot = board.add('LastDRC')
        snapshot['Name'] = 'Previously checked rules'
        snapshot['CheckClearance'] = False
        before,report = dumps(document,preserve=False),ConversionReport()
        project_results(board,report=report)
        self.assertEqual([notice.rule for notice in report.warnings],['last-design-rules'])
        self.assertEqual(dumps(document,preserve=False),before)


if __name__ == '__main__':
    unittest.main()
