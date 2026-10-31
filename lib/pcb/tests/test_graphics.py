"""Graphic selectors become identities and remain coherent during data edits."""
from types import SimpleNamespace
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.drawing_records import POINT
from lib.common.references import Property, ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model.objects import new_trace
from lib.pcb.tests.test_core_assembly import fixture


def design():
    decoded = fixture()
    board = decoded.board
    layers = board.add('Layers')
    for index, name in enumerate(('Top', 'Bottom')):
        layer = layers.add('Layer', name)
        layer.add('Number', index)
        layer.add('Type', 0)
    groups = board.add('Groups')
    for key, enabled in ((8, True), (35, True), (99, False)):
        group = groups.add('Group', key, key*2, key*3)
        group.add('Enabled', enabled)
        group.add('Selected', False)
    board.add('NonSignals').add('NonSignal', 'Notes', 1234, 47, 2)
    component = board.one('Components/Component')
    component.add('Group', 8)
    pad = component.one('Pattern/Pads').children()[1]
    pad.one('Group').set_values(35)
    holes = component.one('Pattern/Holes')
    holes.add('Hole', False, False, 0, 0, 0, 0, -1)
    hole = holes.add('Hole', True, False, 1, 2, 3, 1, 35)
    holes.add('Hole', False, False, 0, 0, 0, 0, -1)
    shapes = component.one('Pattern/Shapes')
    shapes.add('Shape', 0).add('Type', 0)
    pattern_shape = shapes.add('Shape', 1)
    pattern_shape.add('Type', 1)
    pattern_shape.add('Group', 35)
    shapes.add('Shape', 2).add('Type', 0)
    shapes = board.add('Shapes')
    drawings = []
    for index, (family, target, enabled) in enumerate(((3, 1, True), (15, 0, True), (1, 123, False))):
        shape = shapes.add('Shape', index)
        for name, value in (('Enabled', enabled), ('Layer', family), ('LayId', target),
                            ('NetNumber', 73), ('Group', 35), ('Type', 8)):
            shape.add(name, value)
        shape.add('Points_New').add('pt', 1, 2)
        shape.add('TextLine').add('pt', 'Note')
        drawings.append(SimpleNamespace(drawing=shape, previous_number=100+index))
    pour = board.add('CopperPours').add('CopperPour', 0)
    for name, value in (('Enabled', True), ('Lay', 0), ('NetId', 73), ('Group', 8), ('Poured', True)):
        pour.add(name, value)
    pour.add('Points').add('pt', 3, 4)
    fill = pour.add('Fill')
    line = fill.add('Lines').add('Line')
    for name, value in (('X1', 1), ('Y1', 2), ('X2', 3), ('Y2', 4), ('Region', 7)):
        line.add(name, value)
    fill.add('Polygons').add('Poly').add('Points').add('pt', 1, 2)
    fill.add('SpokeLine')
    decoded.upgrades = SimpleNamespace(nets=(), separate_traces=(), drawings=tuple(drawings),
                                      pours=(SimpleNamespace(pour=pour, previous_number=500, regions_counted=True),))
    return decoded, hole, pattern_shape


class GraphicTests(unittest.TestCase):
    def test_import_consumes_saved_selectors_without_treating_keys_as_positions(self):
        decoded, hole, pattern_shape = design()
        result = assemble_graphics(decoded)
        board = result.document.one('/Board')
        top, bottom = result.rules.layers.values()
        first, second = result.groups.values()
        copper, custom = result.drawings.values()
        pour, = result.pours.values()
        component = board.one('Components/Component')
        self.assertEqual(len(board.select('Groups/Group')), 2)
        self.assertEqual(len(board.select('Shapes/Shape')), 2)
        self.assertEqual((first['Id'], second['Id']), (0, 1))
        self.assertEqual((first['X'], first['Y']), (16, 24))
        self.assertIs(component['Group'], first)
        self.assertEqual(component.one('Pattern/Pads/Pad[1]')['Group'], 35)
        self.assertEqual(hole['Group'], 35)
        self.assertEqual(pattern_shape['Group'], 35)
        self.assertIs(copper['LayerTarget'], bottom)
        self.assertIs(custom['LayerTarget'], result.non_signals[0])
        self.assertEqual((result.non_signals[0]['Id'], result.non_signals[0]['Side']), (0, 2))
        self.assertIs(pour['Layer'], top)
        self.assertIs(pour['Net'], result.rules.routing.core.nets[73])
        self.assertIs(copper['Net'], pour['Net'])
        self.assertIs(pour['Group'], first)
        self.assertIsNone(copper.child('LayId'))
        self.assertIsNone(copper.child('NetNumber'))
        self.assertIsNone(component.child('Group'))
        self.assertEqual(hole.values, (True, False, 0, Decimal('.25'), 3, 1, 35))
        self.assertIs(pour.one('Points/pt').schema, POINT)
        pour.one('Fill/Polygons/Poly/Points/pt')['X'] = 9
        self.assertEqual(pour.one('Fill/Polygons/Poly/Points/pt')['X'], 9)
        self.assertTrue(result.document.complete)

    def test_reordering_updates_layer_net_and_group_projections_without_global_scans(self):
        decoded, _, _ = design()
        result = assemble_graphics(decoded)
        document = result.document
        shape = result.drawings[100]
        probe = document.root.add('Probe', 0, 0, 0)
        document.references.bind(probe, shape, Property(probe, 'LayId'),
            Property(probe, 'NetId', argument=1), Property(probe, 'GroupId', argument=2), role='probe')
        first, second = result.groups.values()
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            result.rules.layers[1].move_to(result.rules.layers[1].parent, 0)
            second.move_to(second.parent, 0)
            self.assertEqual(probe.values, (0, 0, 0))
            shape['Group'] = first
            self.assertEqual(probe.values, (0, 0, 1))
            shape['Net'] = None
            self.assertEqual(probe.values, (0, -1, 1))

    def test_layer_family_and_target_constraints_fail_atomically(self):
        decoded, _, _ = design()
        result = assemble_graphics(decoded)
        shape = result.drawings[100]
        bottom = shape['LayerTarget']
        with self.assertRaises(ReferenceError):
            shape['Layer'] = 15
        self.assertEqual(shape['Layer'], 3)
        self.assertIs(shape['LayerTarget'], bottom)
        with self.assertRaises(ReferenceError):
            shape['LayerTarget'] = result.non_signals[0]
        shape['LayerTarget'] = None
        shape['Layer'] = 15
        shape['LayerTarget'] = result.non_signals[0]
        self.assertEqual(shape['LayId'], 0)

    def test_referenced_targets_cannot_be_removed_or_disabled(self):
        decoded, _, _ = design()
        result = assemble_graphics(decoded)
        document = result.document
        for target in (result.groups[35], result.non_signals[0], result.rules.routing.core.nets[73]):
            with self.subTest(kind=target.kind), self.assertRaises(ReferenceError):
                document.remove(target)
            self.assertIsNotNone(target.parent)
        with self.assertRaises(ReferenceError):
            result.groups[35]['Enabled'] = False
        with self.assertRaises(ReferenceError):
            result.rules.routing.core.nets[73]['Enabled'] = False

    def test_cloning_and_copying_remap_owned_and_external_graphic_links(self):
        decoded, _, _ = design()
        result = assemble_graphics(decoded)
        duplicate = result.document.clone()
        board = duplicate.one('/Board')
        self.assertIs(board.one('Shapes/Shape[1]')['Group'], board.one('Groups/Group[2]'))
        self.assertIs(board.one('CopperPours/CopperPour')['Net'], board.one('Nets/Net'))
        self.assertEqual(board.one('Components/Component/Pattern/Holes/Hole')['Group'], 35)
        shape = result.drawings[100]
        copy = result.document.copy(shape, parent=shape.parent)
        self.assertIs(copy['Group'], shape['Group'])
        self.assertIs(copy['LayerTarget'], shape['LayerTarget'])
        self.assertEqual(copy['Id'], 2)

    def test_deleted_footprint_slots_do_not_give_stale_groups_a_target(self):
        decoded, hole, shape = design()
        component = decoded.board.one('Components/Component')
        drawings = component.one('Pattern/Shapes')
        removed = drawings.add('Shape', 1)
        removed.add('Type', 0)
        removed.add('Group', 12345)
        removed.move_to(drawings, 0)
        holes = component.one('Pattern/Holes')
        empty = holes.add('Hole', False, False, 0, 0, 0, 0, 12345)
        empty.move_to(holes, 0)
        result = assemble_graphics(decoded)
        self.assertIsNone(removed.parent)
        self.assertIsNone(empty.parent)
        self.assertEqual(result.placed_shapes, {(component, 2): shape})
        self.assertEqual(result.placed_holes, {(component, 2): hole})
        self.assertEqual(shape['Index'], 0)

    def test_footprint_group_codes_do_not_acquire_board_group_identity_by_coincidence(self):
        decoded, hole, shape = design()
        hole.set_argument(6, 8)
        shape.one('Group').set_values(8)
        component = decoded.board.one('Components/Component')
        component.one('Pattern/Pads').children()[1].one('Group').set_values(8)
        result = assemble_graphics(decoded)
        group = result.groups[8]
        self.assertIs(component['Group'], group)
        self.assertEqual((hole['Group'], shape['Group']), (8, 8))
        self.assertEqual({link.source for link in result.document.references.incoming(group, role='pcb-group')},
                         {component, result.pours[500]})
        group.move_to(group.parent, 1)
        self.assertEqual((hole['Group'], shape['Group']), (8, 8))

    def test_footprint_members_cannot_join_board_groups_through_reserved_graph_roles(self):
        decoded, hole, _ = design()
        result = assemble_graphics(decoded)
        pad = result.document.one('/Board/Components/Component/Pattern/Pads/Pad[1]')
        for member in (pad, hole):
            with self.assertRaises(ReferenceError):
                result.document.references.bind(member, result.groups[8], role='pcb-group')
            self.assertFalse(result.document.references.outgoing(member, role='pcb-group'))

    def test_trace_group_membership_uses_the_same_board_identities(self):
        decoded, _, _ = design()
        result = assemble_graphics(decoded)
        net = result.rules.routing.core.nets[73]
        trace = net.add('Traces').append(new_trace())
        trace['Group'] = result.groups[35]
        self.assertEqual(trace['GroupId'], 1)
        result.groups[35].move_to(result.groups[35].parent, 0)
        self.assertEqual(trace['GroupId'], 0)


if __name__ == '__main__':
    unittest.main()
