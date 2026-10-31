"""Board dimensions follow trace, pour and drawing identities through edits."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model.dimensions import BOARD_ROLES
from lib.pcb.tests.test_graphics import design as graphics_fixture
from lib.pcb.tests.test_placed_dimensions import dimension
from lib.pcb.tests.test_routing_assembly import trace


def source():
    decoded, _, _ = graphics_fixture()
    board = decoded.board
    net = board.one('Nets/Net')
    other = board.one('Nets').add('Net')
    for name, value in dict(Number=98, Enabled=True, Name='Return').items():
        other.add(name, value)
    other.add('Pads')
    other_traces = other.add('Traces')
    traces = net.add('Traces')
    first = trace(traces, 19, (-1, 0, 0, 0), (-1, 0, 0, 0))
    second = trace(traces, 32, (-1, 0, 0, 0), (-1, 0, 0, 0))
    third = trace(other_traces, 84, (-1, 0, 0, 0), (-1, 0, 0, 0))
    for item in (first, second, third):
        for index in (2, 3):
            point = item.trace.one('Points').add('Point', index)
            point.add('X', index)
            point.add('Y', 2)
    decoded.upgrades.nets = (SimpleNamespace(net=net, traces=(first, second)),
                             SimpleNamespace(net=other, traces=(third,)))

    shapes = board.one('Shapes')
    rectangle, polygon, _ = shapes.children()
    rectangle.one('Type').set_values(2)
    rectangle.one('Points_New').add('pt', 4, 6)
    polygon.one('Points_New').add('pt', 3, 2)
    polygon.one('Points_New').add('pt', 3, 5)
    line = rectangle.clone()
    line.one('Type').set_values(0)
    shapes.append(line)
    disabled = rectangle.clone()
    disabled.one('Enabled').set_values(False)
    shapes.insert(disabled, 0)
    for index, shape in enumerate(shapes.children()):
        shape.set_values(index)
    decoded.upgrades.drawings += (SimpleNamespace(drawing=line, previous_number=103),)

    pours = board.one('CopperPours')
    pour = pours.one('CopperPour')
    for x, y in ((5, 4), (5, 6), (3, 6)):
        pour.one('Points').add('pt', x, y)
    disabled_pour = pour.clone()
    disabled_pour.one('Enabled').set_values(False)
    pours.insert(disabled_pour, 0)
    other_pour = pour.clone()
    pours.append(other_pour)
    for index, row in enumerate(pours.children()):
        row.set_values(index)
    decoded.upgrades.pours += (SimpleNamespace(pour=other_pour, previous_number=700, regions_counted=True),)

    dimensions = board.add('Dimensions')
    first_dim = dimension(dimensions, 3, owner=73, member=32, point=2)
    for name, value in dict(Connected2=4, Object2=500, Point2=1).items():
        first_dim.one(name).set_values(value)
    dimension(dimensions, 4, owner=500, point=3)
    dimension(dimensions, 5, owner=100, point=3)
    dimension(dimensions, 5, owner=101, point=2)
    dimension(dimensions, 5, owner=103, point=1)
    dimension(dimensions, 3, owner=73, member=19, point=1, kind=3)
    dimension(dimensions, 3, owner=98, member=84, point=0)
    return decoded


def design():
    return assemble_graphics(source())


def link(document, node, side=1):
    return document.references.outgoing(node, role=BOARD_ROLES[side-1])[0]


class BoardDimensionTests(unittest.TestCase):
    def test_missing_saved_keys_do_not_select_valid_collection_positions(self):
        decoded = source()
        collection = decoded.board.one('Dimensions')
        controls = [dimension(collection, mode, owner=key) for mode, key in
                    ((7, 0), (3, 0), (4, 1), (5, 1))]

        @import_diagnostics('asc')
        def read():
            return assemble_graphics(decoded).document

        report = ConversionReport()
        document = read(report=report)
        for node in controls:
            self.assertEqual(node['Connected1'], -1)
            self.assertFalse(document.references.outgoing(node, role=BOARD_ROLES[0]))
        self.assertEqual(sum(n.rule == 'dimension-attachment-normalization'
                             for n in report.infos), 4)
        document.references.validate()

    def test_trace_cleanup_preserves_surviving_targets_and_frees_removed_targets(self):
        decoded = source()
        first, survivor = decoded.upgrades.nets[0].traces
        points = first.trace.one('Points').children('Point')
        for point in points[:2]:
            point.one('X').set_values(0)
            point.one('Y').set_values(0)
        for point in points[2:]:
            point.detach()
        removed = dimension(decoded.board.one('Dimensions'), 3, owner=73, member=19)

        @import_diagnostics('asc')
        def read():
            return assemble_graphics(decoded).document

        document = read(report=ConversionReport())
        current = document.one('/Board/Dimensions/Dimension[1]')
        self.assertIsNone(first.trace.parent)
        self.assertIs(link(document, current).target, survivor.trace.one('Points/Point[3]'))
        self.assertEqual((current['Object1'], current['SubObject1'], current['Point1']), (0, 0, 2))
        self.assertEqual(removed['Connected1'], -1)
        self.assertFalse(document.references.outgoing(removed, role=BOARD_ROLES[0]))
        self.assertEqual(len(document.select('/Board/Dimensions/Dimension')), 7)
        document.references.validate()

    def test_import_uses_saved_keys_and_keeps_corner_codes_distinct_from_vertices(self):
        result = design()
        document = result.document
        dims = document.select('/Board/Dimensions/Dimension')
        net = result.rules.routing.core.nets[73]
        self.assertIs(link(document, dims[0]).target, net.one('Traces/Trace[2]/Points/Point[3]'))
        self.assertEqual((dims[0]['Object1'], dims[0]['SubObject1'], dims[0]['Point1']), (0, 1, 2))
        self.assertIs(link(document, dims[1]).target, result.pours[500].one('Points/pt[4]'))
        self.assertEqual(dims[1]['Object1'], 0)  # A disabled source slot was consumed.
        self.assertIs(link(document, dims[2]).target, result.drawings[100])
        self.assertEqual((dims[2]['Object1'], dims[2]['Point1']), (0, 3))
        self.assertIs(link(document, dims[3]).target, result.drawings[101].one('Points/pt[3]'))
        self.assertIs(link(document, dims[4]).target, result.drawings[103].one('Points/pt[2]'))
        self.assertIs(link(document, dims[0], 2).target, result.pours[500].one('Points/pt[2]'))
        self.assertFalse(document.references.issues)

    def test_reordering_projects_all_dependent_indices_without_global_scans(self):
        result = design()
        document = result.document
        dims = document.select('/Board/Dimensions/Dimension')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole-document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole-graph scan')):
            point = link(document, dims[0]).target
            point.move_to(point.parent, 0)
            self.assertEqual(dims[0]['Point1'], 0)
            trace = point.parent.parent
            trace.move_to(trace.parent, 0)
            self.assertEqual(dims[0]['SubObject1'], 0)
            other = result.rules.routing.core.nets[98]
            other.move_to(other.parent, 0)
            self.assertEqual((dims[0]['Object1'], dims[6]['Object1']), (1, 0))
            contour = link(document, dims[1]).target
            contour.move_to(contour.parent, 0)
            self.assertEqual((dims[1]['Point1'], dims[0]['Point2']), (0, 2))
            result.pours[700].move_to(result.pours[700].parent, 0)
            self.assertEqual((dims[1]['Object1'], dims[0]['Object2']), (1, 1))
            rectangle = result.drawings[100]
            rectangle.move_to(rectangle.parent, 2)
            self.assertEqual((dims[2]['Object1'], dims[2]['Point1']), (2, 3))
            for node in dims[3:5]:
                vertex = link(document, node).target
                vertex.move_to(vertex.parent, 0)
                self.assertEqual(node['Point1'], 0)

    def test_radius_boundaries_shape_modes_and_referenced_deletion_are_atomic(self):
        result = design()
        document = result.document
        dims = document.select('/Board/Dimensions/Dimension')
        radius = link(document, dims[5]).target
        for operation in (lambda: radius.move_to(radius.parent, 0),
                          lambda: dims[6].set('Type', 3),
                          lambda: result.pours[500].set('Enabled', False),
                          lambda: result.drawings[101].set('Type', 2),
                          lambda: result.drawings[100].set('Type', 0),
                          lambda: document.remove(link(document, dims[1]).target)):
            with self.assertRaises(ReferenceError):
                operation()
        self.assertEqual(radius._ordinal(), 1)
        self.assertEqual(dims[6]['Type'], 0)
        self.assertTrue(result.pours[500]['Enabled'])
        self.assertEqual((result.drawings[101]['Type'], result.drawings[100]['Type']), (8, 2))

    def test_copy_clone_and_retarget_preserve_target_scope(self):
        document = design().document
        dims = document.select('/Board/Dimensions/Dimension')
        copied = document.copy(dims[1], parent=dims[1].parent)
        self.assertIs(link(document, copied).target, link(document, dims[1]).target)
        target = link(document, dims[1]).target.parent.children()[1]
        document.references.retarget(link(document, copied), target)
        self.assertEqual(copied['Point1'], 1)
        clone = document.clone()
        node = clone.one('/Board/Dimensions/Dimension[2]')
        self.assertIs(link(clone, node).target, clone.one('/Board/CopperPours/CopperPour[1]/Points/pt[4]'))
        with self.assertRaises(ReferenceError):
            document.references.retarget(link(document, copied), link(clone, node).target)

    def test_an_ordinary_arc_attachment_follows_its_actual_control_point(self):
        decoded = source()
        arc = decoded.board.one('Shapes/Shape[5]')
        arc.one('Type').set_values(1)
        arc.one('Points_New').add('pt', 6, 3)
        node = decoded.board.one('Dimensions/Dimension[5]')
        node.one('Point1').set_values(2)
        result = assemble_graphics(decoded)
        point = arc.one('Points/pt[3]')
        self.assertIs(link(result.document, node).target, point)
        point.move_to(point.parent, 0)
        self.assertEqual(node['Point1'], 0)

    def test_mixed_attachment_modes_keep_the_outline_lookup_independent(self):
        decoded = source()
        outline = decoded.board.add('Points')
        for x, y in ((0, 0), (20, 0), (20, 10)):
            outline.add('pt', x, y, False)
        node = dimension(decoded.board.one('Dimensions'), 6, member=0, point=2)
        result = assemble_graphics(decoded)
        self.assertIs(link(result.document, node).target, outline.one('pt[3]'))

    def test_invalid_known_attachments_modernize_before_group_binding(self):
        decoded = source()
        dims = decoded.board.select('Dimensions/Dimension')
        dims[0].one('Point1').set_values(99)
        dims[1].one('Point1').set_values(99)
        dims[2].one('Object1').set_values(0)  # Disabled source drawing.
        dims[5].one('Point1').set_values(0)  # A radius cannot use a trace endpoint.
        dims[5].one('Group').set_values(8)

        @import_diagnostics('dip')
        def load():
            return assemble_graphics(decoded).document
        report = ConversionReport()
        document = load(report=report)
        self.assertEqual([node['Connected1'] for node in dims[:3]], [-1, -1, -1])
        self.assertEqual((dims[0]['X1'], dims[0]['Y1']), (7, 8))
        self.assertIsNone(dims[5].parent)
        self.assertFalse(document.references.outgoing(dims[5]))
        self.assertTrue(any(notice.rule == 'dimension-attachment-normalization' for notice in report.infos))

    def test_missing_drawing_vertex_stays_explicit_without_an_invented_loading_repair(self):
        decoded = source()
        node = decoded.board.one('Dimensions/Dimension[4]')
        node.one('Point1').set_values(99)
        result = assemble_graphics(decoded)
        self.assertEqual((node['Connected1'], node['Point1']), (5, 99))
        self.assertTrue(result.document.references.unresolved_slot(node.one('Point1')))
        with self.assertRaises(ReferenceError):
            result.drawings[101].one('Points').add('pt', 8, 9)


if __name__ == '__main__':
    unittest.main()
