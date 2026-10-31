"""Anchor geometry queries use current identities without rewriting annotation data."""
import math
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.references import ReferenceError
from lib.common.drawing_records import POINT, POINTS
from lib.common.footprint_records import TERMINAL, PASTE_SEGMENT
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model.dimension_geometry import attachment_position
from lib.pcb.tests.test_board_dimensions import design as board_design, source
from lib.pcb.tests.test_placed_dimensions import design as placed_design
from lib.pcb.tests.test_dimension_attachments import design as cached_design


class DimensionGeometryTests(unittest.TestCase):
    def test_point_and_rectangle_queries_follow_current_geometry_without_global_scans(self):
        result = board_design()
        document = result.document
        dims = document.select('/Board/Dimensions/Dimension')
        point = document.references.outgoing(dims[0], role='board-dimension-1')[0].target
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole-document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole-graph scan')):
            self.assertEqual(attachment_position(dims[0], 1), (point['X'], point['Y']))
            point['X'] = 50
            self.assertEqual(attachment_position(dims[0], 1)[0], 50)
            self.assertEqual(attachment_position(dims[2], 1), (4, 2))
            result.drawings[100].one('Points/pt[2]')['X'] = 8
            self.assertEqual(attachment_position(dims[2], 1), (8, 2))
        # A query is not a hidden geometry-editing operation.
        self.assertEqual((dims[0]['X1'], dims[0]['Y1']), (7, 8))

    def test_placed_pad_hole_origin_and_polygon_points_use_the_component_frame(self):
        result = placed_design()
        document, core = result.document, result.rules.routing.core
        component = core.components[41]
        component['X'], component['Y'], component['Angle'] = 10, 20, math.pi/2
        pad = core.pads[41, 1]
        pad['X'], pad['Y'], pad['PadAngle'] = 2, 3, math.pi/2
        component.one('Pattern')['OriginX'] = 4
        component.one('Pattern')['OriginY'] = 5
        hole = component.one('Pattern/Holes/Hole')
        hole['X'], hole['Y'] = 1, 2
        dims = document.select('/Board/Dimensions/Dimension')
        self.assertEqual(attachment_position(dims[0], 1), (13, 18))
        self.assertEqual(attachment_position(dims[2], 1), (12, 19))
        # Origin is attached to the second component; move it independently.
        other = core.components[42]
        other['X'], other['Y'] = 30, 40
        other.one('Pattern')['OriginX'], other.one('Pattern')['OriginY'] = 4, 5
        self.assertEqual(attachment_position(dims[4], 1), (34, 45))
        self.assertEqual(attachment_position(dims[5], 1), (11, 17))

    def test_local_anchors_do_not_acquire_board_placement(self):
        result = placed_design()
        component = result.rules.routing.core.components[41]
        component['X'], component['Y'], component['Angle'] = 100, 200, math.pi
        pad = result.rules.routing.core.pads[41, 1]
        pad['X'], pad['Y'] = 2, 3
        local = component.one('Pattern/Dimensions/Dimension[1]')
        self.assertEqual(attachment_position(local, 1), (2, 3))
        cached = cached_design().cached_footprints[0].pattern.one('Dimensions/Dimension[2]')
        self.assertEqual(attachment_position(cached, 1), (2, 1))

    def test_placed_pad_contours_terminals_and_paste_segments_have_named_editable_fields(self):
        decoded = source()
        pattern = decoded.board.one('Components/Component/Pattern')
        pad = pattern.one('Pads/Pad[2]')
        contour = pad.one('PadPoints_New')
        vertex = contour.add('pt', 2, 3)
        terminal = pad.add('PadTerminal', 0)
        terminal.add('Type', 3)
        terminal_point = terminal.add('ShapePoints').add('pt', 4, 5)
        paste = pad.one('PadMask_TopSegments').add('pt', 1, 2, 3, 4)
        default_point = pattern.one('PadPoints').add('pt', 6, 7)
        default_terminal = pattern.add('PadTerminal', 0)
        default_terminal.add('Type', 0)
        result = assemble_graphics(decoded)
        self.assertIs(contour.schema, POINTS)
        for point in (vertex, terminal_point, default_point):
            self.assertIs(point.schema, POINT)
            point['X'] = point['X'] + 10
        self.assertEqual(vertex.values, (12, 3))
        self.assertEqual(terminal_point.values, (14, 5))
        self.assertEqual(default_point.values, (16, 7))
        self.assertIs(terminal.schema, TERMINAL)
        self.assertIs(default_terminal.schema, TERMINAL)
        self.assertEqual((terminal['Index'], terminal['Type']), (0, 3))
        terminal['Angle'] = Decimal('.37')
        self.assertEqual(terminal['Angle'], Decimal('.37'))
        self.assertIs(paste.schema, PASTE_SEGMENT)
        paste['X2'] = 8
        self.assertEqual(paste.values, (1, 2, 8, 4))
        copied = result.document.clone()
        self.assertEqual(copied.one(vertex.path)['X'], 12)
        self.assertIs(copied.one(terminal_point.path).schema, POINT)

    def test_curved_figure_anchor_codes_select_cardinal_extrema_and_center(self):
        expected = ((1, 4), (4, 4), (2.5, 2), (2.5, 6), (2.5, 4))
        for code, position in enumerate(expected):
            decoded = source()
            shape = decoded.board.one('Shapes/Shape[2]')
            shape.one('Type').set_values(4)
            node = decoded.board.one('Dimensions/Dimension[3]')
            node.one('Point1').set_values(code)
            assemble_graphics(decoded)
            self.assertEqual(attachment_position(node, 1), position)

    def test_free_geometry_unknown_calculations_and_unresolved_identity_are_distinct(self):
        decoded = source()
        free = decoded.board.one('Dimensions/Dimension[1]')
        free.one('Connected1').set_values(-1)
        unknown = decoded.board.one('Dimensions/Dimension[4]')
        unknown.one('Point1').set_values(99)
        result = assemble_graphics(decoded)
        self.assertEqual(attachment_position(free, 1), (7, 8))
        radius = result.document.one('/Board/Dimensions/Dimension[6]')
        self.assertIsNone(attachment_position(radius, 1))
        with self.assertRaises(ReferenceError):
            attachment_position(unknown, 1)
        for end in (0, 3, True, '1'):
            with self.subTest(end=end), self.assertRaises(ValueError):
                attachment_position(free, end)


if __name__ == '__main__':
    unittest.main()
