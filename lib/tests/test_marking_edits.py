"""Current label choices drive every output without an explicit cache refresh."""
import unittest
from unittest.mock import Mock, patch

from lib import AscExportContext, ExportReport, Index, new_schematic, parse
from lib.schematic.formats.export_view import (prepare_export)
from lib.schematic.layout.markings import (MarkingStyle)
from lib.schematic.model.objects import (new_symbol, new_symbol_shape)
from lib.schematic.model.refs import (bind_schematic_references)
from lib.schematic.layout.text_layout import (TextLayout)
from lib.common.text.vector import (TextMetrics)


PART = '/Schematic/Components/Part'


def source():
    document = new_schematic()
    part = document.one('/Schematic/Components').append(new_symbol('Buffer', 'U1'))
    part.set_field('Width', 10)
    part.set_field('Height', 6)
    part.set_field('Value', 'Old value')
    bind_schematic_references(document)
    return document


def label(document, kind=2):
    return next(shape for shape in document.select(PART+'/Shapes/Shape')
                if shape.scalar('MarkingGenerated') and shape.scalar('FontType') == kind)


def drawing_text(shape):
    return [line.values[0] for line in shape.select('TextLine/pt')]


class MarkingEditTests(unittest.TestCase):
    def test_default_layout_is_lazy_and_uses_the_optional_backend_only_for_system_fonts(self):
        current = source()
        metrics = Mock()
        metrics.measure.return_value = TextMetrics(100, 20)
        with patch('lib.schematic.layout.text_layout._system_metrics', return_value=metrics) as backend:
            current.to_dch_bytes()
            backend.assert_not_called()
            current.one('/Schematic').set_field('PartFontVector', False)
            current.one(PART).set_field('Width', 1)
            current.one(PART).set_field('Height', 10)
            current.to_dch_bytes()
            backend.assert_called()
            self.assertIn('U1', [call.args[0] for call in metrics.measure.call_args_list])

    def test_absent_calculated_cache_is_rebuilt_without_an_availability_flag(self):
        current = parse(source().to_dch_bytes(), format='dch')
        for shape in current.select(PART+'/Shapes/Shape'):
            if shape.scalar('MarkingGenerated'):
                shape.one('Points_New').detach()
                shape.one('TextLine').detach()
        for outgoing in ('dch', 'asc', 'dchxml'):
            data = getattr(current, 'to_'+outgoing+'_bytes')()
            view = prepare_export(parse(data, format=outgoing))
            self.assertEqual(drawing_text(label(view)), ['U1'])
        self.assertEqual(current.select(PART+'/Shapes/Shape/TextLine'), [])

    def test_edits_from_every_input_drive_every_output_and_leave_source_intact(self):
        original = source()
        for incoming in ('dch', 'asc', 'dchxml'):
            current = parse(getattr(original, 'to_'+incoming+'_bytes')(), format=incoming)
            part = current.one(PART)
            part.set_argument(1, 'U23')
            part.set_field('Value', 'Edited value')
            part.set_field('ShowRefDes', 1, 0, 8, -1, 1, 12, -9, 0)
            before = [(node.kind, node.values) for node in current.root.walk()]
            for outgoing in ('dch', 'asc', 'dchxml'):
                with self.subTest(incoming=incoming, outgoing=outgoing):
                    data = getattr(current, 'to_'+outgoing+'_bytes')()
                    loaded = parse(data, format=outgoing)
                    self.assertEqual(loaded.one(PART).values[1], 'U23')
                    self.assertEqual(loaded.one(PART).scalar('Value'), 'Edited value')
                    view = prepare_export(loaded)
                    self.assertEqual(drawing_text(label(view)), ['U23'])
                    self.assertEqual(label(view).one('Points_New/pt').values, (12, -9))
                    self.assertEqual(drawing_text(label(view, 3)), ['Edited value'])
                    self.assertEqual([(node.kind, node.values) for node in current.root.walk()], before)

    def test_stale_calculated_text_and_anchor_cannot_override_label_settings(self):
        current = parse(source().to_dch_bytes(), format='dch')
        cached = label(current)
        cached.one('TextLine/pt').set_values('Stale text')
        cached.one('Points_New/pt').set_values(123, 456)
        for outgoing in ('dch', 'asc'):
            loaded = parse(getattr(current, 'to_'+outgoing+'_bytes')(), format=outgoing)
            self.assertEqual(drawing_text(label(loaded)), ['U1'])
            self.assertNotEqual(label(loaded).one('Points_New/pt').values, (123, 456))
        self.assertEqual(drawing_text(cached), ['Stale text'])
        self.assertEqual(cached.one('Points_New/pt').values, (123, 456))

    def test_refresh_retains_authored_drawing_references(self):
        current = source()
        part = current.one(PART)
        shape = part.one('Shapes').append(new_symbol_shape())
        shape.one('Points_New').add('pt', 1, 2)
        field = part.add('DrawingSelection', 0)
        current.references.bind(part, shape, Index(field), role='drawing-selection')
        view = prepare_export(current)
        copied = view.one(PART+'/Shapes/Shape[1]')
        reference = view.references.outgoing(view.one(PART), role='drawing-selection')[0]
        self.assertIs(reference.target, copied)
        self.assertEqual(copied.one('Points_New/pt').values, (1, 2))
        self.assertEqual(shape.parent, part.one('Shapes'))

    def test_inactive_authored_content_is_not_reused_as_a_generated_slot(self):
        current = source()
        shape = current.one(PART+'/Shapes').append(new_symbol_shape())
        shape.set_field('Enabled', False)
        shape.set_field('Type', 0)
        shape.one('TextLine').add('pt', 'Saved note')
        view = prepare_export(current, compact_inactive=False)
        retained = view.one(PART+'/Shapes/Shape[1]')
        self.assertFalse(retained.scalar('Enabled'))
        self.assertEqual(drawing_text(retained), ['Saved note'])
        self.assertEqual(drawing_text(label(view)), ['U1'])

    def test_drawing_font_family_survives_regeneration_and_explicit_override_wins(self):
        current = parse(source().to_dch_bytes(), format='dch')
        label(current).set_field('FontName', 'Example Sans')
        current.one(PART).set_argument(1, 'U2')
        for outgoing in ('dch', 'asc'):
            loaded = parse(getattr(current, 'to_'+outgoing+'_bytes')(), format=outgoing)
            self.assertEqual(label(loaded).scalar('FontName'), 'Example Sans')
            context = AscExportContext(marking_style=MarkingStyle(font_name='Override Sans'))
            loaded = parse(getattr(current, 'to_'+outgoing+'_bytes')(context=context), format=outgoing)
            self.assertEqual(label(loaded).scalar('FontName'), 'Override Sans')

    def test_hidden_generated_label_can_reappear_with_its_appearance(self):
        current = parse(source().to_dch_bytes(), format='dch')
        label(current).set_field('FontColor', 123456)
        current.one(PART).set_field('ShowRefDes', 2, 0, 7, 0, 0, 0, 0, 0)
        hidden = parse(current.to_dch_bytes(), format='dch')
        self.assertFalse(label(hidden).scalar('Enabled'))
        hidden.one(PART).set_field('ShowRefDes', 1, 0, 7, 0, 0, 0, 0, 0)
        visible = parse(hidden.to_dch_bytes(), format='dch')
        self.assertTrue(label(visible).scalar('Enabled'))
        self.assertEqual(label(visible).scalar('Type'), 10)
        self.assertEqual(label(visible).scalar('FontColor'), 123456)

    def test_xml_uses_an_unambiguous_stored_label_family_without_context(self):
        for vector in (True, False):
            current = parse(source().to_dch_bytes(), format='dch')
            current.one('/Schematic').set_field('PartFontVector', vector)
            for shape in current.select(PART+'/Shapes/Shape'):
                if shape.scalar('MarkingGenerated'):
                    shape.set_field('FontName', 'Example Sans')
            before = [(node.kind, node.values) for node in current.root.walk()]
            report = ExportReport()
            loaded = parse(current.to_dchxml_bytes(report=report), format='dchxml')
            self.assertEqual(loaded.one('/Schematic/Settings').scalar('MarkingFontName'), 'Example Sans')
            self.assertEqual(loaded.one('/Schematic').scalar('PartFontVector'), vector)
            self.assertNotIn('generated-marking-attributes', {row.rule for row in report.warnings})
            context = AscExportContext(text_layout=TextLayout(lambda *args: TextMetrics(100, 20)))
            reloaded = parse(loaded.to_dch_bytes(context=context), format='dch')
            self.assertEqual(label(reloaded).scalar('FontName'), 'Example Sans')
            self.assertEqual([(node.kind, node.values) for node in current.root.walk()], before)

    def test_xml_reports_differing_label_families_and_an_explicit_override_resolves_them(self):
        current = parse(source().to_dch_bytes(), format='dch')
        for kind, family in ((2, 'First Sans'), (3, 'Second Sans')):
            label(current, kind).set_field('FontName', family)
        before = [(node.kind, node.values) for node in current.root.walk()]
        report = ExportReport()
        current.to_dchxml_bytes(report=report)
        omitted = [row for row in report.warnings if row.rule == 'generated-marking-attributes']
        self.assertEqual(len(omitted), 1)
        self.assertEqual(set(omitted[0].paths), {label(current, kind).one('FontName').path for kind in (2, 3)})
        from lib import DchXmlExportContext
        context = DchXmlExportContext(marking_style=MarkingStyle(font_name='Chosen Sans'))
        report = ExportReport()
        loaded = parse(current.to_dchxml_bytes(context=context, report=report), format='dchxml')
        self.assertEqual(loaded.one('/Schematic/Settings').scalar('MarkingFontName'), 'Chosen Sans')
        self.assertNotIn('generated-marking-attributes', {row.rule for row in report.warnings})
        self.assertEqual([(node.kind, node.values) for node in current.root.walk()], before)

    def test_xml_empty_system_family_uses_the_receiving_environment(self):
        for families in (('', ''), ('First Sans', 'Second Sans')):
            current = parse(source().to_dch_bytes(), format='dch')
            current.one('/Schematic').set_field('PartFontVector', False)
            for kind, family in zip((2, 3), families):
                label(current, kind).set_field('FontName', family)
            report = ExportReport()
            loaded = parse(current.to_dchxml_bytes(report=report), format='dchxml')
            self.assertFalse(loaded.one('/Schematic').scalar('PartFontVector'))
            self.assertEqual(loaded.one('/Schematic/Settings').scalar('MarkingFontName'), '')
            self.assertEqual('generated-marking-attributes' in {row.rule for row in report.warnings}, any(families))

    def test_omitted_inactive_labels_do_not_make_the_exported_family_ambiguous(self):
        current = parse(source().to_dch_bytes(), format='dch')
        for shape in current.select(PART+'/Shapes/Shape'):
            if shape.scalar('MarkingGenerated'):
                shape.set_field('FontName', 'Current Sans')
        hidden = label(current).clone()
        hidden.set_field('Enabled', False)
        hidden.set_field('FontName', 'Inactive Sans')
        current.one(PART+'/Shapes').append(hidden)
        loaded = parse(current.to_dchxml_bytes(report=ExportReport()), format='dchxml')
        self.assertEqual(loaded.one('/Schematic/Settings').scalar('MarkingFontName'), 'Current Sans')

    def test_xml_reports_an_unresolved_generated_label_group_key(self):
        current = parse(source().to_dch_bytes(), format='dch')
        key = label(current).add('UnresolvedKeys').add('Key', 'Group', 77)
        report = ExportReport()
        current.to_dchxml_bytes(report=report)
        omitted = [row for row in report.warnings if row.rule == 'generated-marking-attributes']
        self.assertEqual(len(omitted), 1)
        self.assertEqual(omitted[0].paths, (key.path,))
        self.assertEqual(key.values, ('Group', 77))

    def test_new_labels_inherit_an_existing_unambiguous_family_in_all_outputs(self):
        current = parse(source().to_dch_bytes(), format='dch')
        for shape in current.select(PART+'/Shapes/Shape'):
            if shape.scalar('MarkingGenerated'):
                shape.set_field('FontName', 'Current Sans')
        current.one(PART+'/UserFields').add('UserField', 'Added', 'New label', 0, 1, 7, 0, 0, 0, 0, 0)
        bind_schematic_references(current)
        for kind in ('dch', 'asc', 'dchxml'):
            loaded = parse(getattr(current, 'to_'+kind+'_bytes')(report=ExportReport()), format=kind)
            self.assertEqual(label(prepare_export(loaded), 20).scalar('FontName'), 'Current Sans')
        self.assertIsNone(current.one('/Schematic/Settings').child('MarkingFontName'))

    def test_empty_and_named_families_do_not_create_a_false_common_default(self):
        current = parse(source().to_dch_bytes(), format='dch')
        label(current).set_field('FontName', 'Current Sans')
        from lib.schematic.layout.markings import (resolve_marking_style)
        self.assertEqual(resolve_marking_style(current).font_name, '')
        for kind in ('dch', 'asc'):
            loaded = parse(getattr(current, 'to_'+kind+'_bytes')(report=ExportReport()), format=kind)
            self.assertEqual(label(loaded).scalar('FontName'), 'Current Sans')
            self.assertEqual(label(loaded, 3).scalar('FontName'), '')

    def test_global_family_without_labels_warns_only_in_destinations_that_omit_it(self):
        current = new_schematic()
        current.one('/Schematic/Settings').add('MarkingFontName', 'Saved Sans')
        for kind in ('dch', 'asc', 'dchxml'):
            report = ExportReport()
            loaded = parse(getattr(current, 'to_'+kind+'_bytes')(report=report), format=kind)
            self.assertEqual('global-marking-font' in {row.rule for row in report.warnings}, kind != 'dchxml')
            if kind == 'dchxml':
                self.assertEqual(loaded.one('/Schematic/Settings').scalar('MarkingFontName'), 'Saved Sans')
        self.assertEqual(current.one('/Schematic/Settings').scalar('MarkingFontName'), 'Saved Sans')

    def test_xml_reports_independent_label_attributes_without_mutating_them(self):
        current = parse(source().to_dch_bytes(), format='dch')
        values = dict(FontColor=123456, PenWidth=.25, LineSpacing=2.5,
                      TextAlign=1, Locked=True, Group=7)
        for name, value in values.items():
            label(current).set_field(name, value)
        before = [(node.kind, node.values) for node in current.root.walk()]
        for destination in ('dch', 'asc', 'dchxml'):
            report = ExportReport()
            output = getattr(current, 'to_'+destination+'_bytes')(report=report)
            notices = [row for row in report.warnings if row.rule == 'generated-marking-attributes']
            if destination == 'dchxml':
                self.assertEqual(len(notices), 1)
                self.assertEqual(len(notices[0].paths), len(values))
                self.assertTrue(parse(output, format=destination).complete)
            else:
                self.assertEqual(notices, [])
                loaded = parse(output, format=destination)
                self.assertEqual({name: label(loaded).scalar(name) for name in values}, values)
        self.assertEqual([(node.kind, node.values) for node in current.root.walk()], before)

    def test_matching_global_color_and_default_label_attributes_need_no_loss_notice(self):
        for use_color in (False, True):
            current = parse(source().to_dch_bytes(), format='dch')
            settings = current.one('/Schematic/Settings')
            settings.set_field('UsePartFontColor', use_color)
            settings.set_field('PartFontColor', 123456)
            for shape in current.select(PART+'/Shapes/Shape'):
                if shape.scalar('MarkingGenerated'):
                    shape.set_field('FontColor', 123456 if use_color else 0)
            report = ExportReport()
            loaded = parse(current.to_dchxml_bytes(report=report), format='dchxml')
            self.assertNotIn('generated-marking-attributes', {row.rule for row in report.warnings})
            self.assertEqual(label(prepare_export(loaded)).scalar('FontColor'), 123456 if use_color else 0)


if __name__ == '__main__':
    unittest.main()
