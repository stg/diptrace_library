"""Named, unnamed and numeric pad shapes have one current numeric meaning."""
import unittest

from lib.common.footprint_objects import new_pattern
from lib.common.model import Element
from lib.common.units import XmlUnits
from lib.common.xml_pad_output import project_pad_style
from lib.common.xml_pads import read_pad_style
from lib.common.xml_pad_shapes import shape_code, shape_label
from lib.common.xml_records import XmlRecord


class XmlPadShapeTests(unittest.TestCase):
    def test_main_shape_labels_use_sparse_codes_and_numeric_aliases(self):
        for label, code in (('Ellipse', 0), ('Obround', 1), ('Rectangle', 2), ('Polygon', 3),
                            ('D-shape', 4), ('Fiducial', 20), ('fiducial', 20), ('', 5), ('10', 10)):
            with self.subTest(label=label):
                self.assertEqual(shape_code(label), code)
                self.assertEqual(shape_code(shape_label(code)), code)
        self.assertEqual(shape_label(20), 'Fiducial')
        self.assertEqual(shape_label(5), '')
        self.assertEqual(shape_label(10), '10')

    def test_terminal_unnamed_and_numeric_domains_remain_distinct(self):
        self.assertEqual(shape_code('', terminal=True), -1)
        self.assertEqual(shape_label(-1, terminal=True), '')
        for code in (0, 1, 2, 3, 4, 5, 10, 20):
            with self.subTest(code=code):
                self.assertEqual(shape_code(shape_label(code, terminal=True), terminal=True), code)
        self.assertEqual(shape_label(5, terminal=True), '5')
        self.assertEqual(shape_label(20, terminal=True), '20')

    def test_style_import_and_output_keep_main_and_terminal_unnamed_values(self):
        style = Element('PadStyle')
        style.add('Name', 'Example')
        style.add('MainStack').add('Shape', '')
        style.add('Terminals').add('Terminal').add('Shape', '')
        pattern = new_pattern('Example')
        read_pad_style(XmlRecord(style), pattern, units=XmlUnits('mm'))
        self.assertEqual(pattern['PadShape'], 5)
        self.assertEqual(pattern.one('PadTerminal')['Type'], -1)
        output = project_pad_style(pattern, name='Example', units=XmlUnits('mm'))
        self.assertEqual(output.one('MainStack')['Shape'], '')
        self.assertEqual(output.one('Terminals/Terminal')['Shape'], '')

    def test_invalid_shape_values_do_not_silently_choose_geometry(self):
        for value in ('Hexagon', '1.5', True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                shape_code(value)
        with self.assertRaises(ValueError):
            shape_label(1.5)
