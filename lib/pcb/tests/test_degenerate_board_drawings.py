"""Filled-primitive import cleanup preserves survivors and their references."""
from decimal import Decimal, localcontext
import unittest

from lib.common.conversion import ConversionReport
from lib.common.model import Element
from lib.pcb.formats import io
from lib.pcb.formats.assembly.board_drawings import disable_degenerate_drawings
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.model.dimensions import BOARD_ROLES
from lib.pcb.model.objects import new_document
from lib.pcb.tests.test_graphics import design as graphics_fixture
from lib.pcb.tests.test_placed_dimensions import dimension


def drawing(collection, kind, points):
    shape = collection.add('Shape')
    for name, value in dict(Type=kind, Enabled=True, Layer=0, PenWidth=-1,
                            Color=-1, BrushColor=-1, FontColor=-1).items():
        shape.set_field(name, value)
    vertices = shape.add('Points')
    for point in points:
        vertices.add('pt', *point)
    shape.add('TextLine')
    return shape


class DegenerateBoardDrawingTests(unittest.TestCase):
    def test_import_cleanup_across_all_formats_and_output_versions(self):
        source = new_document()
        shapes = source.one('/Board').add('Shapes')
        for kind, points in ((3, ((0, 0), (1, 0))), (5, ((2, 0), (2, 1))),
                (9, ((3, 0), (4, 1))), (2, ((5, 0), (5, 1))),
                (3, ((6, 0), (7, 1))), (9, ((8, 0), (9, 0), (10, 0)))):
            drawing(shapes, kind, points)
        before = [(node.path, node.values) for node in source.root.walk(include_self=True)]
        for format, capability in FORMATS.items():
            for version in capability.write_versions:
                with self.subTest(format=format, version=version):
                    report = ConversionReport()
                    data = io.serialize(source, format=format, version=version, report=ConversionReport())
                    imported = io.parse(data, report=report)
                    kept = imported.select('/Board/Shapes/Shape')
                    self.assertEqual([shape['Type'] for shape in kept], [2, 3, 9])
                    self.assertEqual([shape.one('Points/pt[1]').values for shape in kept], [(5, 0), (6, 0), (8, 0)])
                    notices = [n for n in report.notices if n.rule == 'degenerate-board-drawing']
                    self.assertEqual(len(notices), 1)
                    self.assertEqual(notices[0].severity, 'info')
                    again_report = ConversionReport()
                    again = io.parse(io.serialize(imported, format=format, version=version,
                                                 report=ConversionReport()), report=again_report)
                    self.assertEqual([shape['Type'] for shape in again.select('/Board/Shapes/Shape')], [2, 3, 9])
                    self.assertFalse(any(n.rule == 'degenerate-board-drawing' for n in again_report.notices))
                    imported.references.validate()
                    again.references.validate()
        self.assertEqual([(node.path, node.values) for node in source.root.walk(include_self=True)], before)

    def test_exact_span_boundary_and_limited_polygon_cleanup(self):
        board = Element('Board')
        shapes = board.add('Shapes')
        narrow = drawing(shapes, 3, ((1, 1), (Decimal('.99991'), 2)))
        boundary = drawing(shapes, 5, ((1, 1), (Decimal('.9999'), 2)))
        outlined = drawing(shapes, 4, ((1, 1), (1, 2)))
        one = drawing(shapes, 9, ((1, 1),))
        two = drawing(shapes, 9, ((1, 1), (2, 2)))
        three = drawing(shapes, 9, ((1, 1), (2, 2), (3, 3)))
        removed = disable_degenerate_drawings(board)
        self.assertEqual(removed, (narrow, two))
        self.assertTrue(all(shape['Enabled'] for shape in (boundary, outlined, one, three)))

    def test_compaction_keeps_later_drawing_targets_and_detaches_removed_target(self):
        decoded, _, _ = graphics_fixture()
        board = decoded.board
        removed, retained = board.select('Shapes/Shape')[:2]
        removed.one('Type').set_values(3)
        removed.one('Points_New').add('pt', 4, 2)
        dimensions = board.add('Dimensions')
        unavailable = dimension(dimensions, 5, owner=100)
        available = dimension(dimensions, 5, owner=101)
        result = assemble_graphics(decoded)
        self.assertIsNone(removed.parent)
        self.assertEqual(set(result.drawings), {101})
        self.assertIs(result.drawings[101], retained)
        self.assertEqual(unavailable['Connected1'], -1)
        self.assertEqual((unavailable['X1'], unavailable['Y1']), (7, 8))
        target, = result.document.references.outgoing(available, role=BOARD_ROLES[0])
        self.assertIs(target.target, retained.one('Points/pt'))
        self.assertEqual(available['Object1'], 0)
        result.document.references.validate()

    def test_span_comparison_does_not_depend_on_ambient_decimal_precision(self):
        for precision in (6, 28, 60):
            with self.subTest(precision=precision):
                board = Element('Board')
                narrow = drawing(board.add('Shapes'), 3,
                    ((1, 0), (Decimal('.9999000000000000000000000000000000000001'), 1)))
                with localcontext() as context:
                    context.prec = precision
                    self.assertEqual(disable_degenerate_drawings(board), (narrow,))


if __name__ == '__main__':
    unittest.main()
