"""Older normalized drawings become physical geometry once, at their gate."""
from types import SimpleNamespace
from decimal import Decimal
import math
import unittest

from lib.common.library_codec import CachedDefinitionInput
from lib.common.model import Element
from lib.pcb.formats.dip.components import DrawingUpgrade
from lib.pcb.formats.dip.decode import DecodedBoard
from lib.pcb.formats.dip.binary import Header
from lib.pcb.formats.dip.geometry import (expand_pattern_drawings, modernize_pattern_origins,
                                       _legacy_defaults, _legacy_placement_defaults)
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.tests.test_core_assembly import fixture


def pattern(parent, kind, *, orientation=0):
    node = parent.add('Pattern')
    node.add('Width', 30)
    node.add('Height', 15)
    shape = node.add('Shapes').add('Shape')
    shape.add('Type', kind)
    points = shape.add('Points_New')
    points.add('pt', .2, .3)
    points.add('pt', .4, .5)
    return node, DrawingUpgrade(shape, (.1, .2, .9, .8, .5, .1), orientation, False)


class GeometryUpgradeTests(unittest.TestCase):
    def test_earlier_placement_initializes_current_font_settings_without_replacing_values(self):
        for saved in (None, 7):
            component = Element('Component')
            component.add('Pattern')
            if saved is not None:
                component.add('MarkingFontSize', saved)
            _legacy_placement_defaults(component)
            self.assertEqual(component['MarkingFontSize'], 5 if saved is None else saved)
            self.assertFalse(component['CustomMarkingFont'])
            self.assertFalse(component['MarkingFontAll'])

    def test_earlier_placed_and_cached_physical_defaults_keep_existing_data_and_role_metadata(self):
        for placed in (True, False):
            with self.subTest(placed=placed):
                node = Element('Pattern')
                node.add('Width', 12)
                node.add('Height', 8)
                node.add('PadCorner', 17)
                pad = node.add('Pads').add('Pad')
                pad.add('PadWidth_New', 4)
                pad.add('PadMask_Percent', 35)
                _legacy_defaults(node, placed=placed)
                self.assertEqual((node['Width'], node['Height'], node['PadCorner']), (12, 8, 17))
                self.assertEqual(node['Name_Description'], '')
                self.assertTrue(node['RecoveryCode_Generator'])
                self.assertEqual((pad['PadWidth_New'], pad['PadMask_Percent']), (4, 35))
                self.assertEqual(pad['PadShape_X'], 0)
                self.assertEqual(node.get('Pattern_Manufacturer'), None if placed else '')

    def test_old_origin_display_settings_modernize_without_changing_placement(self):
        component = Element('Component')
        node = component.add('Pattern')
        for name, value in dict(OriginX=5, OriginY=-7, OriginCommon=0,
                                OriginCross=False, OriginCircle=False, OriginCourtyard=2).items():
            node.add(name, value)
        decoded = SimpleNamespace(header=SimpleNamespace(version=46),
            upgrades=SimpleNamespace(components=(SimpleNamespace(component=component),)))
        modernize_pattern_origins(decoded)
        self.assertEqual((node['OriginX'], node['OriginY']), (5, -7))
        self.assertEqual((node['OriginCross'], node['OriginCircle'],
                          node['OriginCommon'], node['OriginCourtyard']), (True, True, 1, 0))

    def test_current_origin_mode_upgrade_has_a_precise_value_and_version_gate(self):
        for value, expected in ((0, 0), (1, 1), (2, 1), (3, 3)):
            with self.subTest(value=value):
                component = Element('Component')
                node = component.add('Pattern')
                node.add('OriginCommon', value)
                node.add('OriginCross', False)
                decoded = SimpleNamespace(header=SimpleNamespace(version=47),
                    upgrades=SimpleNamespace(components=(SimpleNamespace(component=component),)))
                modernize_pattern_origins(decoded)
                self.assertEqual(node['OriginCommon'], expected)
                self.assertFalse(node['OriginCross'])

    def test_placed_and_cached_patterns_use_the_same_physical_geometry(self):
        component, definition = Element('Component'), Element('Definition')
        component.add('BottomSide', False)
        placed, text = pattern(component, 7, orientation=1)
        cached, polygon = pattern(definition, 8)
        decoded = SimpleNamespace(header=SimpleNamespace(version=46),
            upgrades=SimpleNamespace(
                components=(SimpleNamespace(component=component, drawings=(text,)),),
                cached_definitions=(CachedDefinitionInput(definition, (polygon,)),)))
        expand_pattern_drawings(decoded)
        self.assertEqual([p.values for p in placed.select('Shapes/Shape/Points_New/pt')], [(3., 12.)])
        self.assertEqual(text.shape['TextAngle'], Decimal(str(math.pi/2)))
        self.assertEqual(text.shape['TextHorz'], -1)
        self.assertEqual([p.values for p in cached.select('Shapes/Shape/Points_New/pt')], [(6., 4.5), (12., 7.5)])
        self.assertEqual(polygon.shape['TextAngle'], 0)
        self.assertEqual(polygon.shape['TextHorz'], 0)

    def test_legacy_text_corner_depends_on_board_side_and_not_flip_or_cached_definition(self):
        for bottom in (False, True):
            for flipped in (False, True):
                for quarter in range(4):
                    with self.subTest(bottom=bottom, flipped=flipped, quarter=quarter):
                        component, definition = Element('Component'), Element('Definition')
                        component.add('BottomSide', bottom)
                        component.add('Flipped', flipped)
                        placed, text = pattern(component, 7, orientation=quarter)
                        cached, original = pattern(definition, 7, orientation=quarter)
                        decoded = SimpleNamespace(header=SimpleNamespace(version=46),
                            upgrades=SimpleNamespace(components=(SimpleNamespace(
                                component=component, drawings=(text,)),),
                                cached_definitions=(CachedDefinitionInput(definition, (original,)),)))
                        expand_pattern_drawings(decoded)
                        x = (27 if quarter < 2 else 3) if bottom else (3 if quarter < 2 else 27)
                        y = 3 if quarter in (0, 3) else 12
                        self.assertEqual(placed.one('Shapes/Shape/Points_New/pt').values, (x, y))
                        self.assertEqual(cached.one('Shapes/Shape/Points_New/pt').values,
                                         (3 if quarter < 2 else 27, y))

    def test_newer_authoritative_geometry_is_not_scaled_again(self):
        component = Element('Component')
        node, drawing = pattern(component, 8)
        drawing.shape.add('TextAngle', .37)
        before = [p.values for p in node.select('Shapes/Shape/Points_New/pt')]
        decoded = SimpleNamespace(header=SimpleNamespace(version=47),
            upgrades=SimpleNamespace(
                components=(SimpleNamespace(component=component, drawings=(drawing,)),),
                cached_definitions=()))
        expand_pattern_drawings(decoded)
        self.assertEqual([p.values for p in node.select('Shapes/Shape/Points_New/pt')], before)
        self.assertEqual(drawing.shape['TextAngle'], Decimal('.37'))

    def test_import_assembly_modernizes_cached_symbol_text_and_ellipses(self):
        decoded = fixture()
        decoded.board.add('PanelDX', 0)
        decoded.board.add('PanelDY', 0)
        slot = decoded.board.add('CacheLib').add('Slots').add('Slot', 0, 'catalog.lib')
        definition = slot.add('Definition', 0)
        part = definition.add('Part', 'Definition', 'U')
        shapes = part.add('Shapes')
        for index, kind in enumerate((10, 6)):
            shape = shapes.add('Shape', index)
            shape.add('Type', kind)
            shape.add('Orientation', 1)
            shape.add('Name', 'Text')
            shape.add('TextLine').add('pt', 'Text')
            geometry = shape.add('Points')
            geometry.add('pt', 1, 2)
            geometry.add('pt', 5, 4)
        cached_pattern, drawing = pattern(definition, 8)
        cached_pattern.add('Model3D')
        cached_shapes = cached_pattern.one('Shapes')
        cached_shapes.insert(Element('Shape'), 0).add('Type', 0)
        cached_shapes.add('Shape').add('Type', 0)
        upgrades = SimpleNamespace(components=(), drawings=(),
            initial=SimpleNamespace(legacy_markings=(2, 6, 0, 6)),
            cached_definitions=(CachedDefinitionInput(definition, (drawing,)),))
        decoded = DecodedBoard(decoded.root, Header('DTBOARD', 46, 0), upgrades)
        document = assemble_core(decoded).document
        model = cached_pattern.one('Model3D')
        self.assertEqual(model['AutoColor'], 0x4B4B4B)
        self.assertIs(model['KeepPins'], False)
        model['AutoColor'] = 0x123456
        text, ellipse = shapes.children()
        self.assertEqual(text.one('Points_New/pt').values, (1, 4))
        self.assertEqual(text['TextAngle'], Decimal(str(math.pi/2)))
        self.assertIsNone(text['Group'])
        self.assertEqual(text['GroupId'], -1)
        self.assertIsNone(text.child('Orientation'))
        self.assertIsNone(text.child('Points'))
        self.assertEqual(ellipse['Type'], 8)
        self.assertEqual(len(ellipse.one('Points_New').children()), 31)
        self.assertEqual(ellipse.one('Points_New/pt[1]').values, (5, 3))
        self.assertEqual(ellipse.one('Points_New/pt[31]').values, (5, 3))
        self.assertEqual(cached_pattern.one('Shapes/Shape/Points_New/pt[1]').values, (6., 4.5))
        self.assertIs(text._owner(), document)


if __name__ == '__main__':
    unittest.main()
