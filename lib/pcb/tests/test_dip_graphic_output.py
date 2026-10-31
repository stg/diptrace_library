"""Binary board sections project current geometry without routing or filling."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.font_codec import read_font_properties, write_font_properties
from lib.common.model import Element
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.dip.drawings import read_base_drawings, read_board_dimensions
from lib.pcb.formats.dip.modern import _board_drawings
from lib.pcb.formats.dip.pours import read_base_pours
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.sheet import read_groups
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.formats.dip.write_graphics import (write_base_drawings, write_groups,
    write_base_pours, write_board_dimensions, write_board_drawing_extensions,
    write_picture_sources, board_font_records)
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_graphic_projection import design, signature
from lib.pcb.tests.test_dimension_projection import syntax, design as dimension_design, dimension
from lib.pcb.tests.test_component_projection import signature as model_signature


def sections(document, *, report=None, legacy_picture_files=None):
    writer = Writer(report=report)
    board = document.one('/Board')
    writer.header()
    write_base_drawings(writer, board)
    write_groups(writer, board)
    write_base_pours(writer, board)
    write_board_dimensions(writer, board)
    write_board_drawing_extensions(writer, board)
    write_picture_sources(writer, board, legacy_picture_files=legacy_picture_files)
    for shape in board.select('Shapes/Shape'):
        writer.field(shape, 'PictureFlipped', 'boolean')
    write_font_properties(writer, board_font_records(board))
    return bytes(writer.buffer)


def read_sections(document, *, report=None, legacy_picture_files=None):
    data = sections(document, report=report, legacy_picture_files=legacy_picture_files)
    reader, board = Reader(data+b'\0'), Element('Board')
    drawings = read_base_drawings(reader, board)
    read_groups(reader, board)
    pours = read_base_pours(reader, board)
    read_board_dimensions(reader, board)
    _board_drawings(reader, board)
    for shape in board.select('Shapes/Shape'):
        for name, codec in (('PictureRaster','boolean'), ('Picture_File','text'),
                            ('RasterIndex','integer'), ('PictureTransparent','number')):
            reader.field(shape, name, codec)
    for shape in board.select('Shapes/Shape'):
        reader.field(shape, 'PictureFlipped', 'boolean')
    read_font_properties(reader, board_font_records(board))
    if reader.pos != len(data):
        raise AssertionError('board graphic section boundary differs')
    return board, drawings, pours, data


def reopen(document, *, report=None, legacy_picture_files=None):
    """Replace only these sections in a neutral electrical import context."""
    context = prepare_core(dumps(syntax(document, report=ConversionReport()), preserve=False))
    board, drawings, pours, _ = read_sections(document, report=report, legacy_picture_files=legacy_picture_files)
    for name in ('Shapes', 'Groups', 'CopperPours', 'Dimensions'):
        for previous in tuple(context.board.children(name)):
            previous.detach()
        board.one(name).move_to(context.board)
    context = replace(context, upgrades=replace(context.upgrades, drawings=drawings, pours=pours))
    return assemble_graphics(context).document


def rgb_view(document):
    expected = document.clone()
    for shape in expected.select('/Board/Shapes/Shape'):
        for name in ('Color', 'BrushColor', 'FontColor'):
            value = shape.get(name, 0)
            rgb = 0 if value < 0 or value >= 0x80000000 else value & 0xFFFFFF
            # This fixture imports against a black canvas, whose existing
            # contrast normalization replaces black drawing colors.
            shape[name] = 0xC0C0C0 if rgb == 0 else rgb
    return expected


class DipGraphicOutputTests(unittest.TestCase):
    def test_current_geometry_fill_text_and_indices_round_trip_without_source_changes(self):
        document = design()
        before, report = dumps(document, preserve=False), ConversionReport()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('picture read')):
            rebuilt = reopen(document, report=report)
        self.assertEqual(signature(rebuilt), signature(rgb_view(document)))
        self.assertEqual({notice.rule for notice in report.warnings}, {'color-rgb-range'})
        self.assertEqual(signature(reopen(rebuilt, report=ConversionReport())), signature(rebuilt))
        repeated = reopen(rebuilt, report=ConversionReport())
        self.assertEqual(sections(repeated, report=ConversionReport()), sections(rebuilt, report=ConversionReport()))
        self.assertEqual(dumps(document, preserve=False), before)
        document.references.validate()
        rebuilt.references.validate()

    def test_fill_absence_projects_only_on_export_and_known_empty_fill_stays_filled(self):
        for present in (True, False):
            for filled in (True, False):
                document = design()
                pour = document.one('/Board/CopperPours/CopperPour')
                pour['Poured'] = filled
                document.remove(pour.one('Fill'))
                if present:
                    pour.add('Fill')
                before, report = dumps(document, preserve=False), ConversionReport()
                board, _, upgrades, _ = read_sections(document, report=report)
                output = board.one('CopperPours/CopperPour')
                self.assertEqual(output['Poured'], filled and present)
                self.assertEqual(output.select('Fill/Lines/Line'), [])
                self.assertFalse(upgrades[0].regions_counted)
                self.assertEqual([notice.rule for notice in report.infos], [] if present else ['pour-fill-unavailable'])
                self.assertEqual(pour['Poured'], filled)
                self.assertEqual(pour.child('Fill') is not None, present)
                self.assertEqual(dumps(document, preserve=False), before)

    def test_classification_stays_available_when_one_primitive_is_unassigned(self):
        document = design()
        board, _, pours, _ = read_sections(document, report=ConversionReport())
        self.assertTrue(pours[0].regions_counted)
        self.assertEqual(board.one('CopperPours/CopperPour/Fill/SpokeLine/Line')['Width'], Decimal('.7'))
        line = document.one('/Board/CopperPours/CopperPour/Fill/Lines/Line')
        line['Region'] = None
        board, _, pours, _ = read_sections(document, report=ConversionReport())
        self.assertTrue(pours[0].regions_counted)
        self.assertEqual(board.one('CopperPours/CopperPour/Fill/Lines/Line')['Region'], -1)
        self.assertEqual(board.one('CopperPours/CopperPour/Fill/Polygons/Poly')['Region'], 4)
        self.assertEqual([row.values for row in board.select('CopperPours/CopperPour/Fill/Polygons/Poly/Points/pt')],
                         [(1, 2), (3, 4), (5, 2)])

    def test_area_quantization_has_a_bound_and_repeated_conversion_is_stable(self):
        document = design()
        pour = document.one('/Board/CopperPours/CopperPour')
        pour['MinimumArea'] = 2
        first = reopen(document, report=ConversionReport())
        area = first.one(pour.path)['MinimumArea']
        self.assertEqual(area, Decimal('1.99996164'))
        # A threshold rounded to 1e-4 has area error <= 2*sqrt(A)*5e-5 + (5e-5)^2.
        self.assertLess(abs(area-2), Decimal('.000142'))
        for _ in range(3):
            first = reopen(first, report=ConversionReport())
            self.assertEqual(first.one(pour.path)['MinimumArea'], area)
        self.assertEqual(pour['MinimumArea'], 2)
        pour['MinimumArea'] = -1
        with self.assertRaisesRegex(PcbError, 'area must not be negative'):
            sections(document, report=ConversionReport())

    def test_board_dimension_offsets_and_reordered_targets_match_asc_semantics(self):
        data = syntax(design())
        holes = data.one('/Board/Components/Component/Holes')
        hole = holes.add('Hole', 'Y', 'N', 2, 3, 4, 2, -1)
        hole.move_to(holes, 1)
        dimensions = data.one('/Board/Dimensions')
        dimension(dimensions, Connected1=1, Object1=0, SubObject1=1, Point1=1, Connected2=-1)
        dimension(dimensions, Connected1=2, Object1=0, SubObject1=1, Point1=0, Connected2=-1)
        document = assemble_graphics(prepare_core(dumps(data, preserve=False))).document
        current = document.select('/Board/Dimensions/Dimension')
        self.assertEqual([row['SubObject1'] for row in current], [0, 0])
        board, _, _, _ = read_sections(document, report=ConversionReport())
        self.assertEqual([row['SubObject1'] for row in board.select('Dimensions/Dimension')], [1, 1])
        rebuilt = reopen(document, report=ConversionReport())
        self.assertEqual(model_signature(rebuilt.one('/Board/Dimensions')), model_signature(document.one('/Board/Dimensions')))
        document.references.validate()

    def test_vector_pictures_full_fonts_and_continuous_angles_survive(self):
        document = dimension_design()
        image = document.one('/Board/Shapes/Shape[2]')
        image['PictureFlipped'] = True
        vector = image.add('PictureVector')
        vector['Width'], vector['Height'] = 12, 8
        points = vector.add('Polygons').add('Polygon').add('Points')
        for x, y in ((1, 2), (3, 4), (5, 2)):
            point = points.add('Item')
            point['X'], point['Y'] = x, y
        text = document.one('/Board/Shapes/Shape[1]')
        text['FontSize'], text['FontMono'], text['TextAngle'] = Decimal('1.125'), True, Decimal('17.25')
        rebuilt = reopen(document, report=ConversionReport())
        self.assertEqual(rebuilt.one(text.path)['TextAngle'], Decimal('17.25'))
        self.assertEqual(rebuilt.one(text.path)['FontSize'], Decimal('1.125'))
        self.assertTrue(rebuilt.one(text.path)['FontMono'])
        self.assertTrue(rebuilt.one(image.path)['PictureFlipped'])
        self.assertEqual(rebuilt.one(image.path+'/PictureVector/Polygons/Polygon/Points/Item[2]')['Y'], 4)

    def test_unresolved_picture_needs_an_explicit_path_mapping_and_never_reads_files(self):
        document = design()
        image = document.one('/Board/Shapes/Shape[2]')
        image['Picture_File'], image['BitmapIndex'] = '', 3
        before, report = dumps(document, preserve=False), ConversionReport()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('companion read')):
            rebuilt = reopen(document, report=report)
        self.assertEqual(rebuilt.one(image.path)['BitmapIndex'], -1)
        self.assertIn('unresolved-picture-reference', {notice.rule for notice in report.warnings})
        report.clear()
        rebuilt = reopen(document, report=report, legacy_picture_files=('', '', '', 'images/supplied.png'))
        self.assertEqual(rebuilt.one(image.path)['Picture_File'], 'images/supplied.png')
        self.assertNotIn('unresolved-picture-reference', {notice.rule for notice in report.warnings})
        self.assertEqual(dumps(document, preserve=False), before)

    def test_unknown_data_and_missing_required_layers_reject_without_source_edits(self):
        for target in ('unknown-shape', 'unassigned-pour-layer', 'unassigned-drawing-layer'):
            document = design()
            if target == 'unknown-shape':
                document.one('/Board/Shapes/Shape[1]').add('Unmapped', 10)
            elif target == 'unassigned-pour-layer':
                document.one('/Board/CopperPours/CopperPour')['Layer'] = None
            else:
                document.one('/Board/Shapes/Shape[2]')['LayerTarget'] = None
            before = dumps(document, preserve=False)
            with self.subTest(target=target), self.assertRaises(PcbError):
                sections(document, report=ConversionReport())
            self.assertEqual(dumps(document, preserve=False), before)

    def test_color_wire_projection_reports_upper_flags_without_changing_authored_values(self):
        for value, expected in ((-1, 0), (0x12345678, 0x345678), (0x80000002, 0)):
            document = design()
            image = document.one('/Board/Shapes/Shape[2]')
            image['Color'], image['BrushColor'], image['FontColor'] = value, 1, 2
            report = ConversionReport()
            board, _, _, _ = read_sections(document, report=report)
            self.assertEqual(board.one('Shapes/Shape[2]')['Color'], expected)
            self.assertEqual([notice.rule for notice in report.warnings], ['color-rgb-range'])
            self.assertEqual(image['Color'], value)


if __name__ == '__main__':
    unittest.main()
