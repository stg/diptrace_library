"""PCB export fallbacks are optional, independent and never authored back."""
from dataclasses import replace
from decimal import Decimal
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats.export_context import ExportContext, resolve_export_context
from lib.pcb.formats.export_view import prepare_export
from lib.pcb.formats.dip.write import encode
from lib.pcb.model.objects import new_document
from lib.pcb.tests.test_dip_output import reopen, configured_document


class ExportContextTests(unittest.TestCase):
    def test_empty_document_writes_without_context_or_source_mutation(self):
        source = new_document()
        before, report = dumps(source, preserve=False), ConversionReport()
        data = encode(source, report=report)
        rebuilt = reopen(data, report=ConversionReport())
        board = rebuilt.one('/Board')
        self.assertEqual(rebuilt.root['Units'], 'mm')
        self.assertEqual(board['CompFontSize'], 2)
        self.assertEqual(board.one('Settings')['GridSize'], Decimal('.3'))
        self.assertEqual((board.one('SheetSettings')['SheetWidth'], board.one('SheetSettings')['SheetHeight']), (891, 630))
        self.assertEqual(len(board.select('SheetSettings/TitleBlocks/TitleBlock')), 6)
        self.assertEqual(board.select('Components/Component'), [])
        self.assertEqual(board.select('Nets/Net'), [])
        self.assertEqual(encode(rebuilt, report=ConversionReport()), data)
        self.assertIn('binary-output-defaults', [notice.rule for notice in report.infos])
        self.assertEqual(report.warnings, [])
        self.assertEqual(dumps(source, preserve=False), before)

    def test_stored_settings_win_while_context_customizes_missing_values(self):
        source = new_document()
        board = source.one('/Board')
        board['CompFontSize'] = Decimal('7.25')
        board.add('Settings')['GridSize'] = 2
        sheet = board.add('SheetSettings')
        sheet['SheetWidth'], sheet['SheetHeight'] = 900, 600
        context = ExportContext(font_size=3, vector_font=False, grid_size=1, line_width=Decimal('.6'), sheet_size=(400, 500))
        view, resolved = prepare_export(source, context=context, report=ConversionReport())
        current = view.one('/Board')
        self.assertEqual(current['CompFontSize'], Decimal('7.25'))
        self.assertEqual(current.one('Settings')['GridSize'], 2)
        self.assertEqual(current.one('Settings')['YGridSize'], 2)
        self.assertEqual(current.one('Settings')['SilkLineWidth'], Decimal('.6'))
        self.assertEqual((current.one('SheetSettings')['SheetWidth'], current.one('SheetSettings')['SheetHeight']), (900, 600))
        self.assertFalse(current['PatternFontVector'])
        self.assertIsNone(board.child('PatternFontVector'))
        self.assertIsNot(resolved, context)
        self.assertEqual(context.units, None)

    def test_display_and_project_overrides_are_explicit_and_detached(self):
        source = new_document()
        source.root['Units'] = 'mil'
        source.one('/Board')['ProjectDir'] = 'original/project'
        context = ExportContext(units='in', project_dir='export/project')
        rebuilt = reopen(encode(source, context=context, report=ConversionReport()), report=ConversionReport())
        self.assertEqual(rebuilt.root['Units'], 'inch')
        self.assertEqual(rebuilt.one('/Board')['ProjectDir'], 'export/project')
        self.assertEqual(source.root['Units'], 'mil')
        self.assertEqual(source.one('/Board')['ProjectDir'], 'original/project')
        resolved = ExportContext().resolved(source)
        self.assertEqual((resolved.units, resolved.project_dir), ('mil', 'original/project'))

    def test_missing_last_rules_copy_current_values_and_rebind_layer_identities(self):
        source = new_document()
        board = source.one('/Board')
        drc = board.add('DRC')
        drc['Name'], drc['AllLayers'], drc['CheckClearance'] = 'Current rules', False, True
        rows = drc.add('LayClearances')
        for index, layer in enumerate(board.select('Layers/Layer')):
            row = rows.add('LayClearance')
            row['Layer'], row['SameTraceToTrace'] = layer, Decimal('.3')*(index+1)
            row.add('ClearanceDetails')['TraceToVia'] = Decimal('.6')*(index+1)
        before = dumps(source, preserve=False)
        view, _ = prepare_export(source, report=ConversionReport())
        current, previous = view.one('/Board/DRC'), view.one('/Board/LastDRC')
        self.assertEqual(previous['Name'], 'Current rules')
        self.assertTrue(previous['CheckClearance'])
        for original, copy, layer in zip(current.select('LayClearances/LayClearance'),
                previous.select('LayClearances/LayClearance'), view.select('/Board/Layers/Layer')):
            self.assertIs(copy['Layer'], layer)
            self.assertIsNot(copy['Layer'], source.one('/Board/Layers/Layer[1]'))
            self.assertEqual(copy['SameTraceToTrace'], original['SameTraceToTrace'])
            self.assertEqual(copy.one('ClearanceDetails')['TraceToVia'], original.one('ClearanceDetails')['TraceToVia'])
        previous.one('LayClearances/LayClearance[1]')['SameTraceToTrace'] = 9
        self.assertEqual(current.one('LayClearances/LayClearance[1]')['SameTraceToTrace'], Decimal('.3'))
        self.assertIsNone(board.child('LastDRC'))
        self.assertEqual(dumps(source, preserve=False), before)
        view.references.validate()

    def test_supplied_last_rule_snapshot_is_kept_independent(self):
        source = new_document()
        board = source.one('/Board')
        board.add('DRC')['Name'] = 'Current'
        previous = board.add('LastDRC')
        previous['Name'], previous['CheckClearance'] = 'Previously used', True
        view, _ = prepare_export(source, report=ConversionReport())
        self.assertEqual(view.one('/Board/LastDRC')['Name'], 'Previously used')
        self.assertTrue(view.one('/Board/LastDRC')['CheckClearance'])

    def test_contexts_follow_dataclass_validation_and_replacement_conventions(self):
        context = resolve_export_context(None)
        changed = replace(context, grid_size=Decimal('1.5'))
        self.assertEqual(context.grid_size, Decimal('.3'))
        self.assertEqual(changed.grid_size, Decimal('1.5'))
        for options in ({'font_size':True}, {'grid_size':0}, {'line_width':-1},
                        {'sheet_size':(0, 1)}, {'units':'unsupported'}, {'vector_font':1}):
            with self.subTest(options=options), self.assertRaises((ValueError, TypeError)):
                ExportContext(**options)
        with self.assertRaises(TypeError):
            resolve_export_context({})

    def test_supplier_fallback_is_used_only_when_selection_is_absent(self):
        source = configured_document()
        component = source.one('/Board/Components/Component')
        self.assertIsNone(component.child('Suppliers'))
        context = ExportContext(default_main_supplier=True)
        rebuilt = reopen(encode(source, context=context, report=ConversionReport()), report=ConversionReport())
        self.assertTrue(rebuilt.one('/Board/Components/Component/Suppliers')['MainSupplier'])
        self.assertIsNone(component.child('Suppliers'))
        component.add('Suppliers')['MainSupplier'] = False
        rebuilt = reopen(encode(source, context=context, report=ConversionReport()), report=ConversionReport())
        self.assertFalse(rebuilt.one('/Board/Components/Component/Suppliers')['MainSupplier'])


if __name__ == '__main__':
    unittest.main()
