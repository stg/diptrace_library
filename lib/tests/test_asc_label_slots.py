"""Obsolete label slots are generated from authoritative modern choices."""
import unittest

from lib import AscExportContext, new_schematic, parse_asc, parse_dch


FIELDS = ('ShowText', 'ShowText2', 'TextAlign', 'TextAlign2',
          'FieldName1', 'FieldName2')
SLOTS = (5, 3, 2, 5, 'Earlier label', 'Second label')


def source():
    raw = parse_asc(new_schematic().to_asc_bytes().decode('cp1252'))
    schematic = raw.one('/Schematic')
    for name, value in zip(FIELDS, SLOTS):
        schematic.set_field(name, value)
    return raw.as_schematic()


def slots(document):
    schematic = document.one('/Schematic')
    return tuple(schematic.scalar(name) for name in FIELDS)


class AscLabelSlotTests(unittest.TestCase):
    def test_import_discards_obsolete_slots_and_cycles_keep_modern_choices(self):
        current = source()
        choices = current.one('/Schematic/ShowRefDes_Global').values
        expected = slots(current.as_asc())
        self.assertNotEqual(expected, SLOTS)
        for _ in range(3):
            output = current.to_asc_bytes()
            self.assertEqual(slots(current), (None,)*6)
            self.assertFalse(current.root.changed)
            self.assertEqual(slots(parse_asc(output.decode('cp1252'))), expected)
            current = parse_asc(output.decode('cp1252')).as_schematic()
            self.assertEqual(slots(current), (None,)*6)
            self.assertEqual(current.one('/Schematic/ShowRefDes_Global').values,
                             choices)

    def test_modern_edits_determine_both_text_and_binary_output(self):
        current = source()
        schematic = current.one('/Schematic')
        schematic.one('ShowRefDes_Global').set_values(2, 0, 7)
        schematic.one('ShowManufacturer_Global').set_values(1, 3)
        expected = slots(current.as_asc())
        binary = parse_dch(current.to_dch_bytes())
        self.assertEqual(binary.one('/Schematic/ShowManufacturer_Global').values, (1, 3))
        self.assertEqual(slots(binary.as_asc()), expected)
        self.assertEqual(slots(current), (None,)*6)

    def test_import_origin_does_not_choose_export_behavior(self):
        current = source()
        expected = current.to_asc_bytes()
        for origin in ('dch', 'asc', 'dchxml'):
            current.metadata['imported_from'] = origin
            self.assertEqual(current.to_asc_bytes(), expected)
        context = AscExportContext(legacy_text_slots=SLOTS)
        self.assertEqual(slots(current.as_asc(context=context))[-2:], SLOTS[-2:])
        self.assertEqual(slots(current), (None,)*6)


if __name__ == '__main__':
    unittest.main()
