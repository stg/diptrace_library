"""PCB geometry/text shares the neutral definitions used by schematics."""
import unittest

from lib.common import drawing_records
from lib.common.model import Element
from lib.schematic.model import collections, field_groups
from lib.pcb.model import graphic_records


class SharedDrawingTests(unittest.TestCase):
    def test_both_families_use_one_point_and_text_vocabulary(self):
        self.assertIs(field_groups.POINT, drawing_records.POINT)
        self.assertIs(graphic_records.POINT, drawing_records.POINT)
        self.assertIs(field_groups.TEXT_LINE, drawing_records.TEXT_LINE)
        self.assertIs(graphic_records.TEXT_LINE, drawing_records.TEXT_LINE)
        self.assertIs(collections.COLLECTIONS['Points'], graphic_records.POINTS)
        self.assertIs(collections.COLLECTIONS['TextLines'], graphic_records.TEXT_LINES)
        point = Element('pt', 1, 2).bind_schema(drawing_records.POINT)
        point['X'] = 3
        self.assertEqual(point.values, (3, 2))
        text = Element('pt', 'Label').bind_schema(drawing_records.TEXT_LINE)
        text['Text'] = 'Changed'
        self.assertEqual(text.values, ('Changed',))


if __name__ == '__main__':
    unittest.main()
