"""ASC dimensions keep current attachment identities and independent geometry."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.dimension_projection import project_dimensions
from lib.pcb.formats.asc.graphic_projection import project_graphics
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.errors import PcbError
from lib.pcb.model.dimensions import BOARD_ROLES
from lib.pcb.tests.test_component_projection import project_input, signature
from lib.pcb.tests.test_graphic_projection import design as graphic_design


def dimension(collection, **changes):
    values = dict(Enabled='Y', Locked='N', Type=0, Connected1=6, Object1=0, SubObject1=0,
        Point1=1, Connected2=0, Object2=0, SubObject2=1, Point2=0, Layer=15, NonSignal=0,
        X1=2, Y1=3, X2=4, Y2=5, XD=6, YD=7, ArrowSize=.9, Units=3, VectorFont='Y',
        FontName='Arial', FontSize=1.25, FontScale=1.1, FontWidth=-1, ShowUnits='Y',
        Angle=9.25, ExternalRadius=-1, PointerMode=0, PointerText='Measured', Group=0,
        PanelExclude='Y')
    values.update(changes)
    row = collection.add('Dimension')
    for name, value in values.items():
        row.add(name, value)
    return row


def syntax(document, *, report=None):
    output = project_input(document, report=report)
    board = document.one('/Board')
    target = output.one('/Board')
    for row in tuple(project_graphics(board, report=report).children()):
        row.move_to(target)
    target.append(project_dimensions(board, report=report))
    return output


def design(*, unresolved=False):
    data = syntax(graphic_design())
    board = data.one('/Board')
    dims = board.one('Dimensions')
    dimension(dims)
    dimension(dims, Connected1=5, Object1=0 if unresolved else 1,
              Point1=99 if unresolved else 0, Connected2=4, Object2=0, SubObject2=0, Point2=1)
    dimension(dims, Connected1=7, Object1=0, Point1=0, Connected2=-1, Layer=13,
              NonSignal=-1, Group=-1)
    if unresolved:
        board.one('Shapes/Shape[1]/ShapeType').set_values(8)
    return assemble_graphics(prepare_core(dumps(data, preserve=False))).document


def reopen(document, *, report=None):
    return assemble_graphics(prepare_core(dumps(syntax(document, report=report), preserve=False))).document


class DimensionProjectionTests(unittest.TestCase):
    def test_board_shape_and_hole_indices_account_for_asc_boundary_entries(self):
        data = syntax(graphic_design())
        component = data.one('/Board/Components/Component')
        holes = component.one('Holes')
        hole = holes.add('Hole', 'Y', 'N', 2, 3, 4, 2, -1)
        hole.move_to(holes, 1)
        dimensions = data.one('/Board/Dimensions')
        dimension(dimensions, Connected1=1, Object1=0, SubObject1=1, Point1=1, Connected2=-1)
        dimension(dimensions, Connected1=2, Object1=0, SubObject1=1, Point1=0, Connected2=-1)
        document = assemble_graphics(prepare_core(dumps(data, preserve=False))).document
        current = document.select('/Board/Dimensions/Dimension')
        self.assertEqual([row['SubObject1'] for row in current], [0, 0])
        output = project_dimensions(document.one('/Board'))
        self.assertEqual([row['SubObject1'] for row in output.children()], [1, 1])
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt.one('/Board/Dimensions')), signature(document.one('/Board/Dimensions')))
        self.assertEqual([rebuilt.references.outgoing(row, role=BOARD_ROLES[0])[0].target.kind
                          for row in rebuilt.select('/Board/Dimensions/Dimension')], ['pt', 'Hole'])

    def test_footprint_dimensions_share_projection_but_keep_local_pad_selectors(self):
        data = syntax(graphic_design())
        local = data.one('/Board/Components/Component/Dimensions')
        row = dimension(local, Connected1=0, Object1=0, SubObject1=1, Point1=0,
                        Connected2=-1, Layer=13, Group=-1)
        row.one('NonSignal').detach()
        row.one('PanelExclude').detach()
        document = assemble_graphics(prepare_core(dumps(data, preserve=False))).document
        pattern = document.one('/Board/Components/Component/Pattern')
        pattern.one('Pads/Pad[1]').move_to(pattern.one('Pads'))
        output = project_dimensions(pattern)
        self.assertEqual(output.one('Dimension')['SubObject1'], 2)
        self.assertEqual(output.one('Dimension')['Group'], -1)
        self.assertIsNone(output.one('Dimension').child('NonSignal'))
        rebuilt = reopen(document)
        dimension_row = rebuilt.one('/Board/Components/Component/Pattern/Dimensions/Dimension')
        self.assertEqual(dimension_row['SubObject1'], 2)
        target = rebuilt.references.outgoing(dimension_row, role='pattern-dimension-1')[0].target
        self.assertEqual(target['StringNumber'], '1')

    def test_group_and_custom_layer_choices_follow_reordering(self):
        document = design()
        board = document.one('/Board')
        board.one('Groups').add('Group')['Enabled'] = True
        board.one('Groups/Group[1]').move_to(board.one('Groups'))
        board.one('NonSignals').add('NonSignal', 'Fabrication')
        board.one('NonSignals/NonSignal[1]').move_to(board.one('NonSignals'))
        output = project_dimensions(board)
        self.assertEqual((output.one('Dimension[1]')['Group'], output.one('Dimension[1]')['NonSignal']), (1, 1))
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt.one('/Board/Dimensions')), signature(board.one('Dimensions')))

    def test_geometry_fonts_and_all_current_selectors_round_trip_without_source_changes(self):
        document = design()
        board = document.one('/Board')
        before = signature(board.one('Dimensions'))
        source_text = dumps(document, preserve=False)
        report = ConversionReport()
        current = reopen(document, report=report)
        self.assertEqual(signature(current.one('/Board/Dimensions')), before)
        self.assertEqual(signature(reopen(current).one('/Board/Dimensions')), before)
        self.assertEqual(dumps(document, preserve=False), source_text)
        self.assertEqual(report.notices, [])
        row = project_dimensions(board).one('Dimension[1]')
        self.assertEqual((row['FontSize'], row['Angle'], row['NonSignal']), (Decimal('1.25'), Decimal('9.25'), 0))
        self.assertEqual(project_dimensions(board).one('Dimension[3]')['NonSignal'], -1)
        current.references.validate()

    def test_reorders_and_retargeting_write_current_indices_without_global_scans(self):
        document = design()
        board = document.one('/Board')
        first, second, _ = board.select('Dimensions/Dimension')
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            board.one('Points/pt[2]').move_to(board.one('Points'), 0)
            board.one('Components/Component/Pattern/Pads/Pad[1]').move_to(board.one('Components/Component/Pattern/Pads'))
            board.one('Shapes/Shape[2]').move_to(board.one('Shapes'), 0)
            board.one('CopperPours/CopperPour/Points/pt[2]').move_to(board.one('CopperPours/CopperPour/Points'), 0)
            reference = document.references.outgoing(second, role=BOARD_ROLES[1])[0]
            document.references.retarget(reference, board.one('CopperPours/CopperPour/Points/pt[3]'))
            projected = project_dimensions(board)
        self.assertEqual((projected.one('Dimension[1]')['Point1'], projected.one('Dimension[1]')['SubObject2']), (0, 2))
        self.assertEqual((projected.one('Dimension[2]')['Object1'], projected.one('Dimension[2]')['Point2']), (0, 2))
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt.one('/Board/Dimensions')), signature(board.one('Dimensions')))
        self.assertIs(document.references.outgoing(first, role=BOARD_ROLES[0])[0].target, board.one('Points/pt[1]'))

    def test_known_omissions_have_distinct_severities_and_do_not_mutate_authored_data(self):
        document = design()
        row = document.one('/Board/Dimensions/Dimension[1]')
        row['Selected'], row['FontMono'] = True, True
        report = ConversionReport()
        projected = project_dimensions(document.one('/Board'), report=report)
        self.assertEqual([notice.rule for notice in report.infos], ['dimension-selection'])
        self.assertEqual([notice.rule for notice in report.warnings], ['dimension-font-monospace'])
        self.assertIsNone(projected.one('Dimension[1]').child('Selected'))
        self.assertIsNone(projected.one('Dimension[1]').child('FontMono'))
        self.assertEqual((row['Selected'], row['FontMono']), (True, True))

    def test_unresolved_attachment_remains_explicit_and_reported(self):
        document = design(unresolved=True)
        report = ConversionReport()
        projected = project_dimensions(document.one('/Board'), report=report)
        self.assertEqual(projected.one('Dimension[2]')['Point1'], 99)
        self.assertEqual([notice.rule for notice in report.warnings], ['unresolved-dimension-attachment'])
        current = reopen(document, report=ConversionReport())
        row = current.one('/Board/Dimensions/Dimension[2]')
        self.assertEqual(row['Point1'], 99)
        self.assertTrue(current.references.unresolved_slot(row.one('Point1')))

    def test_unmapped_content_fails_and_required_fields_cannot_be_removed(self):
        document = design()
        row = document.one('/Board/Dimensions/Dimension[1]')
        before = dumps(document, preserve=False)
        with self.assertRaises(ValueError):
            row.one('FontSize').detach()
        self.assertEqual(dumps(document, preserve=False), before)
        row.add('UnmappedSetting', 'retain me')
        before = dumps(document, preserve=False)
        with self.assertRaises(PcbError):
            project_dimensions(document.one('/Board'))
        self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
