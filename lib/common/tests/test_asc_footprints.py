"""Flat ASC drawing fields retain data and ownership without repeated scans."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.asc import loads
from lib.common.asc_footprints import unpack_pattern_shapes
from lib.common.model import Element
from lib.common.schema import Record


def flat_shapes(count):
    rows = []
    for index in range(count):
        rows.append(f'''(Shape 7 N 1 0 0 0 0 0 0 "old" "Vector" Y 5 1 -1 0.25 8 2)
            (Width {index}.125)
            (TextAngle 0.75)
            (Points (pt {index} 2.5))
            (TextLines (TextLine "first-{index}") (TextLine "second-{index}"))''')
    return loads('(Shapes 17 '+''.join(rows)+')')


class AscFootprintGroupingTests(unittest.TestCase):
    def test_flat_fields_keep_identity_order_and_current_values(self):
        document = flat_shapes(3)
        container = document.one('/Shapes')
        headers = container.children('Shape')
        widths = container.children('Width')
        lexical_value = widths[1].arguments[0]
        # Warm both caches before reparenting the fields.
        container.children()
        document._identity_index = {node.uid: node for node in document.root.walk()}
        unpack_pattern_shapes(container, pad_id=False, points_name='Points',
                              header_fields=(('Layer', 2), ('TextAngle', 15)))
        self.assertEqual(container.values, (17,))
        self.assertEqual(container.children(), headers)
        self.assertIsNone(document._identity_index)
        for index, shape in enumerate(headers):
            self.assertEqual(shape.values, (index,))
            self.assertIs(shape.one('Width'), widths[index])
            self.assertIs(widths[index]._owner(), document)
            self.assertEqual(shape.get('Width'), Decimal(index)+Decimal('.125'))
            self.assertEqual(shape.get('TextAngle'), Decimal('.75'))
            self.assertEqual(shape.one('Points_New/pt').values, (index, Decimal('2.5')))
            self.assertEqual([p.values[0] for p in shape.select('TextLine/pt')],
                             [f'first-{index}', f'second-{index}'])
        self.assertIs(widths[1].arguments[0], lexical_value)

    def test_large_unbound_stream_has_linear_source_scan_work(self):
        container = flat_shapes(160).one('/Shapes')
        size = len(container.items)
        scanned = 0
        original = Element._stored_child_sequence

        def tracked(node, kind=None):
            nonlocal scanned
            if node is container:
                scanned += len(node.items)
            return original(node, kind)

        with patch.object(Element, '_stored_child_sequence', tracked):
            unpack_pattern_shapes(container, points_name='Points')
        self.assertEqual(len(container.children('Shape')), 160)
        self.assertLessEqual(scanned, 4*size)

    def test_declared_container_keeps_the_coordinated_move_path(self):
        container = flat_shapes(2).one('/Shapes').clone()
        container.bind_schema(Record('DeclaredDrawingStream', {}))
        moved = []
        original = Element.move_to

        def tracked(node, parent, index=None):
            moved.append(node)
            return original(node, parent, index)

        with patch.object(Element, 'move_to', tracked):
            unpack_pattern_shapes(container, points_name='Points')
        self.assertEqual(len(moved), 8)
        self.assertEqual(len(container.children('Shape')), 2)
        self.assertEqual(container.one('Shape[1]/Points_New/pt').values, (0, Decimal('2.5')))


if __name__ == '__main__':
    unittest.main()
