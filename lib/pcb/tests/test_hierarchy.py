"""Hierarchy keys describe the linked schematic and retain their own order."""
import unittest

from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.model import hierarchy_records
from lib.pcb.model.hierarchy import BLOCK_ROLE, linkage_path
from lib.common.references import ReferenceError
from lib.pcb.tests.test_core_assembly import fixture


def design(*, hidden_id=75, kind=0):
    decoded = fixture()
    component = decoded.board.one('Components/Component')
    component.add('HiddenId', hidden_id)
    component.one('Pattern')['Type'] = kind
    path = component.add('HierarchyPath')
    path.add('Item', 91)
    path.add('Item', 107)
    path.add('Item', hidden_id)
    sheets = decoded.board.add('HierarchySheets')
    first = sheets.add('HSheet', 'Controller', 12)
    first.add('UpdateIds').add('UId', 91, 'Input')
    sheets.add('HSheet', 'Power', 45).add('UpdateIds').add('UId', 107, 'Supply')
    return assemble_core(decoded)


class HierarchyTests(unittest.TestCase):
    def test_assembly_types_persistent_keys_and_external_path_steps(self):
        result = design()
        component = result.components[41]
        path = component.one('HierarchyPath')
        self.assertIs(path.schema, hierarchy_records.PATH)
        self.assertEqual([step['Id'] for step in path.children()], [91, 107])
        first = result.document.one('/Board/HierarchySheets/HSheet[1]')
        self.assertIs(first.schema, hierarchy_records.SHEET)
        self.assertEqual((first['Name'], first['Number']), ('Controller', 12))
        self.assertEqual(first.one('UpdateIds/UId').values, (91, 'Input'))

    def test_list_reordering_does_not_renumber_schematic_identities(self):
        result = design()
        document = result.document
        sheet = document.one('/Board/HierarchySheets/HSheet[2]')
        sheet.move_to(sheet.parent, 0)
        self.assertEqual([row['Number'] for row in document.select('/Board/HierarchySheets/HSheet')], [45, 12])
        self.assertEqual(result.components[41].one('HierarchyPath/Item[2]')['Id'], 107)
        step = result.components[41].one('HierarchyPath/Item[1]')
        first = document.one('/Board/HierarchySheets/HSheet[2]/UpdateIds/UId')
        first['Id'] = 302
        self.assertEqual(step.values, (302,))

    def test_import_removes_stale_paths_from_objects_without_a_schematic_link(self):
        for hidden_id, kind in ((-1, 0), (75, 15), (75, 16)):
            with self.subTest(hidden_id=hidden_id, kind=kind):
                result = design(hidden_id=hidden_id, kind=kind)
                self.assertFalse(result.components[41].one('HierarchyPath').children())
                self.assertEqual(len(result.document.select('/Board/HierarchySheets/HSheet')), 2)

    def test_cloning_and_component_copy_preserve_foreign_keys_without_companion_discovery(self):
        result = design()
        component = result.components[41]
        copied = result.document.copy(component, parent=component.parent, fields={'RefDes': 'U2'})
        self.assertEqual([step['Id'] for step in copied.select('HierarchyPath/Item')], [91, 107])
        step = copied.one('HierarchyPath/Item[1]')
        self.assertIs(result.document.references.outgoing(step, role=BLOCK_ROLE)[0].target,
                      result.document.one('/Board/HierarchySheets/HSheet[1]/UpdateIds/UId'))
        cloned = result.document.clone()
        cloned.one('/Board/HierarchySheets/HSheet[1]/UpdateIds/UId')['Id'] = 205
        self.assertEqual(cloned.one('/Board/Components/Component[1]/HierarchyPath/Item[1]')['Id'], 205)
        self.assertEqual(component.one('HierarchyPath/Item[1]')['Id'], 91)
        cloned.one('/Board/HierarchySheets/HSheet[1]')['Name'] = 'Renamed'
        self.assertEqual(cloned.one('/Board/HierarchySheets/HSheet[1]')['Number'], 12)
        self.assertEqual(result.document.one('/Board/HierarchySheets/HSheet[1]')['Name'], 'Controller')

    def test_terminal_component_identity_is_derived_instead_of_stored_twice(self):
        result = design()
        component = result.components[41]
        self.assertEqual(linkage_path(component), (91, 107, 75))
        component['HiddenId'] = 804
        self.assertEqual(linkage_path(component), (91, 107, 804))
        self.assertEqual([step['Id'] for step in component.select('HierarchyPath/Item')], [91, 107])
        with self.assertRaises(ReferenceError):
            component['HiddenId'] = -1
        self.assertEqual(component['HiddenId'], 804)

    def test_block_keys_are_global_and_removal_of_a_referenced_block_is_atomic(self):
        result = design()
        first, second = result.document.select('/Board/HierarchySheets/HSheet/UpdateIds/UId')
        with self.assertRaises(ReferenceError):
            first['Id'] = second['Id']
        self.assertEqual(first['Id'], 91)
        with self.assertRaises(ReferenceError):
            first.detach()
        self.assertIsNotNone(first.parent)
        sheet = first.parent.parent
        with self.assertRaises(ReferenceError):
            result.document.copy(sheet, parent=sheet.parent)
        self.assertEqual(len(sheet.parent.children()), 2)

    def test_links_are_retargetable_and_names_do_not_change_the_placed_refdes(self):
        result = design()
        component = result.components[41]
        component['RefDes'] = 'D13_3'
        step = component.one('HierarchyPath/Item[1]')
        link, = result.document.references.outgoing(step, role=BLOCK_ROLE)
        block = result.document.one('/Board/HierarchySheets/HSheet[2]/UpdateIds/UId')
        result.document.references.retarget(link, block)
        block['Name'] = 'Renamed block'
        self.assertEqual(step['Id'], 107)
        self.assertEqual(component['RefDes'], 'D13_3')
        self.assertEqual(result.document.refdes('D13_').designators(), ['D13_3'])
        self.assertEqual(result.document.refdes('D').designators(), [])
        with self.assertRaises(ReferenceError):
            result.document.references.retarget(link, component)

    def test_unresolved_foreign_block_stays_explicit_and_does_not_open_a_companion(self):
        # Construct another import with an unknown enclosing block.
        decoded = fixture()
        component = decoded.board.one('Components/Component')
        component.add('HiddenId', 75)
        path = component.add('HierarchyPath')
        path.add('Item', 904)
        path.add('Item', 75)
        imported = assemble_core(decoded)
        step = imported.components[41].one('HierarchyPath/Item')
        self.assertEqual(step['Id'], 904)
        self.assertTrue(imported.document.references.unresolved_slot(step))
        self.assertEqual(len(imported.document.references.issues), 1)

    def test_import_does_not_silently_discard_a_contradictory_terminal(self):
        from lib.pcb.formats.dip.binary import DipError
        decoded = fixture()
        component = decoded.board.one('Components/Component')
        component.add('HiddenId', 75)
        path = component.add('HierarchyPath')
        path.add('Item', 91)
        path.add('Item', 999)
        with self.assertRaisesRegex(DipError, 'terminal'):
            assemble_core(decoded)

    def test_expanded_and_plain_components_can_have_the_same_visible_refdes(self):
        decoded = fixture()
        components = decoded.board.one('Components')
        expanded = components.one('Component')
        expanded.one('RefDes').set_values('D13_3')
        expanded.add('HiddenId', 75)
        path = expanded.add('HierarchyPath')
        path.add('Item', 91)
        path.add('Item', 75)
        plain = expanded.clone()
        plain.one('Number').set_values(42)
        plain.one('HiddenId').set_values(804)
        plain.one('HierarchyPath').one('Item[2]').detach()
        plain.one('HierarchyPath/Item').detach()
        components.append(plain)
        sheets = decoded.board.add('HierarchySheets')
        sheets.add('HSheet', 'Input', 12).add('UpdateIds').add('UId', 91, 'Block3')

        result = assemble_core(decoded)
        document = result.document
        expanded, plain = result.components[41], result.components[42]
        matches = document.select('/Board/Components/Component', where=lambda part: part['RefDes'] == 'D13_3')
        self.assertEqual(matches, [expanded, plain])
        self.assertEqual(document.refdes('D13_').matches('D13_3'), [expanded, plain])
        self.assertEqual(linkage_path(expanded), (91, 75))
        self.assertEqual(linkage_path(plain), ())
        self.assertIsNot(result.pads[41, 5], result.pads[42, 5])
        plain['X'] = 20
        result.pads[42, 5]['Net'] = None
        self.assertEqual(expanded['X'], 0)
        self.assertIs(result.pads[41, 5]['Net'], result.nets[73])
        copied = document.clone()
        self.assertEqual(len(copied.refdes('D13_').matches('D13_3')), 2)

        # Importing an existing ambiguity does not grant a separate namespace
        # for later renames. Occupancy uses the complete placed name.
        plain['RefDes'] = 'D13_3'  # An unchanged assignment is not a rename.
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            plain['RefDes'] = 'D13_003'
        self.assertEqual(plain['RefDes'], 'D13_3')
        plain['RefDes'] = 'D13'
        self.assertEqual(plain['RefDes'], 'D13')
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            plain['RefDes'] = 'D13_3'
        self.assertEqual(plain['RefDes'], 'D13')
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            expanded['RefDes'] = 'D13'
        self.assertEqual(expanded['RefDes'], 'D13_3')
        self.assertEqual(linkage_path(expanded), (91, 75))


if __name__ == '__main__':
    unittest.main()
