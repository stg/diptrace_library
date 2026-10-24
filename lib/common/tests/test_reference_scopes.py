"""A known unresolved local link must not freeze unrelated document arrays."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib import Document, Element, Index, ReferenceError, SourceSpan, Value


class ReferenceScopeTests(unittest.TestCase):
    def test_new_issue_guards_current_state_after_earlier_valid_edits(self):
        document = Document()
        targets = document.root.add('Targets')
        targets.add('Item', 'first')
        document.references.watch(targets)
        targets.add('Item', 'second')
        document.rebuild()
        source = document.root.add('Source')
        field = source.add('Target', 99)
        document.references.note(source, 'new unresolved target', Index(field), collections=(targets,))
        document.rebuild()
        copied = document.clone()
        copied.rebuild()
        before = copied.one('/Targets').children()
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            before[0].move_to(copied.one('/Targets'), 1)
        self.assertEqual(copied.one('/Targets').children(), before)
        copied.validate()
        document.rebuild()

    def test_new_issue_does_not_accept_changes_blocked_by_an_existing_issue(self):
        for old_global, new_global in ((False, False), (False, True), (True, False), (True, True)):
            with self.subTest(old_global=old_global, new_global=new_global):
                document, targets, target, source, field, unused, issue = self.design()
                if old_global:
                    document.references.discard_issue(issue)
                    document.references.note(source, 'unknown target domain', Index(field))
                with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
                    targets.add('Item', 'blocked change')
                document.references.note(source, 'another unresolved target', Index(field),
                                         collections=None if new_global else (targets,))
                with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
                    targets.add('Item', 'still blocked')
                document.validate()

    def test_new_scope_does_not_retroactively_block_unrelated_edits(self):
        document, targets, target, source, field, unused, issue = self.design()
        sources = source.parent
        unused.detach()
        document.rebuild()
        other = sources.add('Item', 'another source')
        other_field = other.add('Target', 100)
        document.references.note(other, 'new source-domain link', Index(other_field), collections=(sources,))
        document.rebuild()
        document.clone().rebuild()
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            sources.add('Item', 'now blocked')
        document.validate()

    def test_released_scope_can_be_edited_before_a_new_issue_is_added(self):
        document, targets, target, source, field, unused, issue = self.design()
        document.references.discard_issue(issue)
        targets.add('Item', 'allowed after discard')
        document.rebuild()
        document.references.note(source, 'new unresolved link', Index(field), collections=(targets,))
        document.rebuild()
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            targets.add('Item', 'blocked after new issue')
        document.validate()

    def test_provenance_changes_do_not_change_an_unresolved_value(self):
        document, targets, target, source, field, unused, issue = self.design()
        field.set_values(Value(99, 'number', lexeme='99', source=SourceSpan('dch', 100, 103, 'example')))
        document.rebuild()
        field.set_values(Value(99, 'number'))
        document.rebuild()
        field.set_values('99')
        with self.assertRaisesRegex(ReferenceError, 'unresolved reference was edited'):
            document.rebuild()

    def design(self):
        document = Document()
        targets = document.root.add('Targets')
        target = targets.add('Item', 'target')
        sources = document.root.add('Sources')
        source = sources.add('Item', 'source')
        field = source.add('Target', 99)
        unused = sources.add('Item', 'unrelated')
        issue = document.references.note(source, 'unresolved local target', Index(field), collections=(targets,))
        document.references.watch(sources)
        return document, targets, target, source, field, unused, issue

    def test_unrelated_removal_and_clone_preserve_the_local_scope(self):
        document, targets, target, source, field, unused, issue = self.design()
        unused.detach()
        document.rebuild()
        copied = document.clone()
        scope = copied.references.issues[0].collections
        self.assertEqual(scope, (copied.one('/Targets'),))
        self.assertIsNot(scope[0], targets)
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            copied.one('/Targets').add('Item', 'new target')
        copied.validate()
        document.rebuild()
        self.assertEqual(field.values, (99,))

    def test_target_scalar_edits_are_allowed_but_slot_edits_require_binding(self):
        document, targets, target, source, field, unused, issue = self.design()
        target.set_values('renamed')
        document.rebuild()
        field.set_values(100)
        with self.assertRaisesRegex(ReferenceError, 'unresolved reference was edited'):
            document.rebuild()

    def test_detached_issue_requires_explicit_discard(self):
        document, targets, target, source, field, unused, issue = self.design()
        with self.assertRaisesRegex(ReferenceError, 'unresolved reference content'):
            source.detach()
        document.references.discard_issue(issue)
        source.detach()
        document.rebuild()
        self.assertEqual(document.references.issues, [])

    def test_binding_resolves_the_issue_and_releases_the_scope(self):
        document, targets, target, source, field, unused, issue = self.design()
        document.references.bind(source, target, Index(field))
        self.assertEqual(document.references.issues, [])
        self.assertEqual(field.values, (0,))
        targets.add('Item', 'other')
        target.move_to(targets, 1)
        document.rebuild()
        self.assertEqual(field.values, (1,))

    def test_external_scope_is_rejected_before_registering_an_issue(self):
        document = Document()
        source = document.root.add('Item')
        field = source.add('Target', 99)
        with self.assertRaises(ReferenceError):
            document.references.note(source, 'invalid scope', Index(field), collections=(Element('Outside'),))
        self.assertEqual(document.references.issues, [])

    def test_forced_renumbering_cannot_give_a_missing_key_an_unrelated_target(self):
        for global_scope in (False, True):
            with self.subTest(global_scope=global_scope):
                document = Document()
                targets = document.root.add('Targets')
                target = targets.add('Item')
                key = target.add('Number', 12)
                document.references.bind(target, target, Index(key), preserve=True)
                source = document.root.add('Source')
                missing = source.add('Target', 0)
                issue = document.references.note(source, 'missing saved key', Index(missing),
                    collections=None if global_scope else (targets,))
                document.rebuild(force=False)
                with self.assertRaisesRegex(ReferenceError, 'unresolved references prevent renumbering'):
                    document.rebuild(force=True)
                self.assertEqual((key.values, missing.values), ((12,), (0,)))
                copied = document.clone()
                with self.assertRaisesRegex(ReferenceError, 'unresolved references prevent renumbering'):
                    copied.rebuild(force=True)
                document.references.discard_issue(issue)
                document.references.bind(source, target, Index(missing), preserve=True)
                document.rebuild(force=True)
                self.assertEqual((key.values, missing.values), ((0,), (0,)))

    def test_forced_renumbering_is_allowed_outside_an_unresolved_scope(self):
        document, targets, target, source, field, unused, issue = self.design()
        key = target.add('Number', 0)
        document.references.bind(target, target, Index(key), preserve=True)
        other = document.root.add('OtherTargets').add('Item')
        other_key = other.add('Number', 12)
        document.references.bind(other, other, Index(other_key), preserve=True)
        document.rebuild(force=True)
        self.assertEqual((key.values, other_key.values, field.values), ((0,), (0,), (99,)))

    def test_renumbering_preflight_leaves_other_planned_changes_untouched(self):
        document, targets, target, source, field, unused, issue = self.design()
        document.references.discard_issue(issue)
        field.set_values(0)
        document.references.note(source, 'missing saved key', Index(field), collections=(targets,))
        key = target.add('Number', 12)
        document.references.bind(target, target, Index(key), preserve=True)
        other = document.root.add('OtherTargets').add('Item')
        other_key = other.add('Number', 35)
        document.references.bind(other, other, Index(other_key), preserve=True)
        with self.assertRaisesRegex(ReferenceError, 'unresolved references prevent renumbering'):
            document.rebuild(force=True)
        self.assertEqual((key.values, other_key.values, field.values), ((12,), (35,), (0,)))

    def test_compound_missing_key_must_match_every_projected_index(self):
        for pin_index in (0, 99):
            with self.subTest(pin_index=pin_index):
                document = Document()
                parts = document.root.add('Components')
                part = parts.add('Part')
                key = part.add('Number', 12)
                part.add('Pins').add('Pin')
                document.references.bind(part, part, Index(key), preserve=True)
                source = document.root.add('Connection', 0, pin_index)
                document.references.note(source, 'missing component/pin',
                    Index(source, 0, 2), Index(source, 1), collections=(parts,))
                if pin_index == 0:
                    with self.assertRaisesRegex(ReferenceError, 'unresolved references prevent renumbering'):
                        document.rebuild(force=True)
                    self.assertEqual(key.values, (12,))
                else:
                    document.rebuild(force=True)
                    self.assertEqual(key.values, (0,))
                self.assertEqual(source.values, (0, pin_index))


if __name__ == '__main__':
    unittest.main()
