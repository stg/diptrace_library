"""ASC geometry enters the same PCB relationships without source-only copies."""
from decimal import Decimal
import unittest

from lib.common.asc import loads, dumps
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_asc_rules import fixture as rule_fixture


GEOMETRY = '''(Enabled "Y")
(Points (pt 0 0 "N") (pt 20 0 "Y") (pt 20 20 "N"))
(Groups (Group 5 2 3 "Y" "N" "Y"))
(NonSignals (NonSignal "Assembly! detail" 123 0 1))
(Shapes (Shape
  (Enabled "Y") (Selected "N") (Orientation 3) (AllLayers "N")
  (Type 3) (Layer 1) (ShapeType 0) (OldNumber 23) (Group 5) (NetNumber 73)
  (BitmapIndex -1) (RasterIndex -1) (TextAngle 9.2)
  (Locked "N") (VectorFont "Y") (Name "Compatibility text")
  (TextLines (TextLine "First line") (TextLine "Second line"))
  (Points (pt 1 2) (pt 3 4))
  (Picture_Raster "N") (Picture_Width 0) (Picture_Height 0)
  (Picture_Proportions "N") (Picture_Transparent 0)
  (Vector_Width 0) (Vector_Height 0) (Vector_Polygons)))
(CopperPours (CopperPour
  (Enabled "Y") (Selected "N") (Poured "Y") (Layer 2) (NetNumber 73)
  (OldNumber 29) (Group 5) (MinimumArea 3) (LineWidth 0.9)
  (Points (pt 0 0) (pt 10 0) (pt 10 10))
  (Lines (pt 1 2 3 4 4))
  (SpokeLine (pt 5 6 7 8 0.7 4))
  (Polygons (Poly 4 (pt 1 2) (pt 3 4) (pt 5 6)))
  (Regions_Counted "Y")))'''


def fixture():
    source = loads(rule_fixture())
    board = source.one('/Board')
    for node in tuple(loads(GEOMETRY).root.children()):
        node.move_to(board)
    return source


def design(source=None):
    return assemble_graphics(prepare_core(dumps(source or fixture(), preserve=False)))


class AscGraphicTests(unittest.TestCase):
    def test_missing_drawing_angle_uses_the_numeric_compatibility_value(self):
        for orientation in (-1, 0, 1, 3):
            with self.subTest(orientation=orientation):
                source = fixture()
                shape = source.one('/Board/Shapes/Shape')
                shape.one('TextAngle').detach()
                shape.one('Orientation').set_values(orientation)
                before = dumps(source, preserve=False)
                current = design(source).drawings[23]
                # In current ASC the fallback is numeric, not quarter turns.
                # Existing point geometry is already in its current frame.
                self.assertEqual(current['TextAngle'], orientation)
                self.assertIsNone(current.child('Orientation'))
                self.assertEqual([point.values for point in current.select('Points/pt')], [(1, 2), (3, 4)])
                self.assertEqual(dumps(source, preserve=False), before)

    def test_missing_both_drawing_angle_fields_uses_zero(self):
        source = fixture()
        shape = source.one('/Board/Shapes/Shape')
        for name in ('TextAngle', 'Orientation'):
            shape.one(name).detach()
        self.assertEqual(design(source).drawings[23]['TextAngle'], 0)

    def test_used_compatibility_orientation_requires_one_integer(self):
        source = fixture()
        shape = source.one('/Board/Shapes/Shape')
        shape.one('TextAngle').detach()
        shape.one('Orientation').set_values(Decimal('1.5'))
        with self.assertRaisesRegex(PcbError, 'integer Orientation'):
            design(source)

    def test_named_pad_thermal_layer_becomes_a_live_reference(self):
        source = fixture()
        thermal = source.one('/Board/Components/Component/Pads/Pad[2]').add('CustomSpokes').add('CustomSpoke')
        for name, value in dict(Layer=1, Type=2, Spoke=4, Width=Decimal('1.5')).items():
            thermal.add(name, value)
        result = design(source)
        current = result.document.one('/Board/Components/Component/Pattern/Pads/Pad[1]/CustomSpokes/CustomSpoke')
        self.assertIs(current['Layer'], result.rules.layers[1])
        self.assertEqual((current['Type'], current['Spoke'], current['Width']), (2, 4, Decimal('1.5')))
        current['Width'] = 2
        current['Layer'] = result.rules.layers[0]
        self.assertEqual((current['Lay'], current['Width']), (0, 2))

    def test_drawings_pours_outline_and_groups_keep_current_identity_links(self):
        result = design()
        board = result.document.one('/Board')
        shape, pour, group = result.drawings[23], result.pours[29], result.groups[5]
        layers = result.rules.layers
        net = result.rules.routing.core.nets[73]
        self.assertIs(shape['LayerTarget'], layers[1])
        self.assertEqual((shape['Layer'], shape['LayId'], shape['Type']), (3, 1, 0))
        self.assertIs(shape['Net'], net)
        self.assertIs(shape['Group'], group)
        self.assertIs(pour['Layer'], layers[2])
        self.assertIs(pour['Net'], net)
        self.assertIs(pour['Group'], group)
        self.assertEqual((group['X'], group['Y']), (2, 3))
        self.assertFalse(group['Selected'])
        self.assertEqual([p['Arc'] for p in board.select('Points/pt')], [False, True, False])
        self.assertEqual(shape['TextAngle'], Decimal('9.2'))
        self.assertIsNone(shape.child('Orientation'))
        self.assertEqual([row['Text'] for row in shape.select('TextLine/pt')], ['First line', 'Second line'])
        self.assertIsNone(shape.child('Name'))
        self.assertIsNone(shape.child('OldNumber'))
        self.assertIsNone(shape.child('PictureVector'))
        layers[2].move_to(layers[2].parent, 1)
        self.assertEqual((shape['LayId'], pour['Lay']), (2, 1))
        self.assertTrue(result.document.complete)

    def test_available_fill_is_typed_data_with_one_squared_area(self):
        result = design()
        pour = result.pours[29]
        self.assertTrue(pour['Poured'])
        self.assertEqual(pour['MinimumArea'], 9)
        self.assertEqual(pour['RatlineMode'], 0)
        line = pour.one('Fill/Lines/Line')
        spoke = pour.one('Fill/SpokeLine/Line')
        polygon = pour.one('Fill/Polygons/Poly')
        self.assertEqual((line['X1'], line['Y1'], line['X2'], line['Y2'], line['RegionId']), (1, 2, 3, 4, 4))
        self.assertEqual(spoke['Width'], Decimal('0.7'))
        self.assertEqual(polygon['RegionId'], 4)
        self.assertIs(line['Region'], polygon['Region'])
        point = polygon.one('Points/pt[1]')
        point['X'] = 9
        self.assertEqual(point['X'], 9)
        self.assertIsNone(pour.child('Regions_Counted'))
        self.assertIsNone(pour.child('OldNumber'))

    def test_missing_fill_is_absent_without_changing_the_filled_choice(self):
        source = fixture()
        pour = source.one('/Board/CopperPours/CopperPour')
        for name in ('Lines', 'SpokeLine', 'Polygons'):
            pour.one(name).detach()
        current = design(source).pours[29]
        self.assertTrue(current['Poured'])
        self.assertIsNone(current.child('Fill'))

    def test_non_signal_layer_identity_is_separate_from_copper(self):
        source = fixture()
        shape = source.one('/Board/Shapes/Shape')
        shape.one('Type').set_values(15)
        shape.one('Layer').set_values(0)
        result = design(source)
        drawing, target = result.drawings[23], result.non_signals[0]
        self.assertIs(drawing['LayerTarget'], target)
        self.assertEqual(target['Name'], 'Assembly! detail')
        target['Name'] = 'Changed custom layer'
        self.assertEqual(drawing['LayerTarget']['Name'], 'Changed custom layer')

    def test_vector_geometry_has_current_owned_points(self):
        source = fixture()
        shape = source.one('/Board/Shapes/Shape')
        shape.one('Vector_Width').set_values(12)
        shape.one('Vector_Height').set_values(8)
        points = shape.one('Vector_Polygons').add('Vector_Polygon').add('Points')
        points.add('pt', 1, 2)
        points.add('pt', 3, 4)
        result = design(source)
        vector = result.drawings[23].one('PictureVector')
        self.assertEqual((vector['Width'], vector['Height']), (12, 8))
        point = vector.one('Polygons/Polygon/Points/Item[1]')
        self.assertEqual((point['X'], point['Y']), (1, 2))
        point['Y'] = 7
        self.assertEqual(point['Y'], 7)

    def test_bad_or_unimplemented_drawing_mappings_fail_explicitly(self):
        for field, value, message in (
            ('Selected', 'unknown', 'boolean'),
        ):
            source = fixture()
            source.one('/Board/Shapes/Shape/'+field).set_values(value)
            with self.subTest(field=field), self.assertRaisesRegex(PcbError, message):
                prepare_core(dumps(source, preserve=False))
        source = fixture()
        source.one('/Board/Shapes/Shape').add('LayId', 2)
        with self.assertRaisesRegex(PcbError, 'ambiguous'):
            prepare_core(dumps(source, preserve=False))

    def test_dimension_flags_are_prepared_in_both_scopes(self):
        source = fixture()
        board = source.one('/Board')
        for owner in (board, board.one('Components/Component')):
            collection = owner.child('Dimensions') or owner.add('Dimensions')
            dimension = collection.add('Dimension')
            dimension.add('Enabled', 'Y')
            dimension.add('Locked', 'N')
        data = prepare_core(dumps(source, preserve=False))
        for path in ('Dimensions/Dimension', 'Components/Component/Pattern/Dimensions/Dimension'):
            dimension = data.board.one(path)
            self.assertEqual(dimension.values, (0,))
            self.assertEqual(dimension.one('Enabled').values, (True,))
            self.assertEqual(dimension.one('Locked').values, (False,))
        self.assertEqual(data.board.one('Dimensions/Dimension/Selected').values, (False,))

    def test_explicit_connection_display_choice_is_retained(self):
        source = fixture()
        source.one('/Board/CopperPours/CopperPour').add('RatlineMode', 2)
        self.assertEqual(design(source).pours[29]['RatlineMode'], 2)


if __name__ == '__main__':
    unittest.main()
