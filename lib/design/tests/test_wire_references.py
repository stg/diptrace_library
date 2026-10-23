"""Wire joins use local identities while retaining redundant source values."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.design import Document, Segment, ReferenceError
from lib.design.schematic_refs import bind_schematic_references, connectivity_mismatches


def wire_document(*, saved_net=29, route_key=5, foreign_route_key=5, segment=1, source_format=None,
                  clamp_segments=False):
    document = Document()
    if source_format is not None:
        document.metadata['source_format'] = source_format
    document.root.add('Source', 'DipTrace-Schematic', 46)
    schematic = document.root.add('Schematic')
    schematic.add('Components')
    nets = schematic.add('Nets')
    first, second = [nets.add('Net', name) for name in ('signal', 'other')]
    for net, number, offset in ((first, 12, 0), (second, 29, 100)):
        net.add('Number', number)
        route = net.add('Lines').add('Line')
        route.add('Number', 5 if net is first else foreign_route_key)
        route.add('NetNumber', number)
        points = route.add('Points')
        points.add('pt', offset, 0, 0)
        points.add('pt', offset+10, 0, 0)
        points.add('pt', offset+10, 10, 1)
    host = first.one('Lines/Line')
    join = first.one('Lines').add('Line')
    for name, value in (('Number', 8), ('NetNumber', 12), ('Page', -1),
                        ('ConnectMode1', 1), ('Connect1', route_key),
                        ('ConnectL1', segment), ('ConnectB1', saved_net)):
        join.add(name, value)
    points = join.add('Points')
    points.add('pt', 300, 50, 0)
    points.add('pt', 400, 50, 0)
    for node in document.root.walk(include_self=True):
        node._dirty = node._reordered = False
    bind_schematic_references(document, clamp_segments=clamp_segments)
    return document, first, second, host, join


class WireReferenceTests(unittest.TestCase):
    def test_unresolved_local_join_does_not_freeze_another_net(self):
        document, first, second, host, join = wire_document(route_key=99)
        self.assertEqual(len(document.references.issues), 1)
        second.one('Lines').add('Line').add('Number', 100)
        bind_schematic_references(document)
        document.rebuild()
        self.assertEqual(join.scalar('Connect1'), 99)
        clone = document.clone()
        clone.one('/Schematic/Nets/Net[1]/Lines/Line[1]/Points').add('pt', 20, 10, 1)
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            clone.rebuild()
        document.rebuild()
        first.one('Lines').add('Line').add('Number', 99)
        bind_schematic_references(document)
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            document.rebuild()

    def test_join_is_local_independent_of_geometry_and_redundant_net_value(self):
        for saved_net in (-1, 12, 29, 1000):
            with self.subTest(saved_net=saved_net):
                document, first, _, host, join = wire_document(saved_net=saved_net)
                self.assertEqual(document.references.issues, [])
                self.assertEqual(connectivity_mismatches(document), [])
                reference = document.references.outgoing(join, role='wire-segment-1')[0]
                self.assertIsInstance(reference.target, Segment)
                self.assertIs(reference.target.start.parent.parent, host)
                self.assertEqual(join.scalar('ConnectB1'), saved_net)
                self.assertFalse(document.root.changed)
                document.rebuild(force=False)
                self.assertEqual(join.scalar('ConnectB1'), saved_net)
                document.rebuild()
                self.assertEqual(join.scalar('ConnectB1'), 0)

    def test_join_follows_net_and_route_order_through_a_detached_copy(self):
        document, first, second, host, join = wire_document()
        second.move_to(first.parent, 0)
        host.move_to(host.parent, 1)
        copied = document.clone()
        copied.rebuild(force=False)
        projected = copied.one('/Schematic/Nets/Net[2]/Lines/Line[1]')
        self.assertEqual((projected.scalar('Connect1'), projected.scalar('ConnectL1'),
                          projected.scalar('ConnectB1')), (1, 1, 1))
        self.assertEqual(connectivity_mismatches(copied), [])
        self.assertEqual((join.scalar('Connect1'), join.scalar('ConnectB1')), (5, 29))

    def test_missing_local_route_stays_unresolved_despite_a_foreign_match(self):
        document, first, second, _, join = wire_document(route_key=99, foreign_route_key=99)
        self.assertEqual(document.references.outgoing(join, role='wire-segment-1'), [])
        self.assertEqual(len(document.references.issues), 1)
        self.assertEqual((join.scalar('Connect1'), join.scalar('ConnectB1')), (99, 29))

    def test_binary_segment_bounds_resolve_without_replacing_the_source_value(self):
        for saved, expected in ((-1,1),(0,1),(1,1),(2,2),(999,2)):
            document, _, _, host, join = wire_document(segment=saved, source_format='dch', clamp_segments=True)
            reference = document.references.outgoing(join, role='wire-segment-1')[0]
            self.assertIs(reference.target.end, host.select('Points/pt')[expected])
            self.assertEqual(join.scalar('ConnectL1'), saved)
            document.rebuild(force=False)
            self.assertEqual(join.scalar('ConnectL1'), saved)
            document.rebuild()
            self.assertEqual(join.scalar('ConnectL1'), expected)
        for source in (None,'dch','asc','dchxml'):
            document, *_ = wire_document(segment=0, source_format=source)
            self.assertEqual(len(document.references.issues), 1)

    def test_wire_cannot_join_its_own_segment(self):
        document, _, _, _, join = wire_document(route_key=8, source_format='dch')
        self.assertEqual(document.references.outgoing(join, role='wire-segment-1'), [])
        self.assertEqual(len(document.references.issues), 1)


if __name__ == '__main__':
    unittest.main()
