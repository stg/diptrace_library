"""Named keys and positional references share identity and atomic rebuild rules."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.design import Document, Index, Key, Property, ReferenceError


class KeyReferenceTests(unittest.TestCase):
    def test_property_rename_does_not_rewrite_saved_index_keys(self):
        document = Document()
        parts = document.root.add('Components')
        target = parts.add('Part', 'Symbol', 'PORT')
        key = target.add('Number', 12)
        document.references.bind(target, target, Index(key), preserve=True)
        source = document.root.add('Connection')
        number, name = source.add('Number', 12), source.add('Name', 'PORT')
        document.references.bind(source, target, Index(number), Property(name, target_argument=1), preserve=True)
        target.set_argument(1, 'RENAMED')
        document.rebuild(force=False)
        self.assertEqual((key.values, number.values, name.values), ((12,), (12,), ('RENAMED',)))

    def test_retarget_and_clone_canonicalize_the_affected_index_collection(self):
        document = Document()
        parts = document.root.add('Components')
        first, second = [parts.add('Part') for _ in range(2)]
        for row, value in ((first, 12), (second, 35)):
            field = row.add('Number', value)
            document.references.bind(row, row, Index(field), preserve=True)
        source = document.root.add('Connection')
        field = source.add('Number', 12)
        reference = document.references.bind(source, first, Index(field), preserve=True)
        document.references.retarget(reference, second)
        copied = document.clone()
        copied.rebuild(force=False)
        self.assertEqual([r.scalar('Number') for r in copied.select('/Components/Part')], [0, 1])
        self.assertEqual(copied.one('/Connection/Number').values, (1,))
        self.assertEqual(first.scalar('Number'), 12)
        document.rebuild(force=False)
        self.assertEqual([r.scalar('Number') for r in parts.children()], [0, 1])

    def test_reorder_canonicalizes_unchanged_siblings_with_saved_numeric_gaps(self):
        document = Document()
        parts = document.root.add('Components')
        rows = [parts.add('Part') for _ in range(3)]
        for row, value in zip(rows, (1, 2, 3)):
            field = row.add('Number', value)
            document.references.bind(row, row, Index(field), preserve=True)
        link = document.root.add('Connection').add('Part', 1)
        document.references.bind(link, rows[0], Index(link), preserve=True)
        document.rebuild(force=False)
        self.assertEqual([r.scalar('Number') for r in rows], [1, 2, 3])
        rows[2].move_to(parts, 1)
        document.rebuild(force=False)
        self.assertEqual([r.scalar('Number') for r in parts.children()], [0, 1, 2])
        self.assertEqual(link.values, (0,))

    def test_property_names_need_not_be_unique_and_retarget_with_the_index(self):
        document = Document()
        parts = document.root.add('Components')
        first = parts.add('Part', 'Symbol', 'PORT')
        second = parts.add('Part', 'Symbol', 'PORT')
        source = document.root.add('Connection')
        number, name = source.add('Number', 0), source.add('Name', 'PORT')
        reference = document.references.bind(source, first, Index(number),
            Property(name, target_argument=1), preserve=True)
        first.set_argument(1, 'RENAMED')
        first.move_to(parts, 1)
        document.rebuild()
        self.assertEqual((number.values, name.values), ((1,), ('RENAMED',)))
        document.references.retarget(reference, second)
        self.assertEqual((number.values, name.values), ((0,), ('PORT',)))
        second.detach()
        with self.assertRaises(ReferenceError):
            document.rebuild()
        self.assertEqual((number.values, name.values), ((0,), ('PORT',)))

    def test_named_properties_preserve_types_and_refuse_projection_chains(self):
        document = Document()
        target = document.root.add('Items').add('Item')
        locked = target.add('Locked', True)
        source = document.root.add('Connection')
        value = source.add('Locked', True)
        document.references.bind(source, target, Property(value, 'Locked'), preserve=True)
        locked.set_values(False)
        document.rebuild()
        self.assertIs(value.values[0], False)
        self.assertEqual(value.arguments[0].kind, 'boolean')
        another = document.root.add('Connection').add('Locked', False)
        with self.assertRaisesRegex(ReferenceError, 'property target is managed'):
            document.references.bind(another, source, Property(another, 'Locked'), preserve=True)
        locked.set_values(0)
        with self.assertRaisesRegex(ReferenceError, 'types/units'):
            document.rebuild()

    def design(self):
        document = Document()
        parts = document.root.add('Components')
        first = parts.add('Part')
        first.add('Id', 12)
        pin = first.add('Pins').add('Pin')
        second = parts.add('Part')
        second.add('Id', 35)
        wire = document.root.add('Wire')
        wire.add('Part', 12)
        wire.add('Pin', 0)
        reference = document.references.bind(
            wire, pin, Key(wire.one('Part'), ancestor=2), Index(wire.one('Pin')),
            role='wire-pin', preserve=True)
        return document, first, second, wire, reference

    def test_reorder_preserves_keys_and_key_edit_updates_all_references(self):
        document, first, second, wire, reference = self.design()
        first.move_to(first.parent, 1)
        document.rebuild()
        self.assertEqual(wire.scalar('Part'), 12)
        first.set_field('Id', 99)
        document.rebuild()
        self.assertEqual(wire.scalar('Part'), 99)
        copied = document.clone()
        copied.one('/Components/Part[2]/Id').set_values(100)
        copied.rebuild()
        self.assertEqual(copied.one('/Wire/Part').values, (100,))
        self.assertEqual(wire.scalar('Part'), 99)

    def test_duplicate_key_failure_is_atomic(self):
        document, first, second, wire, reference = self.design()
        first.set_field('Id', 35)
        with self.assertRaisesRegex(ReferenceError, 'duplicate Id'):
            document.rebuild()
        self.assertEqual(wire.scalar('Part'), 12)

    def test_named_style_keys_follow_rename_and_retarget(self):
        document = Document()
        styles = document.root.add('Styles')
        first = styles.add('Style')
        first.add('Name', 'PadT0')
        second = styles.add('Style')
        second.add('Name', 'PadT1')
        pad = document.root.add('Pad')
        field = pad.add('Style', 'PadT0')
        reference = document.references.bind(pad, first, Key(field, 'Name'), preserve=True)
        first.set_field('Name', 'PowerPad')
        document.rebuild()
        self.assertEqual(field.values, ('PowerPad',))
        document.references.retarget(reference, second)
        self.assertEqual(field.values, ('PadT1',))
        field.set_values('unbound')
        with self.assertRaisesRegex(ReferenceError, 'retarget'):
            document.rebuild()


if __name__ == '__main__':
    unittest.main()
