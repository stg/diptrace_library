"""Live component families and atomic RefDes collision checks."""
import unittest

from lib import ConversionReport, Element, new_schematic, new_symbol, parse, serialize


class SchematicRefDesTests(unittest.TestCase):
    def setUp(self):
        self.document = new_schematic()
        self.parts = self.document.one('/Schematic/Components')

    def part(self, reference, **fields):
        part = new_symbol('Component', reference)
        for name, value in fields.items():
            part[name] = value
        return self.parts.append(part)

    def test_view_returns_all_units_and_excludes_other_domains(self):
        first = self.part('R003', PartNumber=0)
        second = self.part('R003', PartNumber=1, Page=1)
        self.part('R1', Enabled=False)
        self.part('R2', PartType=2)
        self.part('R1-X1')
        # Generic descendants can contain cached/non-placed Part records.
        self.document.root.add('Other').append(Element('Part', 'Cached', 'R1'))
        family = self.document.refdes('R')
        self.assertEqual(family.matches(), [first, second])
        self.assertEqual(family.matches('R3'), [first, second])
        self.assertEqual(family.designators(), ['R003'])
        self.assertEqual(family.first_free(), 'R1')

    def test_view_observes_edits_attachment_removal_and_reordering(self):
        first, second = self.part('R2'), self.part('R10')
        family = self.document.refdes('R')
        self.assertEqual(family.first(), 'R2')
        first['RefDes'] = 'R1'
        self.assertEqual(family.first_free(), 'R2')
        added = self.part('R3')
        self.assertEqual(family.matches(), [first, added, second])
        second.move_to(self.parts, 0)
        self.assertEqual(family.designators(), ['R1', 'R3', 'R10'])
        self.document.remove(first)
        self.assertEqual(family.first_free(), 'R1')
        added['Enabled'] = False
        self.assertEqual(family.matches(), [second])

    def test_rename_collision_is_atomic_and_spelling_change_is_valid(self):
        first, second = self.part('R003'), self.part('R4')
        before = self.document.to_dch_bytes()
        with self.assertRaisesRegex(ValueError, "already occupied"):
            second['RefDes'] = 'R0003'
        self.assertEqual(second['RefDes'], 'R4')
        self.assertEqual(self.document.to_dch_bytes(), before)
        first['RefDes'] = 'R3'
        self.assertEqual(self.document.refdes('R').designators(), ['R3', 'R4'])
        self.assertIs(self.document.refdes('R').matches('R003')[0], first)
        with self.assertRaisesRegex(ValueError, "already occupied"):
            first.set('RefDes', 'R4')
        self.assertEqual(first['RefDes'], 'R3')
        self.document.validate()

    def test_attachment_and_copy_reject_different_spellings_of_occupied_counter(self):
        first = self.part('R003')
        candidate = new_symbol('Component', 'R3')
        before = tuple(self.parts.children())
        with self.assertRaisesRegex(ValueError, "already occupied"):
            self.parts.append(candidate)
        self.assertIsNone(candidate.parent)
        self.assertEqual(tuple(self.parts.children()), before)
        with self.assertRaisesRegex(ValueError, "already occupied"):
            self.document.copy(first, fields={'RefDes': 'R3'})
        self.assertEqual(tuple(self.parts.children()), before)
        copied = self.document.copy(first, fields={'RefDes': self.document.refdes('R').first_free()})
        self.assertEqual(copied['RefDes'], 'R1')
        self.document.validate()

    def test_existing_multipart_units_keep_shared_literal_names(self):
        first = self.part('U003', PartNumber=0)
        second = self.part('U003', PartNumber=1)
        self.assertEqual(self.document.refdes('U').matches('U3'), [first, second])
        first['RefDes'] = 'U003'  # An unchanged assignment remains valid.
        with self.assertRaisesRegex(ValueError, "already occupied"):
            first['RefDes'] = 'U3'
        self.assertEqual((first['RefDes'], second['RefDes']), ('U003', 'U003'))

    def test_enabling_a_conflicting_alias_is_atomic(self):
        self.part('R3')
        disabled = self.part('R003', Enabled=False)
        with self.assertRaisesRegex(ValueError, "already occupied"):
            disabled['Enabled'] = True
        self.assertFalse(disabled['Enabled'])

    def test_bare_prefixes_share_zero_occupancy(self):
        first = self.part('U')
        self.assertIs(self.document.refdes('U').matches('U0')[0], first)
        self.assertEqual(self.document.refdes('U').first_free(0), 'U1')
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            self.part('U000')
        first['RefDes'] = 'U0'
        self.assertEqual(first['RefDes'], 'U0')
        self.assertIs(self.document.refdes('U').matches('U')[0], first)

    def test_punctuation_is_literal_and_spaces_are_rejected_atomically(self):
        part = self.part('BLOCK_%_-1')
        self.assertIs(self.document.refdes('BLOCK_%_-').matches('BLOCK_%_-01')[0], part)
        before = part['RefDes']
        with self.assertRaisesRegex(ValueError, 'spaces'):
            part['RefDes'] = 'R 1'
        self.assertEqual(part['RefDes'], before)
        candidate = new_symbol('Component', 'R 1')
        with self.assertRaisesRegex(ValueError, 'spaces'):
            self.parts.append(candidate)
        self.assertIsNone(candidate.parent)

    def test_managed_multipart_names_follow_one_atomic_change(self):
        from lib import Property
        first, second = self.part('U003'), self.part('U003')
        self.document.references.bind(second, first, Property(second.child('RefDes'), 'RefDes'))
        first['RefDes'] = 'U3'
        self.assertEqual((first['RefDes'], second['RefDes']), ('U3', 'U3'))
        first['RefDes'] = 'U4'
        self.assertEqual((first['RefDes'], second['RefDes']), ('U4', 'U4'))
        self.part('U5')
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            first['RefDes'] = 'U5'
        self.assertEqual((first['RefDes'], second['RefDes']), ('U4', 'U4'))

    def test_cross_document_move_checks_destination_occupancy(self):
        first = self.part('R003')
        other = new_schematic()
        destination = other.one('/Schematic/Components')
        destination.append(new_symbol('Other', 'R3'))
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            first.move_to(destination)
        self.assertIs(first.parent, self.parts)
        self.assertEqual(len(destination.children()), 1)

    def test_same_helpers_after_importing_each_format(self):
        self.part('R003', PartNumber=0)
        self.part('R003', PartNumber=1)
        self.part('R10')
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                data = serialize(self.document, format=format, report=ConversionReport())
                restored = parse(data, format=format)
                family = restored.refdes('R')
                self.assertEqual(family.designators(), ['R003', 'R10'])
                self.assertEqual(len(family.matches('R3')), 2)
                self.assertEqual(family.next('R3', mode='existing'), 'R10')
                self.assertEqual(family.first_free(), 'R1')
                part = family.matches('R10')[0]
                part['RefDes'] = 'R2'
                self.assertEqual(family.first_free(), 'R1')
                self.assertEqual(family.first(), 'R2')

    def test_source_inspection_requires_normal_import_before_refdes_view(self):
        from lib import parse_asc
        source = parse_asc(self.document.to_asc())
        with self.assertRaisesRegex(TypeError, "shared schematic model"):
            source.refdes('R')
