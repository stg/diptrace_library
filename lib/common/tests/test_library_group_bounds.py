"""Derived group coordinates follow field, child and membership edits atomically."""
import unittest

from lib.common.model import Document, Element
from lib.common.references import Property
from lib.common.references import Guard, ReferenceError
from lib.common.schema import Field, Record
from lib.common.drawing_records import POINT, TEXT_LINE
from lib.common.unplaced_footprint_objects import new_pad, new_group, new_drawing


class LibraryGroupBoundsTests(unittest.TestCase):
    def example(self):
        document = Document()
        groups = document.root.add('Groups')
        group = groups.append(new_group())
        pad = document.root.add('Pads').append(new_pad('1', x=12, y=6))
        pad['Group'] = group
        mirror = document.root.add('Mirror').bind_schema(Record('Mirror', {
            'X': Field('X', 'number'), 'Y': Field('Y', 'number')}))
        mirror.add('X', 0)
        mirror.add('Y', 0)
        document.references.bind(mirror, group, Property(mirror.one('X'), 'X'),
                                 Property(mirror.one('Y'), 'Y'), role='measure')
        return document, group, pad, mirror

    def test_derived_values_have_no_stored_duplicate_and_follow_members(self):
        document, group, pad, mirror = self.example()
        self.assertIsNone(group.child('X'))
        self.assertIsNone(group.child('Y'))
        self.assertEqual((12, 6), (mirror['X'], mirror['Y']))
        pad['X'], pad['Y'] = 21, -9
        self.assertEqual((21, -9), (mirror['X'], mirror['Y']))
        self.assertEqual((7, -3), (group.in_units('mm')['X'], group.in_units('mm')['Y']))
        with self.assertRaises(TypeError):
            group['X'] = 3
        document.validate()

    def test_membership_retarget_and_clear_update_dependents(self):
        document, group, pad, mirror = self.example()
        second = group.parent.append(new_group())
        pad['Group'] = second
        self.assertEqual((0, 0), (mirror['X'], mirror['Y']))
        self.assertEqual((12, 6), (second['X'], second['Y']))
        pad['Group'] = group
        self.assertEqual((12, 6), (mirror['X'], mirror['Y']))
        pad['Group'] = None
        self.assertEqual((0, 0), (mirror['X'], mirror['Y']))
        document.validate()

    def test_nested_text_and_point_edits_update_geometry_consumers(self):
        document, group, pad, mirror = self.example()
        pad['Group'] = None
        drawing = document.root.add('Shapes').append(new_drawing(kind=7))
        drawing['TextHorz'], drawing['TextVert'] = -1, -1
        anchor = drawing.one('Points_New').append(Element('pt', 0, 0).bind_schema(POINT))
        line = drawing.one('TextLine').append(Element('pt', 'A').bind_schema(TEXT_LINE))
        drawing['Group'] = group
        before = mirror['X'], mirror['Y']
        line['Text'] = 'A longer line'
        self.assertNotEqual(before[0], mirror['X'])
        anchor['Y'] = 12
        self.assertAlmostEqual(before[1]+12, mirror['Y'])
        height = mirror['Y']
        drawing.one('TextLine').append(Element('pt', 'Second line').bind_schema(TEXT_LINE))
        self.assertGreater(mirror['Y'], height)
        self.assertEqual((group['X'], group['Y']), (mirror['X'], mirror['Y']))
        document.clone().validate()
        document.validate()

    def test_failed_member_edit_preserves_the_member_and_all_calculated_consumers(self):
        document, group, pad, mirror = self.example()
        document.references.bind(mirror, pad, role='hold', guards=(Guard(mirror.one('X'), (12,)),))
        with self.assertRaises(ReferenceError):
            pad['X'] = 21
        self.assertEqual((12, 12, 12), (pad['X'], group['X'], mirror['X']))
        document.validate()
