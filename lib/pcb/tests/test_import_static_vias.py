"""Static-via imports resolve style-controlled geometry in every serialization."""
import unittest
from decimal import Decimal

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport, import_diagnostics, _set_import_format
from lib.common.structural_edits import assembly
from lib.pcb.formats import io
from lib.pcb.formats.dip.decode import decode
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.dipxml.read import prepare
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model.objects import new_layer, new_net
from lib.pcb.model import pad_records
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_xml_via_masks import via_document, configure, facts, COMPONENT, PAD


@import_diagnostics()
def conflicting_import(data, format, *, report=None, blind_layer=None):
    """Exercise source normalization before current-model constraints attach."""
    _set_import_format(format)
    source = {'dip': decode, 'asc': prepare_core, 'dipxml': prepare}[format](data)
    # XML initializes its own pad data. Binary/ASC prepared inputs may retain
    # older local geometry which disagrees with their current via style.
    if format != 'dipxml':
        pad = source.board.one('Components/Component/Pattern/Pads/Pad[2]')
        for name, value in dict(PadWidth_New=4, PadHeight_New=5, PadHole=2, PadHoleH=3,
                                SurfacePad=True, PadHoleType=1, PadShape_New=2,
                                PadAngle=Decimal('.75'), PadCorner=2, PadShape_X=1, PadShape_Y=-1).items():
            pad.set_field(name, value)
    if blind_layer is not None:
        pad = source.board.one('Components/Component/Pattern/Pads/Pad[2]')
        collection = pad.child('BlindLayer') or pad.add('BlindLayer')
        for row in tuple(collection.children('Item')):
            row.detach()
        collection.add('Item', blind_layer)
    return assemble_graphics(source).document


class StaticViaImportTests(unittest.TestCase):
    def reread(self, document, format):
        before = model_text(document, preserve=False)
        data = io.serialize(document, format=format, report=ConversionReport())
        self.assertEqual(model_text(document, preserve=False), before)
        report = ConversionReport()
        return io.parse(data, report=report), report

    def test_size_hole_shape_and_offsets_follow_the_style_without_losing_options(self):
        document = via_document()
        pad = document.one(PAD)
        configure(pad)
        options = facts(pad)
        net = document.one('/Board/Nets').append(new_net('Signal'))
        pad['Net'] = net
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                report = ConversionReport()
                data = io.serialize(document, format=format, report=ConversionReport())
                current = conflicting_import(data, format, report=report)
                pattern, actual = current.one(COMPONENT+'/Pattern'), current.one(PAD)
                style = current.one(COMPONENT)['Via']
                for name in ('PadWidth_New', 'PadHeight_New'):
                    self.assertEqual(actual[name], style['Size'])
                for name in ('PadHole', 'PadHoleH'):
                    self.assertEqual(actual[name], style['HoleSize'])
                for name in ('PadShape_New', 'PadHoleType', 'PadCorner', 'PadShape_X', 'PadShape_Y'):
                    self.assertEqual(actual[name], 0)
                self.assertEqual(actual['PadAngle'], 0 if format == 'dipxml' else Decimal('.75'))
                self.assertFalse(actual['SurfacePad'])
                for name in ('Width', 'Height', 'PadWidth', 'PadHeight'):
                    self.assertEqual(pattern[name], style['Size'])
                self.assertEqual(facts(actual), options)
                self.assertIs(actual['Net'], current.one('/Board/Nets/Net'))
                self.assertEqual(actual['Net']['Name'], 'Signal')
                self.assertTrue(any(notice.rule == 'static-via-style' and notice.severity == 'info'
                                    for notice in report.notices))
                current.references.validate()
                again, _ = self.reread(current, format)
                self.assertEqual(signature(again.one('/Board')), signature(current.one('/Board')))

    def test_blind_layers_come_from_the_selected_span(self):
        for bounded in (False, True):
            document = via_document()
            layers = document.one('/Board/Layers')
            for name in ('Inner 1', 'Inner 2'):
                layers.append(new_layer(name)).move_to(layers, len(layers.children())-2)
            stack = layers.children('Layer')
            if bounded:
                document.one(COMPONENT)['Via']['Span'] = (stack[1], stack[2])
            for format in ('dip', 'asc', 'dipxml'):
                with self.subTest(format=format, bounded=bounded):
                    report = ConversionReport()
                    data = io.serialize(document, format=format, report=ConversionReport())
                    current = conflicting_import(data, format, report=report, blind_layer=1)
                    actual = current.one(PAD)
                    expected = [0, 3] if bounded else []
                    self.assertEqual([row['Lay'] for row in actual.select('BlindLayer/Item')], expected)
                    self.assertTrue(any(notice.rule == 'static-via-style' for notice in report.infos))
                    current.references.validate()

    def test_standard_status_is_checked_after_style_geometry_is_installed(self):
        document = via_document()
        document.one(PAD)['Standard'] = True
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                data = io.serialize(document, format=format, report=ConversionReport())
                report = ConversionReport()
                rebuilt = conflicting_import(data, format, report=report)
                self.assertTrue(rebuilt.one(PAD)['Standard'])
                self.assertNotIn('pad-default-status', {notice.rule for notice in report.infos})
                rebuilt.validate()

    def test_unselected_styles_and_ordinary_pads_keep_individual_dimensions(self):
        for selected, kind in ((False, 16), (True, 14)):
            document = via_document()
            component, pad = document.one(COMPONENT), document.one(PAD)
            component.one('Pattern')['Type'] = kind
            if not selected:
                component['Via'] = None
            pad['PadWidth_New'], pad['PadHeight_New'] = 4, 5
            for format in ('dip', 'asc', 'dipxml'):
                with self.subTest(format=format, selected=selected, kind=kind):
                    current, report = self.reread(document, format)
                    expected = (None, None) if format == 'dipxml' and kind == 16 else (4, 5)
                    self.assertEqual((current.one(PAD)['PadWidth_New'], current.one(PAD)['PadHeight_New']), expected)
                    self.assertFalse(any(notice.rule == 'static-via-style' for notice in report.notices))

    def test_export_reports_receiver_changes_without_mutating_the_edited_model(self):
        document = via_document()
        pad = document.one(PAD)
        # Model setters reject this contradiction. Retain the diagnostic check
        # for internally assembled invalid content, outside authoring operations.
        with assembly(document):
            layers = pad.child('BlindLayer') or pad.add('BlindLayer')
            layers.bind_schema(pad_records.COLLECTIONS['BlindLayer'])
            row = layers.add('Item').bind_schema(pad_records.LAYER_MEMBER)
            document.references.bind(row, document.one('/Board/Layers/Layer[1]'),
                                     role='copper-layer', preserve=True)
        before = model_text(document, preserve=False)
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                report = ConversionReport()
                io.serialize(document, format=format, report=report)
                warnings = [notice for notice in report.warnings if notice.rule == 'static-via-style']
                self.assertEqual(len(warnings), 1)
                self.assertEqual(warnings[0].paths, (document.one(COMPONENT).path,))
                self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
