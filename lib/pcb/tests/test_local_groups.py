"""Local group identities remain coherent across edits without board-wide scans."""
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.model import Element
from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.dip.binary import DipError
from lib.pcb.model.local_groups import GROUP
from lib.pcb.tests.test_core_assembly import fixture


def design():
    decoded = fixture()
    slot = decoded.board.add('CacheLib').add('Slots').add('Slot', 0, 'generic.lib')
    for number in range(2):
        definition = slot.add('Definition', number)
        symbol = definition.add('Part', 'Device', 'U')
        symbol.add('PartType', 1)  # No footprint-pad assignment in this fixture.
        groups = symbol.add('Groups')
        groups.add('pt', True, 93, 0, 0)
        groups.add('pt', False, 100, 2, 3)
        groups.add('pt', True, 4, 5, 6)
        pin = symbol.add('Pins').add('Pin', 0, 1, 2)
        pin.add('Group', 2)
        shape = symbol.add('Shapes').add('Shape', 0)
        shape.add('Group', 1)  # A deleted group becomes no group.
        pattern = definition.add('Pattern', 'Package')
        groups = pattern.add('Pattern_Groups')
        groups.add('pt', True, 48, 1, 2)
        groups.add('pt', False, 1, 0, 0)
        groups.add('pt', True, 3, 3, 4)
        shapes = pattern.add('Shapes')
        shapes.add('Shape', 0).add('Type', 0)
        shape = shapes.add('Shape', 1)
        shape.add('Type', 1)
        shape.add('Group', 2)
        shapes.add('Shape', 2).add('Type', 0)
        holes = pattern.add('Holes')
        holes.add('Hole', False, False, 0, 0, 0, 0, -1)
        holes.add('Hole', True, False, 1, 2, 3, 1, 0)
        holes.add('Hole', False, False, 0, 0, 0, 0, -1)
        dimension = pattern.add('Dimensions').add('Dimension', 0)
        dimension.add('Group', 999)  # An unavailable source group is cleared.
    return assemble_core(decoded)


class LocalGroupTests(unittest.TestCase):
    def test_unavailable_group_without_the_verified_compaction_case_is_explicit(self):
        decoded = fixture()
        definition = decoded.board.add('CacheLib').add('Slots').add('Slot', 0, '').add('Definition', 0)
        part = definition.add('Part', 'Device', 'U')
        part.add('Groups').add('pt', True, 94, 0, 0)
        part.add('Pins').add('Pin', 0, 0, 0).add('Group', 999)
        result = assemble_core(decoded)
        pin = result.document.one('/Board/CacheLib/Slots/Slot/Definition/Part/Pins/Pin')
        self.assertEqual(pin['UnresolvedGroupId'], 999)
        self.assertEqual(pin['GroupId'], 999)
        with self.assertRaisesRegex(ReferenceError, 'unresolved target'):
            pin['Group']
        pin['Group'] = None
        self.assertIsNone(pin.child('UnresolvedGroupId'))
        self.assertIsNone(pin['Group'])
        result.document.references.validate()

    def test_import_uses_saved_positions_and_consumes_regenerated_group_codes(self):
        result = design()
        definition = result.document.one('/Board/CacheLib/Slots/Slot/Definition[1]')
        part, pattern = definition.one('Part'), definition.one('Pattern')
        pin = part.one('Pins/Pin')
        groups = part.one('Groups').children()
        self.assertEqual([group['Id'] for group in groups], [0, 1])
        self.assertTrue(all(group.schema is GROUP for group in groups))
        self.assertTrue(all(group.child('Id') is None for group in groups))
        self.assertIs(pin['Group'], groups[1])
        self.assertEqual(pin['GroupId'], 1)
        self.assertIsNone(part.one('Shapes/Shape')['Group'])
        self.assertIs(pattern.one('Shapes/Shape')['Group'], pattern.one('Pattern_Groups/pt[2]'))
        self.assertIs(pattern.one('Holes/Hole')['Group'], pattern.one('Pattern_Groups/pt[1]'))
        self.assertEqual(pattern.one('Holes/Hole').values, (True, False, 1, 2, 3, 1))
        self.assertIsNone(pattern.one('Dimensions/Dimension')['Group'])
        self.assertIsNone(pin.child('Group'))

    def test_reorder_retarget_and_clear_use_identities_without_global_scans(self):
        document = design().document
        part = document.one('/Board/CacheLib/Slots/Slot/Definition[1]/Part')
        pin = part.one('Pins/Pin')
        first, second = part.one('Groups').children()
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole-document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole-graph scan')):
            second.move_to(second.parent, 0)
            self.assertIs(pin['Group'], second)
            self.assertEqual((pin['GroupId'], second['Id']), (0, 0))
            pin['Group'] = first
            self.assertEqual(pin['GroupId'], 1)
            pin['Group'] = None
            self.assertEqual(pin['GroupId'], -1)
            added = part.one('Groups').append(Element('pt', True, 78, 1, 2))
            pin['Group'] = added
            self.assertEqual(pin['GroupId'], 2)
        with self.assertRaises(TypeError):
            pin['GroupId'] = 0
        with self.assertRaises(TypeError):
            second['Id'] = 5

    def test_group_namespace_scope_and_disabled_or_referenced_edits_are_atomic(self):
        document = design().document
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition[1]')
        other = document.one('/Board/CacheLib/Slots/Slot/Definition[2]')
        pin = definition.one('Part/Pins/Pin')
        current = pin['Group']
        for target in (definition.one('Pattern/Pattern_Groups/pt[1]'), other.one('Part/Groups/pt[1]')):
            with self.assertRaises(ReferenceError):
                pin['Group'] = target
        with self.assertRaises(ReferenceError):
            current['Enabled'] = False
        with self.assertRaises(ReferenceError):
            document.remove(current)
        with self.assertRaises(ReferenceError):
            current.move_to(other.one('Part/Groups'))
        self.assertIs(pin['Group'], current)
        self.assertTrue(current['Enabled'])

    def test_copy_and_clone_capture_group_targets_in_the_owned_subtree(self):
        document = design().document
        original = document.one('/Board/CacheLib/Slots/Slot/Definition[1]')
        copied = document.copy(original, parent=original.parent)
        pin = copied.one('Part/Pins/Pin')
        self.assertIs(pin['Group'], copied.one('Part/Groups/pt[2]'))
        self.assertIsNot(pin['Group'], original.one('Part/Groups/pt[2]'))
        clone = document.clone()
        pin = clone.one('/Board/CacheLib/Slots/Slot/Definition[1]/Part/Pins/Pin')
        self.assertIs(pin['Group'], clone.one('/Board/CacheLib/Slots/Slot/Definition[1]/Part/Groups/pt[2]'))

    def test_verified_group_repairs_use_the_common_import_report(self):
        @import_diagnostics('dip')
        def load():
            return design().document
        report = ConversionReport()
        load(report=report)
        notice, = [item for item in report.infos if item.rule == 'local-group-normalization']
        self.assertEqual((notice.operation, notice.format), ('import', 'dip'))
        self.assertIn('4 inactive', notice.message)
        self.assertIn('4 unavailable', notice.message)


if __name__ == '__main__':
    unittest.main()
