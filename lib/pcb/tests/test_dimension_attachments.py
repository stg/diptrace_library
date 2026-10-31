"""Footprint dimensions follow object, terminal and vertex identities."""
import unittest
from unittest.mock import patch

from lib.common.footprint_objects import new_pad, new_pattern, new_pattern_drawing
from lib.common.references import ReferenceError
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.model.dimensions import LOCAL_ROLES
from lib.pcb.tests.test_core_assembly import fixture


def design(*, unresolved=False):
    decoded = fixture()
    definition = decoded.board.add('CacheLib').add('Slots').add('Slot', 0, '').add('Definition', 0)
    definition.add('Part', 'Device', 'U').add('PartType', 1)
    pattern = definition.append(new_pattern('Package'))
    for position, marker in enumerate((-1, 1, -1, 3, -1)):
        pad = pattern.one('Pads').append(new_pad(str(position), index=position))
        pad['Number_New'] = marker
        for index, kind in enumerate((1, 3)):
            terminal = pad.add('PadTerminal', index)
            terminal.add('Type', kind)
            points = terminal.add('ShapePoints')
            if kind == 3:
                for x, y in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    points.add('pt', x, y)
    for position, kind in enumerate((0, 1, 0, 9, 0)):
        shape = pattern.one('Shapes').append(new_pattern_drawing(position, kind=kind))
        for x, y in ((0, 0), (2, 0), (2, 1), (0, 1)):
            shape.one('Points_New').add('pt', x, y)
    for position, enabled in enumerate((False, True, False, True, False)):
        pattern.one('Holes').add('Hole', enabled, False, position, 0, 2, 1, -1)

    endpoints = [(0, 0, 3, 0), (1, 0, 3, 2), (2, 0, 3, 0),
                 (3, 3, 1, 2), (3, 1, 0, 0), (-1, 0, 0, 0)]
    if unresolved:
        endpoints.append((1, 0, 3, 99))
    for index, (mode, owner, member, point) in enumerate(endpoints):
        dimension = pattern.one('Dimensions').add('Dimension', index)
        for name, value in dict(Enabled=True, Connected1=mode, Object1=owner,
                SubObject1=member, Point1=point, Connected2=-1, Object2=0,
                SubObject2=0, Point2=0, X1=7, Y1=8, Group=-1).items():
            dimension.add(name, value)
    pattern.one('Dimensions').add('Dimension', 99).add('Enabled', False)
    return assemble_core(decoded)


def link(document, dimension):
    return document.references.outgoing(dimension, role=LOCAL_ROLES[0])[0]


class DimensionAttachmentTests(unittest.TestCase):
    def test_import_compacts_geometry_and_binds_saved_positions(self):
        result = design()
        local, = result.cached_footprints
        self.assertEqual(set(local.shapes), {1, 3})
        self.assertEqual(set(local.holes), {1, 3})
        self.assertEqual(len(local.pattern.one('Shapes').children()), 2)
        self.assertEqual(len(local.pattern.one('Holes').children()), 2)
        dimensions = local.pattern.select('Dimensions/Dimension')
        self.assertEqual(len(dimensions), 6)
        targets = [link(result.document, dimension).target for dimension in dimensions[:5]]
        self.assertEqual(targets, [local.pads[3], local.shapes[3].one('Points_New/pt[3]'), local.holes[3],
            local.pads[3].one('PadTerminal[2]/ShapePoints/pt[2]'), local.pads[1].one('PadTerminal[1]')])
        self.assertEqual([dimension['SubObject1'] for dimension in dimensions[:3]], [2, 2, 2])
        self.assertEqual(dimensions[3]['Object1'], 2)
        self.assertFalse(result.document.references.outgoing(dimensions[-1]))

    def test_reorder_updates_selectors_without_scanning_the_document(self):
        result = design()
        document, local = result.document, result.cached_footprints[0]
        pad_dim, shape_dim, hole_dim, polygon_dim, terminal_dim, _ = local.pattern.select('Dimensions/Dimension')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole-document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole-graph scan')):
            local.pads[3].move_to(local.pads[3].parent, 0)
            self.assertEqual((pad_dim['SubObject1'], polygon_dim['Object1'], terminal_dim['Object1']), (1, 1, 2))
            point = link(document, shape_dim).target
            point.move_to(point.parent, 0)
            self.assertEqual(shape_dim['Point1'], 0)
            local.shapes[3].move_to(local.shapes[3].parent, 0)
            self.assertEqual(shape_dim['SubObject1'], 1)
            local.holes[3].move_to(local.holes[3].parent, 0)
            self.assertEqual(hole_dim['SubObject1'], 1)
            vertex = link(document, polygon_dim).target
            vertex.move_to(vertex.parent, 0)
            self.assertEqual(polygon_dim['Point1'], 1)
            terminal = vertex.parent.parent
            terminal.move_to(terminal.parent, 0)
            self.assertEqual(polygon_dim['SubObject1'], 0)

    def test_retarget_and_foreign_or_incompatible_changes_are_atomic(self):
        result = design()
        document, local = result.document, result.cached_footprints[0]
        pad_dim, shape_dim, hole_dim, *_ = local.pattern.select('Dimensions/Dimension')
        document.references.retarget(link(document, pad_dim), local.pads[1])
        self.assertEqual(pad_dim['SubObject1'], 1)
        copy = document.copy(local.pattern.parent, parent=local.pattern.parent.parent)
        with self.assertRaises(ReferenceError):
            document.references.retarget(link(document, pad_dim), copy.one('Pattern/Pads/Pad[1]'))
        for operation in (lambda: local.shapes[3].set('Type', 1),
                          lambda: local.holes[3].set('Enabled', False),
                          lambda: shape_dim.set('Connected1', 0),
                          lambda: document.remove(link(document, shape_dim).target)):
            with self.assertRaises(ReferenceError):
                operation()
        self.assertEqual(local.shapes[3]['Type'], 9)
        self.assertTrue(local.holes[3]['Enabled'])
        self.assertEqual(shape_dim['Connected1'], 1)
        document.remove(hole_dim)
        document.remove(local.holes[3])

    def test_copy_and_clone_remap_owned_dimension_targets(self):
        result = design()
        definition = result.cached_footprints[0].pattern.parent
        document = result.document
        copied = document.copy(definition, parent=definition.parent)
        copied_dimension = copied.one('Pattern/Dimensions/Dimension[4]')
        target = copied.one('Pattern/Pads/Pad[2]/PadTerminal[2]/ShapePoints/pt[2]')
        self.assertIs(link(document, copied_dimension).target, target)
        cloned = document.clone()
        dimension = cloned.one('/Board/CacheLib/Slots/Slot/Definition[1]/Pattern/Dimensions/Dimension[4]')
        self.assertIs(link(cloned, dimension).target,
            cloned.one('/Board/CacheLib/Slots/Slot/Definition[1]/Pattern/Pads/Pad[2]/PadTerminal[2]/ShapePoints/pt[2]'))

    def test_invalid_local_attachment_becomes_free_with_an_informational_report(self):
        @import_diagnostics('dip')
        def load():
            return design(unresolved=True).document
        report = ConversionReport()
        document = load(report=report)
        local = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        dimension = local.one('Dimensions/Dimension[7]')
        self.assertEqual((dimension['Connected1'], dimension['Object1'], dimension['SubObject1'], dimension['Point1']),
                         (-1, 0, 0, 0))
        self.assertEqual((dimension['X1'], dimension['Y1']), (7, 8))
        self.assertFalse(document.references.outgoing(dimension))
        self.assertFalse(document.references.issues)
        self.assertEqual(len([notice for notice in report.infos if notice.rule == 'dimension-attachment-normalization']), 1)
        local.one('Shapes/Shape[2]/Points_New').add('pt', 4, 5)


if __name__ == '__main__':
    unittest.main()
