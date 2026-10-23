"""Library properties are current editable facts, with explicit output limits."""
import unittest

from lib.design import ExportReport, new_schematic, parse_dch
from lib.design.schematic_objects import new_pattern, new_symbol
from lib.design.schematic_refs import bind_schematic_references


def sample():
    document = new_schematic()
    slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
    slot.add('VariablePath', '')
    definition = slot.add('Definition', 0)
    part = definition.append(new_symbol('Definition', '', placed=False))
    definition.append(new_pattern())
    bind_schematic_references(document)
    return document, part


def cached_part(document):
    return document.one('/Schematic/CacheLib/Slots/Slot/Definition/Part')


class CachedPropertiesTests(unittest.TestCase):
    def test_verification_import_modernizes_short_and_long_lists(self):
        source, part = sample()
        flags = (True, False, True, False, True, False, True)
        part.one('Verification').set_values(*flags)
        data = source.to_dch_bytes()
        decoded = cached_part(parse_dch(data)).one('Verification')
        start, end = decoded.source.start, decoded.source.end
        for count in (0, 3, 7, 10):
            with self.subTest(count=count):
                supplied = (flags + (True,)*3)[:count]
                varied = data[:start-3]+(1000000+count).to_bytes(3, 'big')+bytes(supplied)+data[end:]
                loaded = parse_dch(varied)
                expected = (supplied+(False,)*7)[:7]
                self.assertEqual(cached_part(loaded).one('Verification').values, expected)
                self.assertFalse(loaded.select('//VerificationFlags'))
                modern = parse_dch(loaded.to_dch_bytes())
                self.assertEqual(cached_part(modern).one('Verification').values, expected)
                self.assertEqual(modern.to_dch_bytes(), loaded.to_dch_bytes())

    def test_model_note_is_editable_and_binary_output_preserves_it(self):
        source, part = sample()
        part.set_field('ModelNote', 'Model assumptions')
        loaded = parse_dch(source.to_dch_bytes())
        self.assertEqual(cached_part(loaded).scalar('ModelNote'), 'Model assumptions')
        self.assertFalse(loaded.select('//StoredData/ModelNote'))
        cached_part(loaded).set_field('ModelNote', 'Updated assumptions')
        reloaded = parse_dch(loaded.to_dch_bytes())
        self.assertEqual(cached_part(reloaded).scalar('ModelNote'), 'Updated assumptions')
        self.assertEqual(part.scalar('ModelNote'), 'Model assumptions')

    def test_current_text_mapping_omissions_warn_and_leave_the_model_intact(self):
        source, part = sample()
        part.set_field('ModelNote', 'Model assumptions')
        for destination in ('asc', 'dchxml'):
            with self.subTest(destination=destination):
                report = ExportReport()
                getattr(source, 'to_'+destination+'_bytes')(report=report)
                notices = [notice for notice in report.warnings if notice.rule == 'cached-model-note']
                self.assertEqual(len(notices), 1)
                self.assertEqual(notices[0].destination, destination)
                self.assertEqual(part.scalar('ModelNote'), 'Model assumptions')
                self.assertFalse(report.errors)


if __name__ == '__main__':
    unittest.main()
