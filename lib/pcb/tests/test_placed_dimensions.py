"""Placed and board dimensions use local positions, independently of net keys."""
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model.dimensions import LOCAL_ROLES, BOARD_ROLES
from lib.pcb.model.graphic_records import OUTLINE_POINT
from lib.pcb.tests.test_graphics import design as graphics_fixture


def dimension(collection, mode, *, owner=0, member=1, point=0, kind=0):
    node = collection.add('Dimension', len(collection.children()))
    for name, value in dict(Enabled=True, Type=kind, Connected1=mode, Object1=owner,
            SubObject1=member, Point1=point, Connected2=-1, Object2=0, SubObject2=0,
            Point2=0, X1=7, Y1=8, Group=-1).items():
        node.add(name, value)
    return node


def design(*, original_keys=False):
    decoded, _, _ = graphics_fixture()
    board = decoded.board
    board.add('Enabled', True)
    component = board.one('Components/Component')
    pads = component.select('Pattern/Pads/Pad')
    if not original_keys:
        pads[1].one('Number_New').set_values(1)
        pads[2].one('Number_New').set_values(2)
        board.one('Nets/Net/Pads/Item').set_values(41, 1)
    pads[1]['PadShape_New'] = 3
    for x, y in ((0, 0), (2, 0), (2, 1), (0, 1)):
        pads[1].one('PadPoints_New').add('pt', x, y)
    local = component.one('Pattern/Dimensions')
    dimension(local, 0)
    dimension(local, 1)
    dimension(local, 2)
    other = component.clone()
    other.one('Number').set_values(42)
    other.one('RefDes').set_values('U2')
    component.parent.append(other)
    outline = board.add('Points')
    for x, y in ((0, 0), (30, 0), (30, 20), (0, 20)):
        outline.add('pt', x, y, False)
    dimensions = board.add('Dimensions')
    first = dimension(dimensions, 0, owner=41)
    first.one('Connected2').set_values(7)
    first.one('Object2').set_values(42)
    dimension(dimensions, 1, owner=41)
    dimension(dimensions, 2, owner=41)
    dimension(dimensions, 6, point=3)
    dimension(dimensions, 7, owner=42)
    dimension(dimensions, 0, owner=41, point=12)
    return assemble_graphics(decoded)


def link(document, source, *, local=False):
    return document.references.outgoing(source, role=(LOCAL_ROLES if local else BOARD_ROLES)[0])[0]


class PlacedDimensionTests(unittest.TestCase):
    def test_board_keys_and_local_positions_bind_independent_identities(self):
        result = design()
        document = result.document
        component = result.rules.routing.core.components[41]
        first_pad = result.rules.routing.core.pads[41, 1]
        local = component.select('Pattern/Dimensions/Dimension')
        board = document.select('/Board/Dimensions/Dimension')
        self.assertIs(link(document, local[0], local=True).target, first_pad)
        self.assertIs(link(document, board[0]).target, first_pad)
        self.assertEqual(board[0]['Object1'], 0)  # The saved electrical component key was 41.
        self.assertIs(link(document, board[1]).target, component.one('Pattern/Shapes/Shape'))
        self.assertIs(link(document, board[2]).target, component.one('Pattern/Holes/Hole'))
        self.assertIs(link(document, board[3]).target, document.one('/Board/Points/pt[4]'))
        self.assertIs(link(document, board[4]).target, result.rules.routing.core.components[42])
        self.assertIs(link(document, board[5]).target, first_pad.one('PadPoints_New/pt[3]'))
        self.assertIs(document.one('/Board/Points/pt[1]').schema, OUTLINE_POINT)

    def test_reordering_updates_member_and_component_selectors_incrementally(self):
        result = design()
        document, core = result.document, result.rules.routing.core
        component, other = core.components.values()
        dimensions = document.select('/Board/Dimensions/Dimension')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole-document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole-graph scan')):
            other.move_to(other.parent, 0)
            self.assertEqual([node['Object1'] for node in dimensions[:3]], [1, 1, 1])
            self.assertEqual(dimensions[4]['Object1'], 0)
            self.assertEqual(dimensions[0]['Object2'], 0)
            core.pads[41, 2].move_to(component.one('Pattern/Pads'), 0)
            self.assertEqual((dimensions[0]['SubObject1'], dimensions[5]['SubObject1']), (2, 2))
            local_pad = component.one('Pattern/Dimensions/Dimension[1]')
            self.assertEqual(local_pad['SubObject1'], 2)
            vertex = link(document, dimensions[5]).target
            vertex.move_to(vertex.parent, 0)
            self.assertEqual(dimensions[5]['Point1'], 10)
            outline_point = link(document, dimensions[3]).target
            outline_point.move_to(outline_point.parent, 0)
            self.assertEqual(dimensions[3]['Point1'], 0)
            outline_point['Arc'] = True
            self.assertTrue(outline_point['Arc'])

    def test_foreign_targets_vertex_deletion_and_polygon_reinterpretation_fail_atomically(self):
        result = design()
        document, core = result.document, result.rules.routing.core
        dimensions = document.select('/Board/Dimensions/Dimension')
        vertex = link(document, dimensions[5]).target
        with self.assertRaises(ReferenceError):
            core.pads[41, 1]['PadShape_New'] = 0
        with self.assertRaises(ReferenceError):
            document.remove(vertex)
        with self.assertRaises(ReferenceError):
            document.one('/Board')['Enabled'] = False
        self.assertTrue(document.one('/Board')['Enabled'])
        document.references.retarget(link(document, dimensions[0]), core.pads[42, 1])
        self.assertEqual(dimensions[0]['Object1'], 1)
        foreign = document.clone().one('/Board/Components/Component[1]/Pattern/Pads/Pad[1]')
        with self.assertRaises(ReferenceError):
            document.references.retarget(link(document, dimensions[0]), foreign)
        self.assertEqual(core.pads[41, 1]['PadShape_New'], 3)
        copied = document.clone()
        node = copied.one('/Board/Dimensions/Dimension[6]')
        self.assertIs(link(copied, node).target,
            copied.one('/Board/Components/Component[1]/Pattern/Pads/Pad[1]/PadPoints_New/pt[3]'))

    def test_saved_electrical_keys_do_not_make_invalid_local_position_attachments_valid(self):
        @import_diagnostics('dip')
        def load():
            return design(original_keys=True).document
        report = ConversionReport()
        document = load(report=report)
        local = document.one('/Board/Components/Component[1]/Pattern/Dimensions/Dimension[1]')
        self.assertEqual(local['Connected1'], -1)
        self.assertFalse(document.references.outgoing(local))
        pad = document.one('/Board/Components/Component[1]/Pattern/Pads/Pad[1]')
        self.assertIs(pad['Net'], document.one('/Board/Nets/Net'))
        self.assertTrue(any(notice.rule == 'dimension-attachment-normalization' for notice in report.infos))

    def test_invalid_radius_dimensions_are_removed_before_group_binding(self):
        decoded, _, _ = graphics_fixture()
        component = decoded.board.one('Components/Component')
        local = dimension(component.one('Pattern/Dimensions'), 0, member=999, kind=3)
        board = dimension(decoded.board.add('Dimensions'), 6, point=999, kind=3)
        board.one('Group').set_values(8)
        result = assemble_graphics(decoded)
        self.assertIsNone(local.parent)
        self.assertIsNone(board.parent)
        self.assertFalse(result.document.select('/Board/Dimensions/Dimension'))
        self.assertFalse(result.document.select('/Board/Components/Component/Pattern/Dimensions/Dimension'))
        self.assertFalse(result.document.references.outgoing(board))

    def test_unimplemented_board_attachment_modes_remain_explicit_and_guarded(self):
        decoded, _, _ = graphics_fixture()
        node = dimension(decoded.board.add('Dimensions'), 99, owner=0, member=7, point=2)
        result = assemble_graphics(decoded)
        self.assertEqual((node['Connected1'], node['Object1'], node['SubObject1'], node['Point1']), (99, 0, 7, 2))
        issue, = result.document.references.issues
        self.assertIs(issue.source, node)
        self.assertIn('not implemented', issue.message)
        with self.assertRaises(ReferenceError):
            node['Connected1'] = 0


if __name__ == '__main__':
    unittest.main()
