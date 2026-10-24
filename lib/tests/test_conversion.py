"""Export diagnostics separate cached state from loss; the source keeps both."""
from pathlib import Path
import sys
import unittest
import warnings

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lib import (new_schematic, parse_dch, parse_dchxml, ExportReport,
                             ConversionWarning, AscExportContext, DchXmlExportContext)
from lib.schematic.layout.markings import (MarkingStyle)
from lib.schematic.model.objects import (new_symbol, new_pin, new_pattern)
from lib.schematic.model.refs import (bind_schematic_references)


class ConversionTests(unittest.TestCase):
    def test_absent_old_supplier_preference_uses_an_optional_export_default(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Power', 'U1'))
        supplier = part.one('Suppliers')
        supplier.set_field('Supplier', 'Example distributor')
        supplier.set_field('SourceLocator', 'merchant:item-42')
        supplier.one('MainSupplier').detach()
        source.metadata['source_version'] = 43
        bind_schematic_references(source)
        for default in (False, True):
            context = AscExportContext(default_main_supplier=default)
            for destination in ('asc', 'dch'):
                with self.subTest(default=default, destination=destination):
                    report = ExportReport()
                    output = (source.as_asc(context=context, report=report).as_schematic()
                              if destination == 'asc' else
                              parse_dch(source.to_dch_bytes(context=context, report=report)))
                    restored = output.one('/Schematic/Components/Part/Suppliers')
                    self.assertIs(restored.scalar('MainSupplier'), default)
                    self.assertEqual(restored.scalar('Supplier'), 'Example distributor')
                    notices = [item for item in report.infos if item.rule == 'supplier-preference-default']
                    self.assertEqual(len(notices), 1)
                    self.assertEqual(len(notices[0].paths), 1)
                    self.assertEqual(report.errors, [])
                    self.assertIsNone(supplier.child('MainSupplier'))
                    self.assertEqual(supplier.scalar('SourceLocator'), 'merchant:item-42')
        supplier.add('MainSupplier', True)
        report = ExportReport()
        output = source.as_asc(context=AscExportContext(default_main_supplier=False), report=report)
        self.assertTrue(output.as_schematic().one('/Schematic/Components/Part/Suppliers').scalar('MainSupplier'))
        self.assertNotIn('supplier-preference-default', {item.rule for item in report.notices})
        with self.assertRaisesRegex(TypeError, 'default_main_supplier'):
            AscExportContext(default_main_supplier=1)

    def test_supplier_omissions_report_saved_values_without_changing_them(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Power', 'U1'))
        supplier = part.one('Suppliers')
        supplier.set_field('SourceLocator', 'merchant:item-42')
        supplier.set_field('MainSupplier', True)
        supplier.one('Prices').add('Quote', 10, 1.25)
        supplier.one('Prices').add('Quote', 100, 1.0)
        bind_schematic_references(source)
        original = source.to_dch_bytes()
        for destination, export in (('asc', source.as_asc), ('dchxml', source.as_dchxml)):
            report = ExportReport()
            output = export(report=report)
            rules = {notice.rule: notice for notice in report.warnings}
            self.assertIn('supplier-source-locator', rules)
            self.assertEqual(len(rules['supplier-quotes'].paths), 2)
            self.assertNotIn('supplier-preference', rules)
            self.assertEqual(any(notice.rule == 'supplier-preference' for notice in report.infos),
                             destination == 'dchxml')
            self.assertEqual(report.errors, [])
            if destination == 'asc':
                self.assertTrue(output.as_schematic().one('/Schematic/Components/Part/Suppliers').scalar('MainSupplier'))
        self.assertEqual(supplier.scalar('SourceLocator'), 'merchant:item-42')
        self.assertEqual([row.values for row in supplier.select('Prices/Quote')], [(10, 1.25), (100, 1)])
        self.assertEqual(source.to_dch_bytes(), original)

    def test_omitting_cached_main_supplier_match_is_quiet(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Power', 'U1'))
        supplier = part.one('Suppliers')
        supplier.set_field('Supplier', 'Example distributor')
        supplier.set_field('MainSupplier', True)
        bind_schematic_references(source)
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter('always')
            public = source.as_dchxml()
        self.assertEqual(emitted, [])
        restored = public.as_schematic().one('/Schematic/Components/Part/Suppliers')
        self.assertEqual(restored.scalar('Supplier'), 'Example distributor')
        self.assertTrue(supplier.scalar('MainSupplier'))
        self.assertFalse(restored.scalar('MainSupplier'))

    def test_title_grid_data_survives_xml_without_a_selected_name(self):
        source = new_schematic()
        grid = source.one('/Schematic/Pages/Page/TitleBlocks/TitleBlock[1]')
        grid.set_field('Width', 30)
        grid.set_field('Height', 15)
        grid.one('ColWidths').add('pt', 30)
        grid.one('RowHeights').add('pt', 15)
        content = grid.one('Contents').add('Content', 0)
        for name, value in dict(FOrientation=False, FontSize=9, FontType=0, Align=0,
                FontColor=0, Text='Board revision', FontName='', VectorFont=True,
                FontWidth=-1, FontScale=1, LineSpacing=1.2).items():
            content.add(name, value)
        content.add('Placement', 0, 0, 30, 15)
        grid.one('Cells').add('Cell', 0, 0, 0).add('Edges', True, True, True, True)
        bind_schematic_references(source)
        for _ in range(3):
            report = ExportReport()
            xml = source.as_dchxml(report=report)
            public = xml.one('/Source/Schematic/SheetSettings/Sheets/Sheet/BottomRightBlock')
            self.assertEqual(public.one('Name').values, ())
            source = xml.as_schematic()
            restored = source.one('/Schematic/Pages/Page/TitleBlocks/TitleBlock[1]')
            self.assertEqual(restored.values, (0, ''))
            self.assertEqual(restored.one('Contents/Content').scalar('Text'), 'Board revision')
            self.assertEqual(report.warnings, [])
        report = ExportReport()
        source.as_asc(report=report)
        notice = next(notice for notice in report.warnings if notice.rule == 'page-title-blocks')
        self.assertEqual(notice.paths, (restored.path,))
        self.assertEqual(restored.one('Contents/Content').scalar('Text'), 'Board revision')
        report = ExportReport()
        new_schematic().as_asc(report=report)
        self.assertNotIn('page-title-blocks', {notice.rule for notice in report.notices})

    def source(self):
        document = new_schematic()
        slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
        slot.add('VariablePath', '')
        definition = slot.add('Definition', 0)
        part = definition.append(new_symbol('Symbol', 'X', placed=False))
        part.set_field('Datasheet', 'https://example.test/symbol.pdf')
        pin = part.one('Pins').append(new_pin(placed=False))
        pin.set_field('SignalDelay', 7)
        pattern = definition.append(new_pattern())
        pattern.set_field('Datasheet', 'https://example.test/footprint.pdf')
        pattern.set_field('RefDes', 'CUSTOM')
        pattern.set_field('Sided', True)
        unused = document.one('/Schematic/CacheLib').add('Patterns').append(new_pattern('Unused'))
        bind_schematic_references(document)
        return document, part, pin, pattern, unused

    def test_known_omissions_are_structured_and_leave_source_facts_intact(self):
        document, part, pin, pattern, unused = self.source()
        report = ExportReport()
        binary = parse_dch(document.to_dch_bytes(report=report))
        self.assertTrue(binary.complete)
        expected = {'standalone-library-resources', 'cached-symbol-datasheet', 'cached-pin-delay',
                    'footprint-datasheet', 'footprint-reference-prefix', 'default-pad-side'}
        self.assertTrue(expected.issubset({warning.rule for warning in report.warnings}))
        self.assertTrue(all(warning.destination == 'dch' and warning.paths for warning in report.warnings))
        self.assertEqual(pin.scalar('SignalDelay'), 7)
        self.assertEqual(pattern.scalar('RefDes'), 'CUSTOM')
        self.assertEqual(part.scalar('Datasheet'), 'https://example.test/symbol.pdf')
        self.assertIsNotNone(unused.parent)
        style = MarkingStyle(font_name='Arial')
        xml = parse_dchxml(document.to_dchxml_bytes(context=DchXmlExportContext(units='mm', grid_snap=True, marking_style=style)))
        symbol = xml.one('/Source/Library/Components/Component/Part')
        self.assertEqual(symbol.scalar('Datasheet'), part.scalar('Datasheet'))
        self.assertEqual(symbol.one('Pins/Pin').scalar('SignalDelay'), 7)
        self.assertTrue(xml.select('/Source/Library/Library/Patterns/Pattern[Name="Unused"]'))
        asc_report = ExportReport()
        asc = document.as_asc(context=AscExportContext(units='mm', project_dir='', grid_snap=True, marking_style=style), report=asc_report)
        self.assertTrue(asc.complete)
        self.assertTrue((expected-{'footprint-datasheet'}).issubset({warning.rule for warning in asc_report.warnings}))
        self.assertNotIn('footprint-datasheet', {warning.rule for warning in asc_report.warnings})
        imported = asc.as_schematic()
        self.assertEqual(imported.one('/Schematic/CacheLib/Slots/Slot/Definition/Pattern').scalar('Datasheet'),
                         'https://example.test/footprint.pdf')

    def test_default_warning_is_observable_and_unknown_fields_still_fail(self):
        document, part, pin, pattern, unused = self.source()
        with self.assertWarns(ConversionWarning) as captured:
            document.to_dch_bytes()
        self.assertEqual(captured.warning.notice.destination, 'dch')
        part.add('UnknownFutureFact', 'truth')
        report = ExportReport()
        with self.assertRaisesRegex(ValueError, 'unsupported schematic field'):
            document.to_dch_bytes(report=report)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.errors[0].destination, 'dch')
        self.assertIn('UnknownFutureFact', report.errors[0].message)

    def test_routine_schema_selection_is_quiet_and_can_be_collected(self):
        source = parse_dch(new_schematic().to_dch_bytes(version=48))
        for destination, export in (('dch', source.to_dch_bytes), ('dchxml', source.as_dchxml)):
            with self.subTest(destination=destination):
                with warnings.catch_warnings(record=True) as emitted:
                    warnings.simplefilter('always')
                    export(version=46)
                self.assertEqual(emitted, [])
                report = ExportReport()
                export(version=46, report=report)
                self.assertEqual([notice.rule for notice in report.infos], ['schema-version'])
                self.assertEqual(report.warnings, [])
                self.assertEqual(report.errors, [])
                self.assertEqual(report.notices[0].severity, 'info')
        self.assertEqual(source.metadata['source_version'], 48)

    def test_failed_exports_collect_errors_and_preserve_the_exception(self):
        source = new_schematic()
        source.one('/Schematic/Settings').add('UnknownFutureFact', 'truth')
        for destination, export in (('dch', source.to_dch_bytes), ('asc', source.as_asc), ('dchxml', source.as_dchxml)):
            with self.subTest(destination=destination):
                report = ExportReport()
                with self.assertRaisesRegex(ValueError, 'UnknownFutureFact') as captured:
                    export(report=report)
                self.assertEqual(len(report.errors), 1)
                self.assertEqual(report.errors[0].message, str(captured.exception))
                self.assertEqual(report.errors[0].destination, destination)
                self.assertEqual(report.notices[-1].severity, 'error')
        self.assertEqual(source.one('/Schematic/Settings').scalar('UnknownFutureFact'), 'truth')

    def test_text_substitutions_are_reported_only_for_exported_fields(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Power', 'U1'))
        part.set_field('Value', '\u03a9 "power"\n')
        bind_schematic_references(source)
        report = ExportReport()
        output = source.as_asc(report=report)
        self.assertEqual(output.one('/Schematic/Components/Part').scalar('Value'), 'O !power!!')
        rules = {notice.rule: notice for notice in report.warnings}
        self.assertIn('asc-text-encoding', rules)
        self.assertIn('asc-text-sanitization', rules)
        self.assertIn(output.one('/Schematic/Components/Part/Value').path, rules['asc-text-encoding'].paths)
        self.assertEqual(part.scalar('Value'), '\u03a9 "power"\n')
        self.assertEqual(output.to_asc_bytes(), source.to_asc_bytes(report=ExportReport()))

        source, cached, *_ = self.source()
        cached.set_field('Datasheet', '\u03a9 "hidden"\n')
        report = ExportReport()
        source.as_asc(report=report)
        self.assertNotIn('asc-text-encoding', {notice.rule for notice in report.notices})
        self.assertNotIn('asc-text-sanitization', {notice.rule for notice in report.notices})

    def test_serialization_errors_join_the_report_without_duplicate_failures(self):
        source = new_schematic()
        source.one('/Schematic/ProjectDir').set_values('invalid\x00xml')
        report = ExportReport()
        with self.assertRaisesRegex(ValueError, 'XML'):
            source.to_dchxml_bytes(report=report)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.errors[0].destination, 'dchxml')

    def test_unimplemented_layout_service_is_an_error_in_the_report(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Power', 'U1'))
        part.set_field('ShowRefDes', 1, 0, 7, 0, 0, 0, 0, 0)
        part.set_field('Width', 1)
        part.set_field('Height', 10)
        bind_schematic_references(source)
        report = ExportReport()
        from lib.schematic.layout.text_layout import (TextLayout)
        context = AscExportContext(marking_style=MarkingStyle(vector=False, font_name='System Font'),
                                   text_layout=TextLayout())
        with self.assertRaisesRegex(NotImplementedError, 'system font measurements') as captured:
            source.as_asc(context=context, report=report)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.errors[0].message, str(captured.exception))
        self.assertEqual(report.errors[0].destination, 'asc')

    def test_missing_required_records_join_the_error_report(self):
        source = new_schematic()
        from lib.common.structural_edits import assembly
        with assembly(source):  # Deliberately construct invalid input for the export boundary.
            source.one('/Scale').detach()
        report = ExportReport()
        with self.assertRaises(LookupError) as captured:
            source.to_dch_bytes(report=report)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.errors[0].message, str(captured.exception))
        self.assertEqual(report.errors[0].destination, 'dch')


if __name__ == '__main__':
    unittest.main()
