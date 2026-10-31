"""Old board geometry becomes current meaning without old rectangle copies."""
from decimal import Decimal, localcontext
import math
from types import SimpleNamespace
import unittest

from lib.common.model import Element
from lib.pcb.formats.dip.board_drawings import modernize_board_drawings


def drawing(kind, *, orientation=0, first=(1, 2), opposite=(5, 4), version=46):
    shape = Element('Shape')
    shape.add('Type', kind)
    points = shape.add('Points')
    points.add('pt', *first)
    points.add('pt', *opposite)
    item = SimpleNamespace(drawing=shape, orientation=orientation)
    decoded = SimpleNamespace(header=SimpleNamespace(version=version), upgrades=SimpleNamespace(drawings=(item,)))
    return decoded, shape


class BoardDrawingUpgradeTests(unittest.TestCase):
    def test_text_rectangle_has_one_anchor_for_each_old_quarter_turn(self):
        for orientation, anchor in enumerate(((1, 2), (1, 4), (5, 4), (5, 2))):
            with self.subTest(orientation=orientation):
                decoded, shape = drawing(6, orientation=orientation)
                modernize_board_drawings(decoded)
                self.assertEqual([row.values for row in shape.one('Points').children()], [anchor])
                self.assertAlmostEqual(float(shape['TextAngle']), orientation*math.pi/2)
                self.assertEqual((shape['TextHorz'], shape['TextVert'], shape['TextAlign']), (-1, -1, -1))
                self.assertEqual(shape['LineSpacing'], Decimal('1.2'))
                self.assertFalse(shape['Inverted'])
                self.assertFalse(shape['PictureProportions'])

    def test_picture_diagonals_normalize_to_one_anchor_and_positive_dimensions(self):
        for first, opposite in (((1, 2), (5, 4)), ((5, 4), (1, 2)), ((5, 2), (1, 4)), ((1, 4), (5, 2))):
            with self.subTest(first=first):
                decoded, shape = drawing(7, orientation=3, first=first, opposite=opposite)
                modernize_board_drawings(decoded)
                self.assertEqual([row.values for row in shape.one('Points').children()], [(1, 2)])
                self.assertEqual((shape['PictureWidth'], shape['PictureHeight']), (4, 2))
                self.assertEqual(shape['TextAngle'], 0)

    def test_ellipse_uses_shared_geometry_with_the_correct_closure(self):
        for kind, target, count in ((4, 8, 31), (5, 9, 30)):
            with self.subTest(kind=kind):
                decoded, shape = drawing(kind)
                modernize_board_drawings(decoded)
                rows = shape.one('Points').children()
                self.assertEqual((shape['Type'], len(rows)), (target, count))
                self.assertEqual(rows[0].values, (5, 3))
                if kind == 4:
                    self.assertEqual(rows[-1].values, rows[0].values)
                else:
                    self.assertNotEqual(rows[-1].values, rows[0].values)

    def test_ellipse_tolerance_is_not_applied_to_modern_authored_geometry(self):
        decoded, shape = drawing(4, opposite=(Decimal('3.3'), 4))
        modernize_board_drawings(decoded)
        self.assertEqual((shape['Type'], len(shape.one('Points').children())), (4, 2))
        decoded, shape = drawing(4, version=47)
        before = [row.values for row in shape.one('Points').children()]
        modernize_board_drawings(decoded)
        self.assertEqual(shape['Type'], 4)
        self.assertEqual([row.values for row in shape.one('Points').children()], before)
        self.assertIsNone(shape.child('TextAngle'))

    def test_ellipse_classification_uses_exact_spans_at_any_decimal_precision(self):
        for kind, polygon in ((4, 8), (5, 9)):
            for width, expected in (('1000.2999', kind), ('1000.3000', kind), ('1000.3001', polygon)):
                for precision in (6, 28, 60):
                    with self.subTest(kind=kind, width=width, precision=precision), localcontext() as context:
                        context.prec = precision
                        decoded, shape = drawing(kind, first=(Decimal(0), Decimal(0)),
                            opposite=(Decimal(width), Decimal(1000)))
                        modernize_board_drawings(decoded)
                        self.assertEqual(shape['Type'], expected)
                        self.assertEqual(len(shape.one('Points').children()),
                            (31 if kind == 4 else 30) if expected == polygon else 2)

    def test_picture_dimensions_preserve_wire_precision_in_either_direction(self):
        first = (Decimal('10.0001'), Decimal('20.0002'))
        opposite = (Decimal('12355.6790'), Decimal('9896.5434'))
        for corners in ((first, opposite), (opposite, first)):
            for precision in (6, 28, 60):
                with self.subTest(corners=corners, precision=precision), localcontext() as context:
                    context.prec = precision
                    decoded, shape = drawing(7, first=corners[0], opposite=corners[1])
                    modernize_board_drawings(decoded)
                    self.assertEqual((shape['PictureWidth'], shape['PictureHeight']),
                        (Decimal('12345.6789'), Decimal('9876.5432')))
                    self.assertEqual(shape.one('Points/pt').values, first)

    def test_raster_fields_have_their_own_50_gate_and_preserve_authored_data(self):
        decoded, shape = drawing(0, version=49)
        modernize_board_drawings(decoded)
        self.assertEqual((shape['PictureRaster'], shape['Picture_File'], shape['PictureTransparent']), (False, '', 0))
        decoded, shape = drawing(0, version=50)
        shape.add('PictureRaster', True)
        shape.add('Picture_File', 'authored.png')
        shape.add('PictureTransparent', 35)
        before = [(row.kind, row.values) for row in shape.walk(include_self=True)]
        modernize_board_drawings(decoded)
        self.assertEqual([(row.kind, row.values) for row in shape.walk(include_self=True)], before)

    def test_other_primitives_keep_their_points_and_the_upgrade_is_idempotent(self):
        decoded, shape = drawing(1, orientation=1)
        rows = shape.one('Points').children()
        modernize_board_drawings(decoded)
        self.assertEqual(shape.one('Points').children(), rows)
        self.assertEqual([row.values for row in rows], [(1, 2), (5, 4)])
        before = [(node.path, node.values) for node in shape.walk(include_self=True)]
        modernize_board_drawings(decoded)
        self.assertEqual([(node.path, node.values) for node in shape.walk(include_self=True)], before)


if __name__ == '__main__':
    unittest.main()
