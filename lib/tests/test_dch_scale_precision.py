"""DCH viewport scale uses exact percent conversion before wire rounding."""
from decimal import Decimal, localcontext
import unittest

import lib
from lib.common.binary import BinaryWriter
from lib.schematic.formats.capabilities import DCH
from lib.schematic.formats.dch.read import Reader, _preamble
from lib.schematic.formats.dch.write import encode_header
from lib.schematic.model.document import Document


class DchScalePrecisionTests(unittest.TestCase):
    def test_halfway_percent_values_round_once_independent_of_decimal_context(self):
        document = lib.new_schematic()
        cases = (('1.055', '.0106'), ('1.185', '.0118'),
                 ('1.245', '.0124'), ('1.255', '.0126'))
        for version in DCH.write_versions:
            for percent, expected in cases:
                document.root['Scale'] = Decimal(percent)
                for precision in (2, 28):
                    with self.subTest(version=version, percent=percent, precision=precision):
                        with localcontext() as context:
                            context.prec = precision
                            reader = Reader(encode_header(document, version=version))
                            self.assertEqual(reader.number(), Decimal(expected))
                        self.assertEqual(document.root['Scale'], Decimal(percent))

    def test_import_zoom_limits_are_applied_before_percent_conversion(self):
        header = encode_header(lib.new_schematic(), version=DCH.default_write_version)
        start = Reader(header).pos
        for factor, expected in (('-1', '1'), ('.0001', '1'), ('1001', '100000')):
            writer = BinaryWriter()
            writer.number(Decimal(factor))
            data = header[:start]+bytes(writer.buffer)+header[start+4:]
            for precision in (2, 28):
                with self.subTest(factor=factor, precision=precision), localcontext() as context:
                    context.prec = precision
                    loaded = Document()
                    reader = Reader(data)
                    _preamble(reader, loaded)
                    self.assertEqual(loaded.root['Scale'], Decimal(expected))
                    self.assertEqual(reader.pos, len(data))

    def test_complete_output_preserves_source_and_stabilizes_at_wire_precision(self):
        document = lib.new_schematic()
        document.root['Scale'] = Decimal('1.055')
        for version in DCH.write_versions:
            with self.subTest(version=version):
                data = lib.serialize(document, format='dch', version=version,
                                     report=lib.ConversionReport())
                loaded = lib.parse(data, report=lib.ConversionReport())
                self.assertEqual(loaded.root['Scale'], Decimal('1.06'))
                self.assertEqual(lib.serialize(loaded, format='dch', version=version,
                                              report=lib.ConversionReport()), data)
                self.assertEqual(document.root['Scale'], Decimal('1.055'))


if __name__ == '__main__':
    unittest.main()
