"""Viewport percentage conversion must not inherit caller Decimal rounding."""
from decimal import Decimal, localcontext
import unittest

from lib.common.asc import dumps
from lib.common.binary import BinaryWriter
from lib.common.conversion import ConversionReport
from lib.common.model import Document
from lib.pcb.formats.capabilities import DIP
from lib.pcb.formats.dip.preamble import read_initial_sections
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.write import encode
from lib.pcb.formats.dip.write_initial import write_initial_sections
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.model.objects import new_document
from lib.pcb.tests.test_dip_output import configured_document, reopen


def prefix(document, version):
    writer = Writer(version)
    write_initial_sections(writer, document)
    return bytes(writer.buffer)


class DipScalePrecisionTests(unittest.TestCase):
    def test_percent_conversion_rounds_once_independent_of_caller_precision(self):
        document = new_document()
        cases = (('137.25', '1.3725'), ('1.055', '.0106'),
                 ('1.185', '.0118'), ('1.245', '.0124'), ('1.255', '.0126'))
        for version in DIP.write_versions:
            for percent, expected in cases:
                for value in (float(percent), Decimal(percent)):
                    document.root['Scale'] = value
                    for precision in (2, 28):
                        with self.subTest(version=version, percent=percent,
                                          type=type(value).__name__, precision=precision):
                            with localcontext() as context:
                                context.prec = precision
                                reader = Reader(prefix(document, version))
                                self.assertEqual(reader.number(), Decimal(expected))
                            self.assertEqual(document.root['Scale'], Decimal(percent))

    def test_import_limits_precede_exact_percent_conversion(self):
        data = prefix(new_document(), DIP.default_write_version)
        start = Reader(data).pos
        for factor, expected in (('-1', '1'), ('.0001', '1'), ('1001', '100000')):
            writer = BinaryWriter()
            writer.number(Decimal(factor))
            changed = data[:start]+bytes(writer.buffer)+data[start+4:]
            for precision in (2, 28):
                with self.subTest(factor=factor, precision=precision), localcontext() as context:
                    context.prec = precision
                    loaded = Document()
                    reader = Reader(changed)
                    read_initial_sections(reader, loaded.root)
                    self.assertEqual(loaded.root['Scale'], Decimal(expected))
                    self.assertEqual(reader.pos, len(changed))

    def test_complete_stream_preserves_source_and_stabilizes(self):
        document = configured_document()
        document.root['Scale'] = Decimal('1.055')
        before = dumps(document, preserve=False)
        for version in DIP.write_versions:
            with self.subTest(version=version):
                data = encode(document, version=version, report=ConversionReport())
                loaded = reopen(data, report=ConversionReport())
                self.assertEqual(loaded.root['Scale'], Decimal('1.06'))
                self.assertEqual(encode(loaded, version=version, report=ConversionReport()), data)
                self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
