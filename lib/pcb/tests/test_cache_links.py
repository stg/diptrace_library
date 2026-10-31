"""The active cache prefix follows owned slot identities through data edits."""
import unittest
from unittest.mock import patch

from lib.common.asc import loads, dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.library_records import DESIGN_LINK, DESIGN_LINKS
from lib.common.references import ReferenceError
from lib.common.references import Property
from lib.common.schema import Field, Record
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.model.objects import new_document, new_component, new_pattern_drawing, new_user_field
from lib.pcb.tests.test_asc_cache import source
from lib.schematic.model.collections import DESIGN_LINK as SCHEMATIC_LINK


def design(*, active=0, keys=(0, 1, 77)):
    document = new_document()
    board = document.one('/Board')
    slots = board.one('CacheLib/Slots')
    for name in ('first.lib', 'second.lib'):
        slots.add('Slot', 0, name)
    links = board.one('DesignCache_Links')
    for key in keys:
        links.add('Link', key)
    board['DesignCache_Count'] = active
    return document, board, slots.children('Slot'), links.children('Link')


class CacheLinkTests(unittest.TestCase):
    def test_import_discards_spare_capacity_without_discarding_owned_definitions(self):
        syntax = loads(source())
        board = syntax.one('/Board')
        board.add('DesignCache_Count', -1)
        rows = board.add('DesignCache_Links', 3)
        for key in (0, 77, -9):
            rows.add('Link', key)

        @import_diagnostics('asc')
        def read(text):
            return assemble_core(prepare_core(text)).document

        report = ConversionReport()
        document = read(dumps(syntax, preserve=False), report=report)
        owner = document.one('/Board')
        self.assertFalse(owner.one('DesignCache_Links').children())
        self.assertEqual(owner['DesignCache_Count'], -1)
        self.assertTrue(owner.one('CacheLib/Slots').children())
        self.assertFalse(document.references.outgoing(owner, role='design-cache-slot'))
        self.assertIn('cache-selection-capacity', {notice.rule for notice in report.infos})
        document.references.validate()

    def test_import_checks_capacity_header_and_keeps_only_the_active_selection(self):
        syntax = loads(source())
        board = syntax.one('/Board')
        board.add('DesignCache_Count', 0)
        links = board.add('DesignCache_Links', 3)
        for key in (0, 1, 77):
            links.add('Link', key)
        document = assemble_core(prepare_core(dumps(syntax, preserve=False))).document
        owner = document.one('/Board')
        first, = owner.select('DesignCache_Links/Link')
        self.assertIs(first.schema, DESIGN_LINK)
        self.assertIs(first.schema, SCHEMATIC_LINK)
        self.assertIs(first.parent.schema, DESIGN_LINKS)
        self.assertFalse(first.parent.arguments)
        self.assertEqual(first['SlotIndex'], 0)
        self.assertEqual(len(document.references.outgoing(owner, role='design-cache-slot')), 1)
        with self.assertRaisesRegex(ValueError, 'count does not match rows'):
            assemble_core(prepare_core(dumps(syntax, preserve=False).replace('(DesignCache_Links 3', '(DesignCache_Links 4')))

    def test_slot_reorder_updates_active_links_without_rebuild_or_global_scan(self):
        document, board, (first, second), (a, b, tail) = design()
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole-document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole-graph scan')):
            second.move_to(first.parent, 0)
        self.assertEqual((a['SlotIndex'], b['SlotIndex'], tail['SlotIndex']), (1, 1, 77))
        self.assertIs(document.references.outgoing(board, role='design-cache-slot')[0].target, first)
        document.validate()

    def test_expanding_prefix_activates_new_links_atomically(self):
        document, board, (first, second), (a, b, _) = design()
        board['DesignCache_Count'] = 1
        self.assertEqual({r.target for r in document.references.outgoing(board, role='design-cache-slot')}, {first, second})
        second.move_to(first.parent, 0)
        self.assertEqual((a['SlotIndex'], b['SlotIndex']), (1, 0))
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            board['DesignCache_Count'] = 0
        self.assertEqual(board['DesignCache_Count'], 1)
        reference = next(r for r in document.references.outgoing(board, role='design-cache-slot') if r.indices[0].field is b)
        document.references.discard(reference)
        board['DesignCache_Count'] = 0
        document.validate()

    def test_new_literal_link_activates_when_added_to_the_prefix(self):
        document, board, (_, second), _ = design(active=-1, keys=())
        link = board.one('DesignCache_Links').add('Link', 1)
        self.assertIs(link.schema, DESIGN_LINK)
        self.assertFalse(document.references.outgoing(board, role='design-cache-slot'))
        board['DesignCache_Count'] = 0
        self.assertIs(document.references.outgoing(board, role='design-cache-slot')[0].target, second)
        document.validate()

    def test_projected_prefix_change_activates_links_in_the_same_edit(self):
        document, board, (first, second), _ = design(active=-1)
        counter = document.root.add('Counter', -1).bind_schema(Record('Counter', {
            'Value': Field('Value', 'integer', required=True)}, parameters=('Value',)))
        document.references.bind(board, counter, Property(board.one('DesignCache_Count'), 'Value'), role='counter')
        counter['Value'] = 1
        self.assertEqual(board['DesignCache_Count'], 1)
        self.assertEqual({r.target for r in document.references.outgoing(board, role='design-cache-slot')}, {first, second})
        with self.assertRaises(ReferenceError):
            counter['Value'] = -1
        self.assertEqual((counter['Value'], board['DesignCache_Count']), (1, 1))
        document.validate()

    def test_unknown_active_key_is_scoped_and_preserved_in_a_clone(self):
        document, board, _, (_, _, tail) = design()
        board['DesignCache_Count'] = 2
        issue, = document.references.issues
        self.assertEqual(issue.collections, (board.one('CacheLib/Slots'),))
        self.assertEqual(tail['SlotIndex'], 77)
        clone = document.clone()
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            clone.one('/Board')['DesignCache_Count'] = 1
        clone.references.discard_issue(clone.references.issues[0])
        clone.one('/Board')['DesignCache_Count'] = 1
        self.assertEqual(board['DesignCache_Count'], 2)
        clone.validate()

    def test_one_edit_can_activate_cache_and_user_text_links_together(self):
        document, board, (_, second), _ = design()
        component = board.one('Components').append(new_component('Device', 'U1'))
        user = component.one('UserFields').append(new_user_field('Order', 'A123'))
        shape = new_pattern_drawing(kind=1)
        shape['TextShow'] = 20
        shape.one('TextLine').add('pt', 'Literal')
        component.one('Pattern/Shapes').append(shape)
        counter = document.root.add('Counter', 0).bind_schema(Record('Counter', {
            'Value': Field('Value', 'integer', required=True),
            'Choice': Field('Choice', 'integer', getter=lambda node: 1+node['Value']*6,
                            value_dependencies=lambda node: ((node, 'Value'),)),
        }, parameters=('Value',)))
        document.references.bind(board, counter, Property(board.one('DesignCache_Count'), 'Value'), role='counter')
        document.references.bind(shape, counter, Property(shape.one('Type'), 'Choice'), role='text-counter')
        counter['Value'] = 1
        self.assertEqual(board['DesignCache_Count'], 1)
        self.assertEqual(shape['TextShow'], 20)
        self.assertEqual(shape['Type'], 7)
        self.assertEqual(shape.one('TextLine/pt')['Text'], 'A123')
        self.assertIs(document.references.outgoing(shape, role='marking-user-field')[0].target, user)
        self.assertIn(second, {r.target for r in document.references.outgoing(board, role='design-cache-slot')})
        with self.assertRaises(ReferenceError):
            counter['Value'] = 0
        self.assertEqual((counter['Value'], board['DesignCache_Count'], shape['TextShow']), (1, 1, 20))
        document.validate()

    def test_retarget_delete_and_mode_errors_leave_data_consistent(self):
        document, board, (first, second), (a, _, _) = design()
        reference, = document.references.outgoing(board, role='design-cache-slot')
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            a['SlotIndex'] = 1
        document.references.retarget(reference, second)
        self.assertEqual(a['SlotIndex'], 1)
        before = a.parent.children()
        with self.assertRaises(ReferenceError):
            a.move_to(a.parent)
        self.assertEqual(a.parent.children(), before)
        with self.assertRaises(ReferenceError):
            second.detach()
        other, _, (foreign, _), _ = design()
        with self.assertRaises(ReferenceError):
            document.references.retarget(document.references.outgoing(board, role='design-cache-slot')[0], foreign)
        self.assertIsNot(other, document)
        document.validate()

    def test_invalid_prefix_does_not_change_values_or_create_links(self):
        document, board, _, _ = design(active=-1)
        for value in (-2, 3):
            with self.subTest(value=value), self.assertRaises(ReferenceError):
                board['DesignCache_Count'] = value
            self.assertEqual(board['DesignCache_Count'], -1)
            self.assertFalse(document.references.outgoing(board, role='design-cache-slot'))

    def test_clone_keeps_slot_targets_local_and_capacity_literal(self):
        document, board, _, _ = design(active=1)
        cloned = document.clone()
        cloned.one('/Board/CacheLib/Slots/Slot[2]').move_to(cloned.one('/Board/CacheLib/Slots'), 0)
        self.assertEqual([r['SlotIndex'] for r in cloned.select('/Board/DesignCache_Links/Link')], [1, 0, 77])
        self.assertEqual([r['SlotIndex'] for r in board.select('DesignCache_Links/Link')], [0, 1, 77])
        cloned.validate()
        document.validate()
