"""Older binary thermal choices become current data without moving geometry."""
import math
from types import SimpleNamespace
import unittest

import lib
from lib.pcb.formats.dip.decode import DecodedBoard
from lib.pcb.formats.dip.thermal_upgrade import modernize_thermals, _contains
from lib.pcb.model.objects import new_document, new_component, new_pad, new_net, new_layer


def design(*, angle=math.pi/4):
    document = new_document()
    board = document.one('/Board')
    net = board.one('Nets').append(new_net('N'))
    net['Enabled'] = True
    component = board.one('Components').append(new_component('Device', 'U1'))
    component['Enabled'], component['Angle'] = True, angle
    pad = component.one('Pattern/Pads').append(new_pad('1'))
    pad['SurfacePad'], pad['Net'] = False, net
    return document, component, pad, net


def pour(document, net, *, layer=None, spoke=4, width=.6, enabled=True, points=None):
    board = document.one('/Board')
    collection = board.child('CopperPours') or board.add('CopperPours')
    result = collection.add('CopperPour')
    result['Enabled'], result['Net'] = enabled, net
    result['Layer'] = layer if layer is not None else board.one('Layers/Layer[1]')
    result['Spoke'], result['SpokeWidth'] = spoke, width
    polygon = result.add('Points')
    for point in points if points is not None else ((-10, -10), (10, -10), (10, 10), (-10, 10)):
        polygon.add('pt', *point)
    return result


def thermal(pad, *, spoke, layer=None, width=.3, kind=0):
    collection = pad.child('CustomSpokes') or pad.add('CustomSpokes')
    row = collection.add('CustomSpoke')
    row['Type'], row['Spoke'], row['Width'] = kind, spoke, width
    if layer is not None:
        row['Layer'] = layer
    return row


def upgrade(document, component, pad, *, version=46):
    return modernize_thermals(document, version=version, placements=((component, (pad,)),))


class ThermalUpgradeTests(unittest.TestCase):
    def test_all_supported_older_binary_versions_use_the_same_current_rule(self):
        for version in range(31, 47):
            with self.subTest(version=version):
                document, component, pad, net = design()
                pour(document, net)
                self.assertEqual(upgrade(document, component, pad, version=version), (pad,))
                row = pad.one('CustomSpokes/CustomSpoke')
                self.assertEqual((row['Type'], row['Spoke'], row['Width'], row['Lay']), (0, 3, .6, -1))
                self.assertIsNone(row['Layer'])
                document.validate()

    def test_newer_binary_versions_do_not_reapply_the_older_orientation_rule(self):
        for version in range(47, 63):
            document, component, pad, net = design()
            pour(document, net)
            existing = thermal(pad, spoke=1)
            self.assertEqual(upgrade(document, component, pad, version=version), ())
            self.assertEqual(existing['Spoke'], 1)
            self.assertEqual(len(pad.select('CustomSpokes/CustomSpoke')), 1)

    def test_both_spoke_maps_preserve_independent_type_width_and_global_selection(self):
        for angle, expected in ((math.pi/4, (0, 3, 3, 4, 3, 19)),
                                (math.pi/2, (0, 2, 1, 3, 4, 19))):
            for before, after in zip((0, 1, 2, 3, 4, 19), expected):
                with self.subTest(angle=angle, spoke=before):
                    document, component, pad, net = design(angle=angle)
                    pour(document, net)
                    row = thermal(pad, spoke=before, kind=2, width=.375)
                    upgrade(document, component, pad)
                    self.assertEqual((row['Spoke'], row['Type'], row['Width'], row['Layer']),
                                     (after, 2, .375, None))
                    self.assertEqual(len(pad.select('CustomSpokes/CustomSpoke')), 1)

    def test_combined_pad_and_component_angle_is_periodic(self):
        for component_angle, pad_angle in ((0, math.pi/4), (math.pi/8, math.pi/8),
                                            (-math.pi/4, 0), (math.tau+math.pi/4, 0)):
            document, component, pad, net = design(angle=component_angle)
            pad['PadAngle'] = pad_angle
            pour(document, net)
            upgrade(document, component, pad)
            self.assertEqual(pad.one('CustomSpokes/CustomSpoke')['Spoke'], 3)

    def test_compatibility_intervals_have_strict_bounds(self):
        for divisor, phases in ((math.pi/2, (.45, .45001, .54999, .55)),
                                (math.pi, (.49, .49001, .50999, .51))):
            for phase, expected in zip(phases, (False, True, True, False)):
                document, component, pad, net = design(angle=divisor*phase)
                pour(document, net, spoke=1)
                upgrade(document, component, pad)
                self.assertEqual(bool(pad.select('CustomSpokes/CustomSpoke')), expected,
                                 (divisor, phase))

    def test_other_angles_and_unassigned_pads_do_not_acquire_overrides(self):
        for angle in (0, math.pi/6, math.pi, math.tau):
            document, component, pad, net = design(angle=angle)
            pour(document, net)
            self.assertEqual(upgrade(document, component, pad), ())
        document, component, pad, net = design()
        pour(document, net)
        pad['Net'] = None
        self.assertEqual(upgrade(document, component, pad), ())

    def test_inactive_or_different_net_pours_do_not_supply_defaults(self):
        for same_net in (True, False):
            document, component, pad, net = design()
            other = document.one('/Board/Nets').append(new_net('Other'))
            other['Enabled'] = True
            pour(document, net if same_net else other, enabled=not same_net)
            self.assertEqual(upgrade(document, component, pad), ())

    def test_existing_choices_only_modernize_for_a_net_with_an_active_pour(self):
        document, component, pad, net = design()
        row = thermal(pad, spoke=1)
        self.assertEqual(upgrade(document, component, pad), ())
        self.assertEqual(row['Spoke'], 1)
        pour(document, net, points=((20, 20), (30, 20), (30, 30), (20, 30)))
        self.assertEqual(upgrade(document, component, pad), (pad,))
        self.assertEqual(row['Spoke'], 3)

    def test_first_applicable_pour_retains_precedence_even_for_an_unchanged_mode(self):
        for first_mode, expected in ((0, None), (4, .4)):
            document, component, pad, net = design()
            pour(document, net, spoke=first_mode, width=.4)
            pour(document, net, spoke=3, width=.8)
            upgrade(document, component, pad)
            rows = pad.select('CustomSpokes/CustomSpoke')
            self.assertEqual(len(rows), int(expected is not None))
            if rows:
                self.assertEqual(rows[0]['Width'], expected)

    def test_containment_uses_the_current_pad_world_position(self):
        document, component, pad, net = design()
        pour(document, net)
        component['X'] = 20
        self.assertEqual(upgrade(document, component, pad), ())
        pad['X'], pad['Y'] = -10*math.sqrt(2), -10*math.sqrt(2)
        self.assertEqual(upgrade(document, component, pad), (pad,))

    def test_surface_side_and_individual_pad_side_choose_the_outside_layer(self):
        for bottom in (False, True):
            for sided in (False, True):
                document, component, pad, net = design()
                component['BottomSide'], pad['Sided'], pad['SurfacePad'] = bottom, sided, True
                pour(document, net)
                self.assertEqual(bool(upgrade(document, component, pad)), bottom == sided)

    def test_through_pad_hidden_and_blind_layers_are_both_excluded(self):
        for group in ('HideLayer', 'BlindLayer'):
            document, component, pad, net = design()
            layer = document.one('/Board/Layers/Layer[1]')
            pour(document, net)
            (pad.child(group) or pad.add(group)).add('Item')['Layer'] = layer
            self.assertEqual(upgrade(document, component, pad), ())

    def test_existing_layer_coverage_retains_order_and_appends_one_missing_layer(self):
        document, component, pad, net = design()
        top, bottom = document.select('/Board/Layers/Layer')
        pour(document, net, layer=top)
        pour(document, net, layer=bottom, width=.9)
        existing = thermal(pad, spoke=1, layer=top)
        upgrade(document, component, pad)
        rows = pad.select('CustomSpokes/CustomSpoke')
        self.assertIs(rows[0], existing)
        self.assertEqual([(r['Spoke'], r['Width'], r['Layer']) for r in rows],
                         [(3, .3, top), (3, .9, bottom)])
        bottom.move_to(bottom.parent, 0)
        self.assertEqual(rows[1]['Lay'], 0)
        document.validate()

    def test_one_new_default_is_global_even_when_other_layers_have_pours(self):
        document, component, pad, net = design()
        for layer in document.select('/Board/Layers/Layer'):
            pour(document, net, layer=layer)
        upgrade(document, component, pad)
        self.assertEqual(len(pad.select('CustomSpokes/CustomSpoke')), 1)
        self.assertIsNone(pad.one('CustomSpokes/CustomSpoke')['Layer'])

    def test_new_layer_record_does_not_fill_every_uncovered_pour(self):
        document, component, pad, net = design()
        layers = document.one('/Board/Layers')
        layers.append(new_layer('Inner'))
        top, bottom, inner = layers.children('Layer')
        thermal(pad, spoke=1, layer=top)
        pour(document, net, layer=bottom)
        pour(document, net, layer=inner)
        upgrade(document, component, pad)
        self.assertEqual([r['Layer'] for r in pad.select('CustomSpokes/CustomSpoke')], [top, bottom])

    def test_import_boundary_retains_only_the_importers_positional_pad_selection(self):
        document, component, pad, net = design()
        other = component.one('Pattern/Pads').append(new_pad('2'))
        other['Net'] = net
        pour(document, net)
        assembled = SimpleNamespace(document=document, rules=SimpleNamespace(routing=SimpleNamespace(
            core=SimpleNamespace(pad_positions={component: {1: pad}}))))
        DecodedBoard.finish_import(SimpleNamespace(header=SimpleNamespace(version=46)), assembled)
        self.assertEqual(len(pad.select('CustomSpokes/CustomSpoke')), 1)
        self.assertFalse(other.select('CustomSpokes/CustomSpoke'))

    def test_boundary_and_connectivity_are_unchanged(self):
        document, component, pad, net = design()
        polygon = pour(document, net)
        before = [p.values for p in polygon.select('Points/pt')]
        members = tuple(document.references.incoming(pad))
        upgrade(document, component, pad)
        self.assertEqual([p.values for p in polygon.select('Points/pt')], before)
        self.assertIs(pad['Net'], net)
        self.assertEqual(tuple(document.references.incoming(pad)), members)

    def test_current_binary_and_text_imports_keep_supplied_spokes(self):
        for format in ('dip', 'asc', 'dipxml'):
            document, component, pad, net = design(angle=math.pi/2)
            pour(document, net)
            thermal(pad, spoke=1)
            rebuilt = lib.parse(lib.serialize(document, format=format), format=format)
            self.assertEqual(rebuilt.one('/Board/Components/Component/Pattern/Pads/Pad/CustomSpokes/CustomSpoke')['Spoke'], 1)


class StableContainmentTests(unittest.TestCase):
    def test_even_odd_polygon_in_both_orders_and_half_open_boundary(self):
        box = ((0, 0), (2, 0), (2, 2), (0, 2))
        for polygon in (box, box[::-1]):
            for point, expected in (((1, 1), True), ((3, 1), False), ((0, 1), False),
                                    ((2, 1), True), ((1, 0), False), ((1, 2), True)):
                self.assertEqual(_contains(point, polygon), expected, point)
        self.assertEqual(box, ((0, 0), (2, 0), (2, 2), (0, 2)))

    def test_empty_degenerate_and_concave_boundaries(self):
        for polygon in ((), ((0, 0),), ((0, 0), (2, 2))):
            self.assertFalse(_contains((1, 1), polygon))
        corner = ((0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3))
        self.assertTrue(_contains((.5, 2), corner))
        self.assertFalse(_contains((2, 2), corner))


if __name__ == '__main__':
    unittest.main()
