"""Picture sources share the single-file and detached-projection conventions."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.model import Element
from lib.common.picture_sources import prepare_picture_sources
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.assembly.pictures import prepare_pictures
from lib.pcb.formats.dip.pictures import modernize_picture_sources
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_asc_graphics import fixture


def asc_source(*, bitmap=4, raster=73, filename='', variable=''):
    syntax = fixture()
    board = syntax.one('/Board')
    board.add('PictureCount', 5)
    shape = board.one('Shapes/Shape')
    shape.one('ShapeType').set_values(7)
    shape.one('BitmapIndex').set_values(bitmap)
    shape.one('RasterIndex').set_values(raster)
    shape.one('Picture_Raster').set_values('Y')
    shape.one('Picture_Width').set_values(12)
    shape.one('Picture_Height').set_values(9)
    shape.add('Picture_File', filename)
    shape.add('Picture_File_Variable', variable)
    return dumps(syntax, preserve=False)


@import_diagnostics('asc')
def read_asc(text):
    return assemble_graphics(prepare_core(text)).document


class PcbPictureSourceTests(unittest.TestCase):
    def test_raster_cache_is_consumed_while_filename_and_geometry_survive_without_file_reads(self):
        text = asc_source(filename='images/logo.png')
        report = ConversionReport()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('external image read')):
            document = read_asc(text, report=report)
        shape = document.one('/Board/Shapes/Shape')
        self.assertEqual((shape['Picture_File'], shape['BitmapIndex']), ('images/logo.png', -1))
        self.assertEqual((shape['PictureWidth'], shape['PictureHeight']), (12, 9))
        self.assertTrue(shape['PictureRaster'])
        self.assertIsNone(shape.child('RasterIndex'))
        self.assertIsNone(document.one('/Board').child('PictureCount'))
        self.assertEqual([point.values for point in shape.select('Points/pt')], [(1, 2), (3, 4)])
        self.assertTrue(any(notice.rule == 'picture-raster-cache' for notice in report.infos))
        self.assertFalse(any(notice.rule == 'unresolved-picture-reference' for notice in report.warnings))
        shape['Picture_File'] = 'images/replacement.png'
        copied = document.clone().one('/Board/Shapes/Shape')
        self.assertEqual(copied['Picture_File'], 'images/replacement.png')

    def test_unresolved_legacy_source_is_editable_and_warns_without_companion_discovery(self):
        report = ConversionReport()
        document = read_asc(asc_source(), report=report)
        shape = document.one('/Board/Shapes/Shape')
        self.assertEqual(shape['BitmapIndex'], 4)
        self.assertEqual(shape['Picture_File'], '')
        self.assertTrue(any(notice.rule == 'unresolved-picture-reference' for notice in report.warnings))
        shape['BitmapIndex'] = 7
        copy = document.clone()
        self.assertEqual(copy.one('/Board/Shapes/Shape')['BitmapIndex'], 7)
        shape['Picture_File'] = 'supplied.png'
        projected = document.clone().one('/Board/Shapes/Shape')
        prepare_picture_sources((projected,), destination='asc', keep_legacy_indices=True, report=ConversionReport())
        self.assertEqual(projected['BitmapIndex'], -1)

    def test_variable_filename_is_authoritative_and_unassigned_source_is_quiet(self):
        report = ConversionReport()
        document = read_asc(asc_source(variable='${PICTURES}/logo.png'), report=report)
        shape = document.one('/Board/Shapes/Shape')
        self.assertEqual((shape['Picture_File_Variable'], shape['BitmapIndex']), ('${PICTURES}/logo.png', -1))
        report.clear()
        empty = read_asc(asc_source(bitmap=-1, raster=-1), report=report)
        self.assertEqual(empty.one('/Board/Shapes/Shape')['BitmapIndex'], -1)
        self.assertFalse(any(notice.rule == 'unresolved-picture-reference' for notice in report.warnings))

    def test_shared_projection_retains_or_adapts_sources_only_on_detached_views(self):
        document = read_asc(asc_source(), report=ConversionReport())
        original = document.one('/Board/Shapes/Shape')
        for destination, keep, expected in (('asc', True, 4), ('dipxml', False, -1)):
            shape = document.clone().one('/Board/Shapes/Shape')
            report = ConversionReport()
            prepare_picture_sources((shape,), destination=destination, keep_legacy_indices=keep, report=report)
            self.assertEqual(shape['BitmapIndex'], expected)
            self.assertTrue(any(notice.rule == 'unresolved-picture-reference' for notice in report.warnings))
        resolved = document.clone().one('/Board/Shapes/Shape')
        prepare_picture_sources((resolved,), destination='dip', filenames=('', '', '', '', 'logo.png'), report=ConversionReport())
        self.assertEqual((resolved['Picture_File'], resolved['BitmapIndex']), ('logo.png', -1))
        self.assertEqual(original['BitmapIndex'], 4)

    def test_binary_legacy_reference_gate_is_separate_from_raster_cache(self):
        for version in (31, 46, 47, 49, 50, 62):
            with self.subTest(version=version):
                board = Element('Board')
                shape = board.add('Shapes').add('Shape')
                shape.add('Type', 7)
                shape.add('Picture_File', '')
                shape.add('Picture_File_Variable', '')
                shape.add('RasterIndex', 89)
                shape.add('PictureWidth', 12)
                decoded = SimpleNamespace(header=SimpleNamespace(version=version),
                    upgrades=SimpleNamespace(drawings=(SimpleNamespace(drawing=shape, bitmap_index=3),)))
                modernize_picture_sources(decoded)
                self.assertEqual(shape['BitmapIndex'], 3 if version < 47 else -1)
                prepare_pictures(board, (shape,))
                self.assertIsNone(shape.child('RasterIndex'))
                self.assertEqual(shape['PictureWidth'], 12)

    def test_malformed_counts_and_cache_values_remain_errors(self):
        for field, value in (('PictureCount', -1), ('RasterIndex', 'invalid')):
            syntax = fixture()
            board = syntax.one('/Board')
            if field == 'PictureCount':
                board.add(field, value)
            else:
                board.one('Shapes/Shape/'+field).set_values(value)
            with self.subTest(field=field), self.assertRaises(PcbError):
                read_asc(dumps(syntax, preserve=False), report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
