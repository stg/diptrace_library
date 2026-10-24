"""Common choices are reusable; unsupported explicit destination options fail."""
from dataclasses import replace
import unittest

from lib import (AscExportContext, ConversionReport, DchExportContext,
                        DchXmlExportContext, ExportContext, new_schematic, parse, serialize)


class ExportContextTests(unittest.TestCase):
    def test_common_overrides_apply_to_every_destination_without_changing_design(self):
        doc = new_schematic()
        context = ExportContext(units='in', use_part_font_color=False)
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                restored = parse(serialize(doc, format=format, context=context, report=ConversionReport()),
                                 format=format, report=ConversionReport())
                settings = restored.one('/Schematic/Settings')
                self.assertTrue(settings['UnitsINCH'])
                self.assertFalse(settings['UsePartFontColor'])
        self.assertTrue(doc.one('/Schematic/Settings').scalar('UnitsMM'))
        self.assertTrue(doc.one('/Schematic/Settings').scalar('GridSnap'))
        self.assertTrue(doc.one('/Schematic/Settings').scalar('UsePartFontColor'))

    def test_grid_override_is_carried_by_text_formats_and_rejected_for_binary(self):
        context = ExportContext(grid_snap=False)
        for format in ('asc', 'dchxml'):
            current = parse(serialize(new_schematic(), format=format, context=context), format=format)
            self.assertFalse(current.one('/Schematic/Settings')['GridSnap'])
        with self.assertRaisesRegex(ValueError, 'grid_snap is not stored'):
            serialize(new_schematic(), format='dch', context=context)

    def test_default_resolution_and_customization_are_independent(self):
        doc = new_schematic()
        defaults = ExportContext()
        resolved = defaults.resolved(doc)
        custom = replace(resolved, marking_style=replace(resolved.marking_style, font_size=9))
        self.assertEqual(custom.marking_style.font_size, 9)
        self.assertEqual(resolved.marking_style.font_size, 6)
        self.assertIsNone(defaults.marking_style)
        self.assertIsNone(defaults.units)
        self.assertFalse(DchExportContext().resolved(doc).compact_inactive)
        self.assertTrue(AscExportContext().resolved(doc).compact_inactive)
        serialize(doc, format='dch', context=DchExportContext().resolved(doc))

    def test_common_defaults_can_be_resolved_for_the_destination_before_customizing(self):
        doc = new_schematic()
        classes = {'dch': DchExportContext, 'asc': AscExportContext, 'dchxml': DchXmlExportContext}
        for format, expected in classes.items():
            with self.subTest(format=format):
                context = ExportContext().resolved(doc, format=format)
                self.assertIsInstance(context, expected)
                serialize(doc, format=format, context=replace(context, units='mm'), report=ConversionReport())
        with self.assertRaisesRegex(ValueError, 'unsupported schematic output format'):
            ExportContext().resolved(doc, format='pcb')

    def test_explicit_options_unsupported_by_destination_are_not_silently_ignored(self):
        for context, format, name in (
                (AscExportContext(encoding='utf-8'), 'dch', 'encoding'),
                (DchXmlExportContext(active_sheet=1), 'asc', 'active_sheet'),
                (AscExportContext(compact_inactive=False), 'dchxml', 'compact_inactive')):
            report = ConversionReport()
            with self.subTest(format=format), self.assertRaisesRegex(ValueError, name):
                serialize(new_schematic(), format=format, context=context, report=report)
            self.assertEqual(len(report.errors), 1)

    def test_compatible_previous_asc_context_remains_accepted_for_binary_output(self):
        doc = new_schematic()
        previous = AscExportContext(units='mil', compact_inactive=False)
        data = serialize(doc, format='dch', context=previous)
        current = parse(data, format='dch')
        self.assertTrue(current.one('/Schematic/Settings')['UnitsMIL'])

    def test_invalid_common_types_are_rejected_at_construction(self):
        for options in ({'grid_snap': 0}, {'use_part_font_color': 1}, {'text_layout': None},
                        {'project_dir': 3}, {'units': 'metres'}):
            with self.subTest(options=options), self.assertRaises((TypeError, ValueError)):
                ExportContext(**options)
