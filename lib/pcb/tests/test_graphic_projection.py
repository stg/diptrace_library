"""Board geometry output preserves current data without layout calculations."""
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from lib.common.asc import dumps
from lib.common.asc_text import project_text
from lib.common.conversion import ConversionReport
from lib.common.schema import MISSING
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.graphic_projection import project_graphics, project_shape, project_pour
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_component_projection import design as component_design, project_input


def design():
    document = component_design()
    board = document.one('/Board')
    outline = board.add('Points')
    for point in ((0, 0, False), (20, 0, True), (20, 20, False)):
        outline.add('pt', *point)
    group = board.add('Groups').add('Group')
    group['Enabled'], group['X'], group['Y'] = True, 2, 3
    layer = board.add('NonSignals').add('NonSignal', 'Assembly notes')
    layer['Color'], layer['Side'] = 0x123456, 1
    shapes = board.add('Shapes')
    text = shapes.add('Shape')
    for name, value in dict(Enabled=True, Type=6, Layer=0, VectorFont=True, FontSize=1.25,
                            FontScale=1, FontWidth=-1, LineSpacing=1.2, FontName='Arial',
                            Color=0x123456, BrushColor=0x456789, FontColor=0x789ABC,
                            TextAngle=9.2, PenWidth=.6).items():
        text[name] = value
    text['Group'], text['Net'] = group, board.one('Nets/Net')
    text.add('TextLine').add('pt', 'First line').parent.add('pt', 'Second line')
    text.add('Points').add('pt', 1, 2).parent.add('pt', 3, 4)
    image = shapes.add('Shape')
    for name, value in dict(Enabled=True, Type=7, Layer=15, PictureRaster=True,
                            Picture_File='images/logo.png', PictureWidth=12, PictureHeight=9,
                            PictureProportions=True, PictureTransparent=128,
                            Color=-1, BrushColor=-1, FontColor=-1).items():
        image[name] = value
    image['LayerTarget'] = layer
    image.add('Points').add('pt', 5, 6).parent.add('pt', 17, 15)
    image.add('TextLine')
    pour = board.add('CopperPours').add('CopperPour')
    for name, value in dict(Enabled=True, Poured=True, MinimumArea=9, LineWidth=.9, Clearance=1.2).items():
        pour[name] = value
    pour['Layer'], pour['Net'], pour['Group'] = board.one('Layers/Layer[1]'), board.one('Nets/Net'), group
    points = pour.add('Points')
    for point in ((0, 0), (10, 0), (10, 10)):
        points.add('pt', *point)
    fill = pour.add('Fill')
    region = fill.add('Regions').add('Region', 4)
    for name in ('Lines', 'SpokeLine'):
        line = fill.add(name).add('Line')
        for field, value in dict(X1=1, Y1=2, X2=3, Y2=4, Region=region).items():
            line[field] = value
        if name == 'SpokeLine':
            line['Width'] = .7
    polygon = fill.add('Polygons').add('Poly')
    polygon['Region'] = region
    points = polygon.add('Points')
    for point in ((1, 2), (3, 4), (5, 2)):
        points.add('pt', *point)
    return document


def reopen(document, *, report=None, legacy_picture_files=None):
    syntax = project_input(document)
    target = syntax.one('/Board')
    generated = project_graphics(document.one('/Board'), report=report, legacy_picture_files=legacy_picture_files)
    for section in tuple(generated.children()):
        for previous in tuple(target.children(section.kind)):
            previous.detach()
        section.move_to(target)
    project_text(syntax, report=report)
    return assemble_graphics(prepare_core(dumps(syntax, preserve=False))).document


def signature(document):
    result = {}
    board = document.one('/Board')
    for name in ('Points', 'Groups', 'NonSignals', 'Shapes', 'CopperPours'):
        for node in board.one(name).walk(include_self=True):
            if node.schema is None:
                continue
            for field_name, field in node.schema.fields.items():
                value = node.get(field_name, None if field.default is MISSING else field.default)
                if field.kind == 'reference':
                    value = None if value is None else value.path
                elif field.kind == 'number' and value is not None:
                    value = Decimal(str(value))
                result[node.path+'/'+field_name] = value
    return result


class GraphicProjectionTests(unittest.TestCase):
    def test_drawings_outline_groups_custom_layers_and_fill_round_trip_without_mutation(self):
        document = design()
        before = signature(document)
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('external resource read')):
            rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt), before)
        self.assertEqual(signature(document), before)
        self.assertEqual(signature(reopen(rebuilt)), before)
        document.references.validate()
        rebuilt.references.validate()

    def test_reordering_layers_groups_shapes_and_fill_points_uses_current_indices(self):
        document = design()
        board = document.one('/Board')
        board.one('Layers/Layer[1]').move_to(board.one('Layers'))
        text = board.one('Shapes/Shape[1]')
        text.move_to(text.parent)
        point = board.one('CopperPours/CopperPour/Fill/Polygons/Poly/Points/pt[1]')
        point.move_to(point.parent)
        projected = project_graphics(board)
        self.assertEqual(projected.one('CopperPours/CopperPour')['Layer'], 1)
        self.assertEqual(projected.one('Shapes/Shape[2]')['OldNumber'], 1)
        self.assertEqual(projected.one('Groups/Group').values, (0, 2, 3, 'Y', 'N', 'N'))
        self.assertEqual(signature(reopen(document)), signature(document))

    def test_text_keeps_full_radian_angle_and_fractional_size_without_layout_context(self):
        text = design().one('/Board/Shapes/Shape[1]')
        output = project_shape(text)
        self.assertEqual((output['TextAngle'], output['FontSize'], output['Orientation']), (Decimal('9.2'), Decimal('1.25'), 6))
        self.assertEqual(output['Name'], 'First line')
        self.assertEqual([node.values for node in output.select('TextLines/TextLine')], [('First line',), ('Second line',)])

    def test_missing_fill_and_known_empty_fill_remain_distinct_from_the_filled_choice(self):
        for filled in (True, False):
            for present in (True, False):
                with self.subTest(filled=filled, present=present):
                    document = design()
                    pour = document.one('/Board/CopperPours/CopperPour')
                    pour['Poured'] = filled
                    document.remove(pour.one('Fill'))
                    if present:
                        pour.add('Fill')
                    output = project_pour(pour)
                    self.assertEqual(output['Poured'], 'Y' if filled else 'N')
                    self.assertEqual(output.child('Lines') is not None, present)
                    rebuilt = reopen(document).one('/Board/CopperPours/CopperPour')
                    self.assertEqual(rebuilt['Poured'], filled)
                    self.assertEqual(rebuilt.child('Fill') is not None, present)
                    self.assertEqual(pour.child('Fill') is not None, present)

    def test_area_projection_is_bounded_and_repeated_output_does_not_accumulate_error(self):
        document = design()
        pour = document.one('/Board/CopperPours/CopperPour')
        pour['MinimumArea'] = 2
        rebuilt = reopen(document)
        first = rebuilt.one(pour.path)['MinimumArea']
        self.assertLess(abs(first-2), Decimal('1e-32'))
        for _ in range(5):
            rebuilt = reopen(rebuilt)
            self.assertEqual(rebuilt.one(pour.path)['MinimumArea'], first)
        self.assertEqual(pour['MinimumArea'], 2)
        pour['MinimumArea'] = -1
        with self.assertRaisesRegex(PcbError, 'area must not be negative'):
            project_pour(pour)

    def test_hatch_lines_cannot_acquire_a_spoke_only_width(self):
        pour = design().one('/Board/CopperPours/CopperPour')
        line = pour.one('Fill/Lines/Line')
        spoke = pour.one('Fill/SpokeLine/Line')
        with self.assertRaises(KeyError):
            line['Width'] = .3
        spoke['Width'] = .25
        self.assertEqual(project_pour(pour).one('SpokeLine/pt').values[-2:], (Decimal('.25'), 4))

    def test_vector_picture_geometry_is_owned_editable_data(self):
        document = design()
        image = document.one('/Board/Shapes/Shape[2]')
        vector = image.add('PictureVector')
        vector['Width'], vector['Height'] = 12, 8
        points = vector.add('Polygons').add('Polygon').add('Points')
        for x, y in ((1, 2), (3, 4), (5, 2)):
            point = points.add('Item')
            point['X'], point['Y'] = x, y
        self.assertEqual(signature(reopen(document)), signature(document))
        points.children()[0]['Y'] = 7
        self.assertEqual(reopen(document).one(image.path+'/PictureVector/Polygons/Polygon/Points/Item[1]')['Y'], 7)

    def test_picture_references_are_resolved_only_by_explicit_context_and_keep_sources_unchanged(self):
        document = design()
        image = document.one('/Board/Shapes/Shape[2]')
        image['Picture_File'], image['BitmapIndex'] = '', 3
        report = ConversionReport()
        rebuilt = reopen(document, report=report)
        self.assertEqual(rebuilt.one(image.path)['BitmapIndex'], 3)
        self.assertIn('unresolved-picture-reference', {notice.rule for notice in report.warnings})
        report.clear()
        rebuilt = reopen(document, report=report, legacy_picture_files=('', '', '', 'images/supplied.png'))
        self.assertEqual(rebuilt.one(image.path)['Picture_File'], 'images/supplied.png')
        self.assertEqual((image['Picture_File'], image['BitmapIndex']), ('', 3))

    def test_known_omissions_warn_but_unknown_content_and_unassigned_active_layers_fail(self):
        document = design()
        text = document.one('/Board/Shapes/Shape[1]')
        pour = document.one('/Board/CopperPours/CopperPour')
        text['FontMono'], text['PictureFlipped'], text['ShieldGroup'] = True, True, 0
        pour['RatlineMode'], pour['ShieldGroup'], pour['TraceShieldGroup'] = 2, 0, 3
        report = ConversionReport()
        reopen(document, report=report)
        self.assertEqual({notice.rule for notice in report.warnings}, {'board-drawing-options', 'copper-pour-options'})
        self.assertEqual((pour['RatlineMode'], text['ShieldGroup']), (2, 0))
        pour['Layer'] = None
        with self.assertRaisesRegex(PcbError, 'select a copper layer'):
            project_pour(pour)
        text.add('Unmapped', 1)
        with self.assertRaisesRegex(PcbError, 'no PCB ASC projection'):
            project_shape(text)


if __name__ == '__main__':
    unittest.main()
