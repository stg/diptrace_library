"""Ordinary exports use stored settings and overridable library defaults."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import (new_schematic, parse_asc, parse_dch, parse_dchxml,
                        AscExportContext, DchXmlExportContext, IncompleteDocumentError, parse, ExportReport)
from lib.schematic.layout.markings import (MarkingStyle)
from lib.schematic.model.objects import (new_symbol)
from lib.schematic.model.refs import (bind_schematic_references)


class ExportDefaultsTests(unittest.TestCase):
    def test_all_formats_export_without_context_and_keep_the_source_unchanged(self):
        source = new_schematic()
        source.one('/Schematic/Components').append(new_symbol('Resistor', 'R1'))
        bind_schematic_references(source)
        binary = source.to_dch_bytes()
        loaded = parse_dch(binary)
        asc = loaded.to_asc_bytes()
        self.assertTrue(asc.startswith(b'(Source "DipTrace-Schematic"'))
        self.assertEqual(parse_asc(asc.decode('cp1252')).one('/Units').values, ('mm',))
        xml = parse_dchxml(loaded.to_dchxml_bytes())
        self.assertEqual(xml.one('/Source').scalar('Units'), 'mm')
        self.assertEqual(loaded.to_dch_bytes(), binary)
        self.assertFalse(loaded.root.changed)

    def test_stored_choices_take_precedence_and_context_overrides_only_the_view(self):
        source = new_schematic()
        settings = source.one('/Schematic/Settings')
        settings.set_field('UnitsMM', False)
        settings.set_field('UnitsMIL', True)
        settings.set_field('PartFontSize', 8)
        settings.set_field('GridSnap', False)
        xml = parse_dchxml(source.to_dchxml_bytes())
        self.assertEqual(xml.one('/Source').scalar('Units'), 'mil')
        self.assertEqual(xml.one('/Source/Schematic/Settings/Markings').scalar('FontSize'), 8)
        self.assertEqual(source.as_asc().one('/Units').values, ('mil',))
        style = MarkingStyle(font_size=9, font_width=3)
        xml = parse_dchxml(source.to_dchxml_bytes(context=DchXmlExportContext(units='mm', marking_style=style)))
        self.assertEqual(xml.one('/Source').scalar('Units'), 'mm')
        self.assertEqual(xml.one('/Source/Schematic/Settings/Markings').scalar('FontSize'), 9)
        binary = parse_dch(source.to_dch_bytes(context=AscExportContext(marking_style=style)))
        self.assertEqual(binary.one('/Schematic/Settings').scalar('PartFontSize'), 9)
        self.assertEqual(settings.scalar('PartFontSize'), 8)
        self.assertFalse(settings.scalar('UnitsMM'))
        self.assertTrue(settings.scalar('UnitsMIL'))

    def test_missing_appearance_uses_vector_size_two_and_default_units_are_mm(self):
        source = new_schematic()
        schematic = source.one('/Schematic')
        for name in ('PartFontVector', 'PartFontWidth', 'PartFontScale'):
            schematic.one(name).detach()
        source.one('/Schematic/Settings/PartFontSize').detach()
        for context in (AscExportContext(), DchXmlExportContext()):
            resolved = context.resolved(source)
            self.assertEqual(resolved.units, 'mm')
            self.assertEqual(resolved.marking_style.font_size, 2)
            self.assertTrue(resolved.marking_style.vector)
        self.assertIsNone(schematic.child('PartFontVector'))

    def test_system_font_settings_need_no_metrics_when_no_text_is_laid_out(self):
        source = new_schematic()
        style = MarkingStyle(vector=False, font_name='Arial', font_size=10)
        xml = parse_dchxml(source.to_dchxml_bytes(context=DchXmlExportContext(marking_style=style)))
        markings = xml.one('/Source/Schematic/Settings/Markings')
        self.assertFalse(markings.scalar('FontVector'))
        self.assertEqual(markings.scalar('FontName'), 'Arial')
        self.assertTrue(source.one('/Schematic').scalar('PartFontVector'))

    def test_unit_flags_supply_display_units_and_aliases_follow_the_destination(self):
        source = new_schematic()
        settings = source.one('/Schematic/Settings')
        settings.set_field('UnitsMM', False)
        settings.set_field('UnitsINCH', True)
        self.assertEqual(source.as_asc().one('/Units').values, ('in',))
        self.assertEqual(source.as_dchxml().one('/Source').scalar('Units'), 'inch')
        self.assertEqual(source.as_asc(context=AscExportContext(units='inch')).one('/Units').values, ('in',))
        self.assertEqual(source.as_dchxml(context=DchXmlExportContext(units='in')).one('/Source').scalar('Units'), 'inch')

    def test_optional_context_does_not_allow_an_incomplete_document_to_export(self):
        source = new_schematic()
        source.complete = False
        with self.assertRaises(IncompleteDocumentError):
            source.to_asc_bytes()
        with self.assertRaises(IncompleteDocumentError):
            source.to_dchxml_bytes()

    def test_edits_to_current_unit_settings_control_all_imported_designs(self):
        source = new_schematic()
        source.one('/Schematic/Settings').set_field('UnitsMM', False)
        source.one('/Schematic/Settings').set_field('UnitsMIL', True)
        for kind in ('dch', 'asc', 'dchxml'):
            current = parse(getattr(source, 'to_'+kind+'_bytes')(), format=kind)
            self.assertNotIn('display_units', current.metadata)
            self.assertNotIn('xml_units', current.metadata)
            settings = current.one('/Schematic/Settings')
            settings.set_field('UnitsMIL', False)
            settings.set_field('UnitsINCH', True)
            self.assertEqual(current.as_asc().one('/Units').values, ('in',))
            self.assertEqual(current.as_dchxml().one('/Source').scalar('Units'), 'inch')
            self.assertEqual(parse_dch(current.to_dch_bytes()).one('/Schematic/Settings/UnitsINCH').values, (True,))
            self.assertFalse(settings.scalar('UnitsMIL'))
            self.assertTrue(settings.scalar('UnitsINCH'))

    def test_asc_header_units_do_not_override_current_settings_or_rescale_geometry(self):
        from lib.schematic.model.objects import (new_schematic_shape)
        source = new_schematic()
        shape = source.one('/Schematic/Shapes').append(new_schematic_shape())
        shape.one('Points_New').add('pt', 3, 6)
        shape.one('Points_New').add('pt', 9, 12)
        bind_schematic_references(source)
        raw = source.as_asc()
        raw.one('/Units').set_values('mil')
        current = raw.as_schematic()
        self.assertEqual(current.as_asc().one('/Units').values, ('mm',))
        self.assertEqual([point.values for point in current.select('/Schematic/Shapes/Shape/Points_New/pt')], [(3, 6), (9, 12)])
        view = current.as_asc(context=AscExportContext(units='in'), report=ExportReport())
        self.assertEqual(view.one('/Units').values, ('in',))
        self.assertEqual(current.one('/Schematic/Settings/UnitsMM').values, (True,))


if __name__ == '__main__':
    unittest.main()
