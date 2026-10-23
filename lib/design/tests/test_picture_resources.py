"""Picture import owns modernization; export resolves current resource facts."""
import unittest

from lib.design import AscExportContext, DchXmlExportContext, ExportReport, new_schematic, parse
from lib.design.pictures import upgrade_legacy_pictures
from lib.design.schematic_objects import new_schematic_shape
from lib.design.schematic_refs import bind_schematic_references


def sample():
    document = new_schematic()
    schematic = document.one('/Schematic')
    shape = schematic.one('Shapes').append(new_schematic_shape())
    shape.set_field('Type', 11)
    shape.set_field('BitmapIndex', 0)
    for point in ((1, 2), (8, 12)):
        shape.one('Points_New').add('pt', *point)
    upgrade_legacy_pictures(41, schematic)
    bind_schematic_references(document)
    return document, shape


class PictureResourceTests(unittest.TestCase):
    def test_import_leaves_only_current_geometry_and_the_unresolved_key(self):
        _, shape = sample()
        self.assertEqual(shape.scalar('Picture_Width'), 7)
        self.assertEqual(shape.scalar('Picture_Height'), 10)
        self.assertEqual(shape.one('Points_New/pt').values, (1, 2))
        self.assertEqual(shape.scalar('BitmapIndex'), 0)
        self.assertIsNone(shape.child('StoredData'))
        self.assertFalse(any(key.startswith('legacy_picture') for key in shape.annotations))

    def test_every_writer_resolves_on_a_detached_view_without_changing_geometry(self):
        document, shape = sample()
        for destination in ('dch', 'asc', 'dchxml'):
            with self.subTest(destination=destination):
                context_type = DchXmlExportContext if destination == 'dchxml' else AscExportContext
                context = context_type(legacy_picture_files=('photo.png',))
                data = getattr(document, 'to_'+destination+'_bytes')(context=context, report=ExportReport())
                loaded = parse(data, format=destination)
                picture = loaded.one('/Schematic/Shapes/Shape')
                self.assertEqual(picture.scalar('Picture_File'), 'photo.png')
                self.assertEqual(picture.one('Points_New/pt').values, (1, 2))
                self.assertEqual(picture.scalar('Picture_Width'), 7)
                self.assertEqual(picture.scalar('Picture_Height'), 10)
                self.assertEqual(shape.scalar('BitmapIndex'), 0)
                self.assertEqual(shape.scalar('Picture_File'), '')

    def test_explicit_edits_supply_current_resource_without_migration_history(self):
        document, shape = sample()
        shape.set_field('Picture_File', 'edited.png')
        shape.one('Points_New/pt').set_values(4, 5)
        loaded = parse(document.to_dch_bytes(), format='dch')
        picture = loaded.one('/Schematic/Shapes/Shape')
        self.assertEqual(picture.scalar('Picture_File'), 'edited.png')
        self.assertEqual(picture.one('Points_New/pt').values, (4, 5))
        self.assertEqual(shape.scalar('BitmapIndex'), 0)

    def test_variable_path_is_a_current_source_without_opening_external_files(self):
        document, shape = sample()
        shape.set_field('Picture_File_Variable', '%pictures%/photo.png')
        for destination in ('dch', 'asc', 'dchxml'):
            report = ExportReport()
            data = getattr(document, 'to_'+destination+'_bytes')(report=report)
            picture = parse(data, format=destination).one('/Schematic/Shapes/Shape')
            self.assertEqual(picture.scalar('BitmapIndex'), -1)
            self.assertEqual(picture.scalar('Picture_File_Variable'), '%pictures%/photo.png')
            self.assertFalse(any(notice.rule == 'unresolved-picture-reference' for notice in report.notices))
            self.assertEqual(shape.scalar('BitmapIndex'), 0)

    def test_asc_cycles_keep_the_unresolved_reference(self):
        document, _ = sample()
        for _ in range(3):
            report = ExportReport()
            document = parse(document.to_asc_bytes(report=report), format='asc')
            picture = document.one('/Schematic/Shapes/Shape')
            self.assertEqual(picture.scalar('BitmapIndex'), 0)
            self.assertEqual(picture.scalar('Picture_File'), '')
            self.assertEqual(len([notice for notice in report.warnings if notice.rule == 'unresolved-picture-reference']), 1)

    def test_unresolved_resource_warns_without_changing_the_authoring_reference(self):
        document, shape = sample()
        for destination in ('dch', 'asc', 'dchxml'):
            with self.subTest(destination=destination):
                report = ExportReport()
                data = getattr(document, 'to_'+destination+'_bytes')(report=report)
                warnings = [notice for notice in report.warnings if notice.rule == 'unresolved-picture-reference']
                self.assertEqual(len(warnings), 1)
                self.assertEqual(warnings[0].destination, destination)
                self.assertEqual(report.errors, [])
                loaded = parse(data, format=destination)
                picture = loaded.one('/Schematic/Shapes/Shape')
                self.assertEqual(picture.scalar('BitmapIndex'), 0 if destination == 'asc' else -1)
                self.assertEqual(picture.scalar('Picture_File'), '')
                self.assertEqual(picture.one('Points_New/pt').values, (1, 2))
                self.assertEqual(picture.scalar('Picture_Width'), 7)
                self.assertEqual(shape.scalar('BitmapIndex'), 0)
                self.assertEqual(shape.scalar('Picture_File'), '')

    def test_unassigned_picture_sources_are_quiet_and_invalid_indices_remain_errors(self):
        document, shape = sample()
        for destination in ('dch', 'asc', 'dchxml'):
            shape.set_field('BitmapIndex', -1)
            report = ExportReport()
            getattr(document, 'to_'+destination+'_bytes')(report=report)
            self.assertFalse(any(notice.rule == 'unresolved-picture-reference' for notice in report.notices))
            shape.set_field('BitmapIndex', True)
            report = ExportReport()
            with self.assertRaisesRegex(TypeError, 'BitmapIndex requires an integer'):
                getattr(document, 'to_'+destination+'_bytes')(report=report)
            self.assertEqual(len(report.errors), 1)


if __name__ == '__main__':
    unittest.main()
