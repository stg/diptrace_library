"""The few public workflows run against self-contained designs in every format."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.schematic.create import build
from examples.schematic.edit import edit
from examples.schematic.convert import convert
from lib import ConversionReport, parse, read, schematic_schema, serialize, write


class ExampleTests(unittest.TestCase):
    def test_create_edit_and_each_format_keep_current_facts(self):
        with redirect_stdout(StringIO()):
            design = edit(build())
        for kind in ('dch', 'asc', 'dchxml'):
            with self.subTest(kind=kind):
                report = ConversionReport()
                current = parse(serialize(design, format=kind, version=52, report=report)
                                if kind != 'asc' else serialize(design, format=kind, report=report),
                                format=kind, report=report)
                part = current.one('/Schematic/Components/Part')
                self.assertEqual(part['Value'], 'Edited input')
                self.assertEqual(part.one('UserFields/UserField')['Value'], 'Fit')
                first, second = part.select('Pins/Pin')
                self.assertIsNone(first['Net'])
                self.assertEqual(second['Net']['Name'], 'ALTERNATE')
                self.assertEqual(len(current.select('/Schematic/Shapes/Shape')), 2)
                current.validate()
                self.assertEqual(report.errors, [])

    def test_file_conversion_example_accepts_each_input_and_output(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary, redirect_stdout(StringIO()):
            directory = Path(temporary)
            for incoming in ('dch', 'asc', 'dchxml'):
                source = directory/('source.'+incoming)
                write(build(), source, report=ConversionReport())
                for outgoing in ('dch', 'asc', 'dchxml'):
                    with self.subTest(incoming=incoming, outgoing=outgoing):
                        target = directory/('converted.'+outgoing)
                        report = convert(source, target, units='mm')
                        current = read(target, report=report)
                        self.assertEqual(current.one('/Schematic/Components/Part')['RefDes'], 'J1')
                        self.assertEqual(report.errors, [])

    def test_catalogue_is_immutable_and_ownership_types_are_resolvable(self):
        catalogue = schematic_schema()
        with self.assertRaises(TypeError):
            catalogue['Other'] = catalogue['Part']
        for definition in catalogue.values():
            for child in definition.children.values():
                for name in child.record.split('|'):
                    self.assertIn(name, catalogue, (definition.name, child.name))
        for node in build().root.walk():
            if node.schema is not None:
                self.assertIs(node.schema, catalogue[node.schema.name])
