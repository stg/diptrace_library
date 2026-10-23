"""Attachment modernization preserves physical facts and usable identities."""
import unittest
from decimal import Decimal

from lib.design import Element, Index, Segment, ReferenceError
from lib.design.route_normalization import upgrade_short_junctions
from lib.design.schematic_refs import bind_schematic_references
from lib.design.tests.test_legacy_routes import junction


def positions(line):
    return [p.values[:2] for p in line.select('Points/pt')]


def dependent(*, hint=0, bend=False, reordered=False):
    document, host, branch = junction(parallel=3,perpendicular=17,pinned=True)
    branch.one('Points/pt[2]').set_argument(2,0 if bend else 1)
    part = document.one('/Schematic/Components/Part')
    pin = part.one('Pins').add('Pin',1,-91,112)
    pin.add('Orientation',2)
    pin.add('Length',3)
    pin.add('NetNumber',0)
    child = host.parent.add('Line')
    for name,value in dict(Number=2,ConnectMode1=1,ConnectMode2=0,Connect1=1,
                           Connect2=0,ConnectL1=1,ConnectL2=1,ConnectB1=0,ConnectB2=-1).items():
        child.add(name,value)
    points = child.add('Points')
    points.add('pt',1.5,8.5,0)
    points.add('pt',12,12,hint)
    bind_schematic_references(document)
    if reordered:
        child.move_to(host.parent,0)
        document.rebuild()
    return document,host,branch,child


class JunctionBoundaryTests(unittest.TestCase):
    def assertAttached(self,document):
        for reference in document.references:
            if reference.role not in ('wire-segment-1','wire-segment-2'):
                continue
            points = reference.source.select('Points/pt')
            joined = points[0 if reference.role.endswith('1') else -1].values[:2]
            a,b = reference.target.start.values[:2],reference.target.end.values[:2]
            self.assertEqual((joined[0]-a[0])*(b[1]-a[1]),(joined[1]-a[1])*(b[0]-a[0]))
            self.assertTrue(all(min(x,y)<=z<=max(x,y) for x,y,z in zip(a,b,joined)))

    def test_stored_direction_selects_the_bend_before_axis_cleanup(self):
        for hint,count in ((0,3),(1,2)):
            document,_,branch = junction(parallel=3,perpendicular=17,pinned=True)
            branch.one('Points/pt[2]').set_argument(2,hint)
            upgrade_short_junctions(document)
            self.assertEqual(len(positions(branch)),count)
            self.assertEqual(positions(branch)[-1],(3,17))
            self.assertAttached(document)
            self.assertEqual(upgrade_short_junctions(document),())

    def test_corner_overlap_retargets_an_existing_segment_and_keeps_selection_identity(self):
        document,host,branch = junction(parallel=-10,perpendicular=-30,pinned=True)
        host.one('Points').insert(Element('pt',-10,-12,-1),0)
        host.one('Points/pt[2]').set_argument(2,1)
        document.rebuild()
        host_points = host.select('Points/pt')
        original = [p.values for p in host_points]
        selected = branch.one('Points/pt[1]')
        field = document.root.add('Pick',0)
        link = document.references.bind(field,selected,Index(field),role='selected-wire-point')
        upgrade_short_junctions(document)
        self.assertEqual(positions(branch),[(-10,-12),(-10,-30)])
        self.assertIs(link.target,selected)
        self.assertIs(branch.one('Points/pt[1]'),selected)
        target = document.references.outgoing(branch,role='wire-segment-1')[0].target
        self.assertEqual(target,Segment(host_points[0],host_points[1]))
        self.assertEqual([p.values for p in host.select('Points/pt')],original)
        self.assertAttached(document)

    def test_nearby_pins_and_free_leads_are_not_disconnected_or_collapsed(self):
        document,_,branch = junction(parallel=3,perpendicular=.1,pinned=True)
        branch.one('Points/pt[2]').set_argument(2,1)
        upgrade_short_junctions(document)
        self.assertEqual(positions(branch),[(3,0),(3,Decimal('.1'))])
        self.assertAttached(document)
        document,_,branch = junction(parallel=3,perpendicular=17)
        branch.one('Points/pt[2]').set_argument(2,0)
        upgrade_short_junctions(document)
        self.assertEqual(positions(branch),[(0,0),(0,17),(3,17)])
        self.assertAttached(document)

    def test_dependencies_follow_settled_geometry_independent_of_array_order(self):
        for hint in (0,1):
            for bend in (False,True):
                expected = None
                for reordered in (False,True):
                    document,host,branch,child = dependent(hint=hint,bend=bend,reordered=reordered)
                    original = {line:line.select('Points/pt') for line in (branch,child)}
                    pins = [p.values for p in document.select('/Schematic/Components/Part/Pins/Pin')]
                    self.assertEqual(upgrade_short_junctions(document),(branch,child))
                    actual = [positions(line) for line in (host,branch,child)]
                    if expected is None:
                        expected = actual
                    self.assertEqual(actual,expected)
                    self.assertEqual(positions(branch)[-1],(3,17))
                    self.assertEqual(positions(child)[-1],(12,12))
                    self.assertEqual([p.values for p in document.select('/Schematic/Components/Part/Pins/Pin')],pins)
                    for line,points in original.items():
                        self.assertIs(line.one('Points/pt[1]'),points[0])
                        self.assertIs(line.select('Points/pt')[-1],points[-1])
                    self.assertAttached(document)
                    self.assertEqual(upgrade_short_junctions(document),())

    def test_dependent_unresolved_scope_blocks_before_any_geometry_changes(self):
        document,host,branch,child = dependent(bend=True)
        original = [positions(line) for line in (host,branch,child)]
        field = document.root.add('Unknown',99)
        document.references.note(field,'unknown geometry',Index(field),collections=(child.one('Points'),))
        with self.assertRaises(ReferenceError):
            upgrade_short_junctions(document)
        self.assertEqual([positions(line) for line in (host,branch,child)],original)


if __name__=='__main__':
    unittest.main()
