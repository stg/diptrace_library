"""Earlier supported binary layouts load complete current editable properties."""
import unittest

from lib import AscExportContext, ExportReport, new_schematic, parse, parse_dch
from lib.schematic.formats.dch.binary import (read_header)
from lib.schematic.model.objects import (new_symbol)
from lib.schematic.model.refs import (bind_schematic_references)


def older_input(version):
    source = new_schematic()
    part = source.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
    part.set_field('LibPath', 'library.eli')
    part.one('Pattern/Model3D').set_field('Model3DFile', 'package.step')
    bind_schematic_references(source)
    data = source.to_dch_bytes()
    decoded = parse_dch(data)
    part = decoded.one('/Schematic/Components/Part')
    # These append-only layouts precede supplier data and variable paths.
    # Controlled streams exercise the real decoder; they are not editor exports.
    boundary = part.one('Suppliers/PartNumber' if version == 42 else 'LibPath_Variable').source.start
    body = read_header(data).body_offset
    return data[:body-3]+(1000000+version).to_bytes(3, 'big')+data[body:boundary]


class ImportPropertiesTests(unittest.TestCase):
    def test_old_inputs_expose_current_properties_before_any_export(self):
        for version in (42, 44):
            with self.subTest(version=version):
                document = parse_dch(older_input(version))
                schematic = document.one('/Schematic')
                part = schematic.one('Components/Part')
                self.assertEqual(schematic.scalar('ProjectDir'), '')
                self.assertEqual(part.scalar('LibPath_Variable'), 'library.eli')
                self.assertEqual(part.one('Pattern/Model3D').scalar('Model3DFile_Variable'), 'package.step')
                for name in ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'SourceLocator', 'Currency'):
                    self.assertEqual(part.one('Suppliers').scalar(name), '')
                self.assertIsNotNone(part.child('Suppliers').child('Prices'))
                self.assertFalse(document.root.changed)
                part.one('Suppliers/Supplier').set_values('Edited supplier')
                for destination in ('dch','asc','dchxml'):
                    reloaded = parse(getattr(document,'to_'+destination+'_bytes')(report=ExportReport()),format=destination)
                    self.assertEqual(reloaded.one('/Schematic/Components/Part/Suppliers').scalar('Supplier'), 'Edited supplier')
                self.assertEqual(schematic.scalar('ProjectDir'), '')

    def test_project_directory_override_is_independent_of_input_version(self):
        for source in (parse_dch(older_input(44)), new_schematic()):
            with self.subTest(version=source.metadata['source_version']):
                source.one('/Schematic').set_field('ProjectDir', 'stored project')
                context = AscExportContext(project_dir='export project')
                loaded = parse_dch(source.to_dch_bytes(context=context))
                self.assertEqual(loaded.one('/Schematic').scalar('ProjectDir'), 'export project')
                self.assertEqual(source.one('/Schematic').scalar('ProjectDir'), 'stored project')


if __name__ == '__main__':
    unittest.main()
