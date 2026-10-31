"""Invalid owned prefix data must not disappear during binary export."""
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.model import Element
from lib.pcb.formats.capabilities import DIP
from lib.pcb.formats.dip.preamble import read_initial_sections
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.write_initial import write_initial_sections
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.formats.errors import PcbError
from lib.pcb.formats.io import serialize
from lib.pcb.model.objects import new_document


class DipPrefixValidationTests(unittest.TestCase):
    def test_unmapped_collection_content_fails_before_output_without_mutation(self):
        for name in ('Points', 'Layers', 'ViaStyles', 'NetClasses',
                     'ClassClearances', 'NonSignals', 'HierarchySheets'):
            for version in DIP.write_versions:
                with self.subTest(collection=name, version=version):
                    document = new_document()
                    board = document.one('/Board')
                    collection = board.child(name)
                    if collection is None:
                        collection = board.add(name)
                    collection.add('Unmapped', 17)
                    before = dumps(document, preserve=False)
                    writer = Writer(version)
                    with self.assertRaises(PcbError):
                        write_initial_sections(writer, document)
                    self.assertEqual(writer.buffer, b'')
                    self.assertEqual(dumps(document, preserve=False), before)

    def test_extra_owned_values_are_rejected_by_every_format(self):
        for kind in ('NonSignal', 'HSheet', 'UId'):
            for destination in ('dip', 'asc', 'dipxml'):
                with self.subTest(kind=kind, destination=destination):
                    document = new_document()
                    board = document.one('/Board')
                    if kind == 'NonSignal':
                        board.add('NonSignals').add('NonSignal', 'Assembly', 0x123456, 101, 1)
                    else:
                        sheet = board.add('HierarchySheets').add('HSheet', 'Controller', 40)
                        if kind == 'HSheet':
                            sheet.set_values('Controller', 40, 101)
                        else:
                            sheet.add('UpdateIds').add('UId', 91, 'Instance', 101)
                    before = dumps(document, preserve=False)
                    with self.assertRaises(PcbError):
                        serialize(document, format=destination, report=ConversionReport())
                    self.assertEqual(dumps(document, preserve=False), before)

    def test_valid_custom_layers_and_nested_hierarchy_keep_values_and_order(self):
        document = new_document()
        board = document.one('/Board')
        layers = board.add('NonSignals')
        for name, color, side in (('Assembly top', 0x123456, 1), ('Assembly bottom', 0x654321, 2)):
            layer = layers.add('NonSignal', name)
            layer['Color'], layer['Side'] = color, side
        sheet = board.add('HierarchySheets').add('HSheet', 'Controller', 40)
        blocks = sheet.add('UpdateIds')
        blocks.add('UId', 91, 'Top block')
        blocks.add('UId', 107, 'Nested block')
        before = dumps(document, preserve=False)
        for version in DIP.write_versions:
            with self.subTest(version=version):
                writer = Writer(version)
                write_initial_sections(writer, document)
                reader, root = Reader(bytes(writer.buffer)), Element('')
                read_initial_sections(reader, root)
                self.assertEqual(reader.pos, len(writer.buffer))
                self.assertEqual([row.values for row in root.select('/Board/NonSignals/NonSignal')],
                                 [('Assembly top', 0x123456, 0, 1), ('Assembly bottom', 0x654321, 1, 2)])
                restored = root.one('/Board/HierarchySheets/HSheet')
                self.assertEqual(restored.values, ('Controller', 40))
                self.assertEqual([row.values for row in restored.select('UpdateIds/UId')],
                                 [(91, 'Top block'), (107, 'Nested block')])
                self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
