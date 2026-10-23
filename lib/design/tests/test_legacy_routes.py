"""Legacy handle upgrades retain editable geometry and stable identities."""
import unittest

from lib.design import Document, Index, Segment, ReferenceError, coalesce_routes
from lib.design.route_normalization import (upgrade_redundant_route_handles, upgrade_short_route_axes,
                                     upgrade_short_junctions)
from lib.design.schematic_refs import bind_schematic_references


def route(values):
    document = Document()
    net = document.root.add('Schematic').add('Nets').add('Net')
    line = net.add('Lines').add('Line')
    points = line.add('Points')
    for value in values:
        points.add('pt', *value)
    return document, net, line


def junction(*, axis=0, side=0, parallel=17, perpendicular=3, pinned=False, orientation=0):
    def position(along, across):
        return (along, across) if axis == 0 else (across, along)
    document, net, host = route([(*position(-10, 0), -1), (*position(10, 0), axis)])
    document.root.add('Source', 'DipTrace-Schematic', 46)
    host.add('Number', 0)
    host.add('ConnectMode1', 4)
    host.add('ConnectMode2', 4)
    branch = host.parent.add('Line')
    branch.add('Number', 1)
    positions = [position(0, 0), position(parallel, perpendicular)]
    if side:
        positions.reverse()
    for end in (1, 2):
        branch.add('ConnectMode'+str(end), 1 if end == side+1 else 0 if pinned else 4)
        branch.add('Connect'+str(end), 0 if end == side+1 or pinned else -1)
        branch.add('ConnectL'+str(end), 1 if end == side+1 else 0 if pinned else -1)
        branch.add('ConnectB'+str(end), 0 if end == side+1 else -1)
    points = branch.add('Points')
    direction = int(abs(positions[1][1]-positions[0][1]) > abs(positions[1][0]-positions[0][0]))
    for index, point in enumerate(positions):
        points.add('pt', *point, 2 if index == 0 else direction)
    if pinned:
        part = document.one('/Schematic').add('Components').add('Part')
        part.add('Number', 0)
        part.add('X', 100)
        part.add('Y', -100)
        dx, dy = ((-1, 0), (0, -1), (1, 0), (0, 1))[orientation]
        x, y = positions[1-side]
        pin = part.add('Pins').add('Pin', 0, x-100-3*dx, y+100-3*dy)
        pin.add('Orientation', orientation)
        pin.add('Length', 3)
        pin.add('NetNumber', 0)
    bind_schematic_references(document)
    return document, host, branch


class LegacyRouteTests(unittest.TestCase):
    def test_segment_local_junctions_keep_host_anchors_and_all_geometry_identities(self):
        for axis in (0, 1):
            for side in (0, 1):
                for pinned in (False, True):
                    for modes in ((0, 0), (0, 4), (4, 0), (4, 4)):
                        document, host, branch = junction(axis=axis, side=side, parallel=3,
                                                         perpendicular=9, pinned=pinned)
                        points = host.select('Points/pt')
                        # Keep the declared middle segment and add other bends
                        # to the same host. Segment identity updates its index.
                        for index, current, amount in ((0, points[0], -12), (3, points[-1], 12)):
                            xy = list(current.values[:2])
                            xy[1-axis] += amount
                            host.one('Points').insert(type(current)('pt', *xy, -1 if index == 0 else 1-axis), index)
                        points[0].set_argument(2, 1-axis)
                        part = document.one('/Schematic').child('Components')
                        part = part.children('Part')[0] if part is not None else None
                        if part is None:
                            part = document.one('/Schematic').add('Components').add('Part')
                            part.add('Number', 0)
                            part.add('X', 100)
                            part.add('Y', -100)
                            part.add('Pins')
                        for end, mode in enumerate(modes, 1):
                            host.set_field('ConnectMode'+str(end), mode)
                            if mode == 0:
                                target = host.select('Points/pt')[0 if end == 1 else -1]
                                pins = part.one('Pins')
                                index = len(pins.children('Pin'))
                                pin = pins.add('Pin', index, target.values[0]-100, target.values[1]+100)
                                pin.add('Orientation', 0)
                                pin.add('Length', 0)
                                pin.add('NetNumber', 0)
                                host.set_field('Connect'+str(end), 0)
                                host.set_field('ConnectL'+str(end), index)
                        bind_schematic_references(document)
                        document.rebuild()
                        original = [p.values for p in host.select('Points/pt')]
                        pin_values = [p.values for p in part.select('Pins/Pin')]
                        link = document.references.outgoing(branch, role='wire-segment-'+str(side+1))[0]
                        target = link.target
                        self.assertEqual(upgrade_short_junctions(document), (branch,))
                        self.assertEqual([p.values for p in host.select('Points/pt')], original)
                        self.assertEqual([p.values for p in part.select('Pins/Pin')], pin_values)
                        self.assertEqual(link.target, target)
                        self.assertEqual(branch.scalar('ConnectL'+str(side+1)), 2)
                        self.assertEqual(upgrade_short_junctions(document), ())

    def test_redundant_hint_moves_to_the_retained_segment_anchor(self):
        values = [(0, 0, 0), (0, 0, 1), (0, 0, 0), (10, 0, 0)]
        document, net, line = route(values)
        original = line.select('Points/pt')
        field = net.add('Attachment', 3)
        reference = document.references.bind(field, Segment(original[2], original[3]), Index(field))
        removed = upgrade_redundant_route_handles(document)
        self.assertEqual([(item.point, item.position) for item in removed], [(original[1], 1)])
        self.assertEqual(line.select('Points/pt'), [original[0], original[2], original[3]])
        self.assertEqual([point.values for point in line.select('Points/pt')], [values[0], values[1], values[3]])
        self.assertIsNone(line.child('StoredData'))
        self.assertEqual(reference.target, Segment(original[2], original[3]))
        self.assertEqual(field.values, (2,))
        self.assertEqual(upgrade_redundant_route_handles(document), ())

    def test_handle_hint_transfer_keeps_direct_anchors_and_preflights_changes(self):
        for unresolved in (False, True):
            values = [(0, 0, 0), (0, 0, 1), (0, 0, 0), (10, 0, 0)]
            document, net, line = route(values)
            points = line.select('Points/pt')
            field = net.add('Attachment', 3 if unresolved else 2)
            document.references.bind(field, Segment(points[2], points[3]) if unresolved else points[2], Index(field))
            if unresolved:
                unknown = net.add('Unknown', 99)
                document.references.note(unknown, 'unknown point', Index(unknown), collections=(line.one('Points'),))
                with self.assertRaises(ReferenceError):
                    upgrade_redundant_route_handles(document)
            else:
                self.assertEqual(upgrade_redundant_route_handles(document), ())
            self.assertEqual([point.values for point in line.select('Points/pt')], values)
            self.assertIsNone(line.child('StoredData'))

    def test_pin_junctions_keep_the_pin_endpoint_and_identity(self):
        for axis in (0, 1):
            for side in (0, 1):
                for orientation in range(4):
                    for parallel, perpendicular in ((9, 3), (3, 9), (17, 3), (-17, -3)):
                        document, host, branch = junction(axis=axis, side=side, parallel=parallel,
                            perpendicular=perpendicular, pinned=True, orientation=orientation)
                        original = branch.select('Points/pt')
                        values = [point.values for point in original]
                        pin_link = document.references.outgoing(branch, role='wire-pin-'+str(2-side))[0]
                        pin = pin_link.target
                        pin_values = pin.values
                        host_values = [point.values for point in host.select('Points/pt')]
                        self.assertEqual(upgrade_short_junctions(document), (branch,))
                        current = branch.select('Points/pt')
                        self.assertIs(current[0], original[0])
                        self.assertIs(current[-1], original[-1])
                        self.assertEqual(current[-1 if side == 0 else 0].values[:2], values[1-side][:2])
                        self.assertEqual(len(current), 3 if abs(parallel) > abs(perpendicular) else 2)
                        self.assertTrue(all(a.values[0] == b.values[0] or a.values[1] == b.values[1]
                                            for a, b in zip(current, current[1:])))
                        self.assertEqual(pin.values, pin_values)
                        self.assertIs(pin_link.target, pin)
                        self.assertEqual([point.values for point in host.select('Points/pt')], host_values)
                        self.assertIsNone(branch.child('StoredData'))
                        self.assertEqual(upgrade_short_junctions(document), ())

    def test_pin_junctions_with_incoherent_endpoints_remain_literal(self):
        document, _, branch = junction(parallel=3, perpendicular=9, pinned=True)
        pin = document.one('/Schematic/Components/Part/Pins/Pin')
        pin.set_argument(1, pin.values[1]+1)
        original = [point.values for point in branch.select('Points/pt')]
        self.assertEqual(upgrade_short_junctions(document), ())
        self.assertEqual([point.values for point in branch.select('Points/pt')], original)
        self.assertIsNone(branch.child('StoredData'))

    def test_outside_projection_uses_a_dogleg_at_every_distance_without_moving_the_pin(self):
        for axis in (0,1):
            for side in (0,1):
                for parallel in (10.1, 10.5, 11, 11.0001, 17, -17):
                    document, host, branch = junction(axis=axis, side=side, parallel=parallel,
                                                      perpendicular=30, pinned=True)
                    original = branch.select('Points/pt')
                    fixed = original[1-side].values[:2]
                    self.assertEqual(upgrade_short_junctions(document), (branch,))
                    points = branch.select('Points/pt')
                    self.assertEqual(len(points), 4)
                    self.assertEqual(points[-1 if side==0 else 0].values[:2], fixed)
                    self.assertIs(points[0], original[0])
                    self.assertIs(points[-1], original[-1])
                    self.assertTrue(all(a.values[0]==b.values[0] or a.values[1]==b.values[1]
                                        for a,b in zip(points, points[1:])))
                    self.assertEqual(upgrade_short_junctions(document), ())

    def test_free_junctions_keep_endpoint_identities_without_geometry_history(self):
        for axis in (0, 1):
            for side in (0, 1):
                for parallel, perpendicular in ((17, 3), (3, 17)):
                    document, host, branch = junction(axis=axis, side=side, parallel=parallel, perpendicular=perpendicular)
                    original = branch.select('Points/pt')
                    values = [point.values for point in original]
                    self.assertEqual(upgrade_short_junctions(document), (branch,))
                    current = branch.select('Points/pt')
                    self.assertIs(current[0], original[0])
                    self.assertIs(current[-1], original[-1])
                    self.assertEqual(current[0].values[2], 2)
                    self.assertTrue(all(a.values[0] == b.values[0] or a.values[1] == b.values[1]
                                        for a, b in zip(current, current[1:])))
                    self.assertEqual(len(current), 3 if parallel > perpendicular else 2)
                    self.assertIsNone(branch.child('StoredData'))
                    link = document.references.outgoing(branch, role='wire-segment-'+str(side+1))[0]
                    self.assertEqual(link.target, Segment(*host.select('Points/pt')))
                    self.assertEqual(upgrade_short_junctions(document), ())

    def test_junctions_with_other_attachment_constraints_remain_literal(self):
        for constraint in ('anchored-host', 'referenced-point'):
            document, host, branch = junction(parallel=17, perpendicular=3)
            if constraint == 'anchored-host':
                host.set_field('ConnectMode1', 0)
            elif constraint == 'referenced-point':
                field = document.root.add('Anchor', 0)
                document.references.bind(field, branch.one('Points/pt[1]'), Index(field))
            original = [point.values for point in branch.select('Points/pt')]
            self.assertEqual(upgrade_short_junctions(document), ())
            self.assertEqual([point.values for point in branch.select('Points/pt')], original)
            self.assertIsNone(branch.child('StoredData'))

    def test_unresolved_junction_scope_blocks_before_geometry_changes(self):
        document, _, branch = junction()
        field = document.root.add('UnknownAnchor', 99)
        document.references.note(field, 'unresolved point', Index(field), collections=(branch.one('Points'),))
        original = [point.values for point in branch.select('Points/pt')]
        with self.assertRaises(ReferenceError):
            upgrade_short_junctions(document)
        self.assertEqual([point.values for point in branch.select('Points/pt')], original)
        self.assertIsNone(branch.child('StoredData'))

    def test_unrelated_unresolved_links_allow_independent_route_compaction(self):
        document, _, line = route([(0,0,0),(0,0,0),(0,0,0),(10,0,0)])
        other = document.root.add('OtherTargets')
        source = document.root.add('OtherSource')
        field = source.add('Target', 99)
        document.references.note(source, 'unknown other target', Index(field), collections=(other,))
        removed = coalesce_routes(document)
        self.assertEqual(len(removed), 1)
        self.assertEqual(len(line.select('Points/pt')), 3)
        self.assertEqual(field.values, (99,))
        self.assertEqual(len(document.references.issues), 1)

    def test_related_or_unknown_reference_domains_block_before_any_removal(self):
        for scoped in (True, False):
            document, _, line = route([(0,0,0),(0,0,0),(0,0,0),(10,0,0)])
            original = line.select('Points/pt')
            source = document.root.add('OtherSource')
            field = source.add('Target', 99)
            document.references.note(source, 'unknown target', Index(field),
                collections=(line.one('Points'),) if scoped else None)
            with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
                coalesce_routes(document)
            self.assertEqual(line.select('Points/pt'), original)
            self.assertTrue(all(point.parent is line.one('Points') for point in original))

    def test_short_pin_or_free_route_normalizes_axes_without_history(self):
        document, _, line = route([(0,0,-1),(0,10,0)])
        line.add('ConnectMode1',0)
        line.add('ConnectMode2',4)
        self.assertEqual(upgrade_short_route_axes(document),1)
        self.assertEqual([p.values for p in line.select('Points/pt')],[(0,0,-1),(0,10,1)])
        self.assertIsNone(line.child('StoredData'))
        self.assertEqual(upgrade_short_route_axes(document),0)

    def test_attachment_hints_and_longer_routes_need_their_own_rules(self):
        for values,modes in (([(0,0,-1),(0,10,0)],(1,0)),
                             ([(0,0,-1),(0,10,0),(10,10,1)],(0,4))):
            document, _, line = route(values)
            for side,mode in enumerate(modes,1):
                line.add('ConnectMode'+str(side),mode)
            self.assertEqual(upgrade_short_route_axes(document),0)
            self.assertEqual([p.values for p in line.select('Points/pt')],values)
            self.assertIsNone(line.child('StoredData'))

    def test_handles_simplify_without_removing_regular_vertices(self):
        cases = [
            ([(0,0,0),(0,0,0),(10,0,0),(10,10,1)], 1),
            ([(0,0,-1),(10,0,0),(10,0,0),(10,10,1)], 1),
            ([(0,0,-1),(10,0,0),(10,0,0)], 1),
        ]
        for values, position in cases:
            with self.subTest(values=values):
                document, _, line = route(values)
                original = line.select('Points/pt')
                removed = upgrade_redundant_route_handles(document)
                self.assertEqual(len(removed), 1)
                self.assertIs(removed[0].point, original[position])
                self.assertEqual(removed[0].position, position)
                self.assertIsNone(removed[0].point.parent)
                self.assertIs(line.select('Points/pt')[0], original[0])
                self.assertIs(line.select('Points/pt')[-1], original[-1])
                self.assertEqual(upgrade_redundant_route_handles(document), ())
        document, _, _ = route([(0,0,-1),(5,0,0),(10,0,0)])
        self.assertEqual(upgrade_redundant_route_handles(document), ())

    def test_direction_changes_and_marked_handles_remain(self):
        for values in ([(0,0,0),(0,0,1),(0,10,1)],
                       [(0,0,0),(0,0,2),(10,0,0)]):
            document, _, line = route(values)
            original = line.select('Points/pt')
            self.assertEqual(upgrade_redundant_route_handles(document), ())
            self.assertEqual(line.select('Points/pt'), original)

    def test_referenced_point_and_segment_anchors_remain(self):
        for segment in (False, True):
            document, net, line = route([(0,0,0),(0,0,0),(10,0,0)])
            points = line.select('Points/pt')
            target = Segment(points[1], points[2]) if segment else points[1]
            reference = document.references.bind(net, target, Index(net.add('Anchor', 0)))
            self.assertEqual(upgrade_redundant_route_handles(document), ())
            self.assertIs(reference.target, target)
            self.assertEqual(line.select('Points/pt'), points)


if __name__ == '__main__':
    unittest.main()
