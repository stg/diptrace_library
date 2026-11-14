"""Local pad-pair identities are coherent in both standalone library models."""
from pathlib import Path
import unittest

from lib.common.references import ReferenceError
from lib.component import model as component_model
from lib.component.formats.eli.decode import decode
from lib.component.formats.eli.read import construct
from lib.pattern import model as pattern_model

FIXTURES = Path(__file__).with_name('fixtures')


class InternalConnectionTests(unittest.TestCase):
    def design(self, family):
        document = family.new_library()
        if family is component_model:
            owner = document.one('/Library/Components').append(family.new_component('Example', 'U'))
        else:
            owner = document.one('/Library/Patterns')
        pattern = owner.append(family.new_pattern('Package'))
        pads = [pattern.one('Pads').append(family.new_pad(number)) for number in ('A', 'B')]
        connection = pattern.one('InternalConnections').append(family.new_internal_connection())
        return document, pattern, pads, connection

    def test_each_endpoint_follows_pad_identity_and_clone(self):
        for family in (component_model, pattern_model):
            with self.subTest(family=family.__name__):
                document, pattern, pads, pair = self.design(family)
                self.assertEqual((-1, -1), pair.values)
                pair['Pad1'], pair['Pad2'] = pads
                self.assertEqual((1, 2), pair.values)
                pads[1].move_to(pattern.one('Pads'), index=0)
                self.assertEqual((2, 1), pair.values)
                self.assertIs(pads[0], pair['Pad1'])
                self.assertIs(pads[1], pair['Pad2'])
                copied = document.clone()
                copied_pair = copied.one(pair.path)
                self.assertIs(copied.one(pads[0].path), copied_pair['Pad1'])
                self.assertIsNot(pair['Pad1'], copied_pair['Pad1'])
                pair['Pad1'] = None
                self.assertEqual((-1, 1), pair.values)
                self.assertEqual((2, 1), copied_pair.values)
                document.validate()
                copied.validate()

    def test_foreign_pad_and_scope_moves_are_atomic(self):
        for family in (component_model, pattern_model):
            with self.subTest(family=family.__name__):
                document, pattern, pads, pair = self.design(family)
                pair['Pad1'] = pads[0]
                if family is component_model:
                    owner = document.one('/Library/Components').append(family.new_component('Other', 'R'))
                else:
                    owner = document.one('/Library/Patterns')
                other = owner.append(family.new_pattern('Other'))
                foreign = other.one('Pads').append(family.new_pad('1'))
                with self.assertRaises(ReferenceError):
                    pair['Pad1'] = foreign
                with self.assertRaises(ReferenceError):
                    pair.move_to(other.one('InternalConnections'))
                with self.assertRaises(ReferenceError):
                    pads[0].move_to(other.one('Pads'))
                self.assertIs(pads[0], pair['Pad1'])
                self.assertIs(pattern.one('InternalConnections'), pair.parent)
                self.assertEqual((1, -1), pair.values)
                document.validate()

    def test_unavailable_endpoint_has_one_explicit_key_and_can_be_resolved(self):
        decoded = decode((FIXTURES/'parameters.eli').read_bytes())
        raw = decoded.root.one('Components/Component/Parts/Part/Pattern/InternalConnections')
        raw.add('IntCon', 1, 99)
        document = construct(decoded)
        pattern = document.one('/Library/Components/Component/Pattern')
        pads = pattern.select('Pads/Pad')
        pair = pattern.one('InternalConnections/IntCon')
        self.assertIs(pads[0], pair['Pad1'])
        self.assertEqual((1, 99), pair.values)
        self.assertEqual(99, pair['UnresolvedY'])
        with self.assertRaises(ReferenceError):
            pair['Pad2']
        clone = document.clone()
        copied = clone.one(pair.path)
        copied['Pad2'] = clone.one(pads[1].path)
        self.assertIsNone(copied.child('UnresolvedY'))
        self.assertEqual((1, 2), copied.values)
        self.assertEqual([], clone.references.issues)
        self.assertEqual((1, 99), pair.values)
        pair['Pad2'] = None
        self.assertIsNone(pair.child('UnresolvedY'))
        self.assertEqual((1, -1), pair.values)
        self.assertEqual([], document.references.issues)
        document.validate()
        clone.validate()

    def test_imported_endpoints_are_not_stored_indices(self):
        decoded = decode((FIXTURES/'parameters.eli').read_bytes())
        decoded.root.one('Components/Component/Parts/Part/Pattern/InternalConnections').add('IntCon', 1, 2)
        document = construct(decoded)
        pattern = document.one('/Library/Components/Component/Pattern')
        pair = pattern.one('InternalConnections/IntCon')
        pads = pattern.select('Pads/Pad')
        self.assertIsNone(pair.child('X'))
        with self.assertRaises(TypeError):
            pair['X'] = 2
        pads[0].move_to(pattern.one('Pads'))
        self.assertEqual((2, 1), pair.values)
        self.assertIs(pads[0], pair['Pad1'])
        document.validate()

    def test_canonical_connections_in_each_binary_output_revision(self):
        from lib.component.formats.eli.read import parse
        for version in (31, 32, 33):
            with self.subTest(version=version):
                document = parse((FIXTURES/f'connections_{version}.eli').read_bytes())
                pattern = document.one('/Library/Components/Component/Pattern')
                pads = pattern.select('Pads/Pad')
                pair = pattern.one('InternalConnections/IntCon')
                self.assertEqual((1, 2), pair.values)
                self.assertIs(pads[0], pair['Pad1'])
                self.assertIs(pads[1], pair['Pad2'])
                pads[1].move_to(pattern.one('Pads'), index=0)
                self.assertEqual((2, 1), pair.values)
                document.validate()


if __name__ == '__main__':
    unittest.main()
