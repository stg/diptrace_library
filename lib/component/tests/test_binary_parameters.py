"""Standalone part prefixes use the same named symbol parameters as caches."""
import unittest

from lib.common.binary_records import RecordWriter
from lib.common.model import Element
from lib.common.symbol_codec import write_symbol_parameters
from lib.common.symbol_objects import new_symbol
from lib.component.formats.eli.binary import ComponentError
from lib.component.formats.eli.parameters import read_part_parameters
from lib.component.formats.eli.reader import Reader
from lib.component.tests.test_binary_header import stream


def parameters(version):
    part = new_symbol('caf\u00e9', 'U')
    for name, value in dict(PartType=1, PartName='Power', ShowNumbers=2, Type=3,
                            Number1=4, Number2=7, Width=12.5, Height=6,
                            Value='Example value', LockProperties=True).items():
        part[name] = value
    writer = RecordWriter()
    if version < 24:
        def text(value):
            encoded = value.encode('cp1252')
            writer.buffer.append(len(encoded))
            writer.buffer.extend(encoded)
        writer.text = text
    write_symbol_parameters(writer, part)
    return part, bytes(writer.buffer)


class BinaryParameterTests(unittest.TestCase):
    def test_named_fields_and_next_payload_boundary_in_each_text_mode(self):
        for version in (23, 24, 31, 33):
            with self.subTest(version=version):
                source, payload = parameters(version)
                reader = Reader(stream(version)+payload+b'end')
                result = read_part_parameters(reader, Element('Parts'))
                for name in ('Enabled', 'PartType', 'PartName', 'ShowNumbers', 'Type', 'Number1',
                             'Number2', 'Width', 'Height', 'Name', 'RefDes', 'Value', 'LockProperties'):
                    self.assertEqual(source[name], result[name], name)
                self.assertEqual(b'end', reader.take(3))

    def test_every_truncated_parameter_boundary_is_rejected(self):
        _, payload = parameters(31)
        for size in range(len(payload)):
            with self.subTest(size=size), self.assertRaises(ComponentError):
                read_part_parameters(Reader(stream()+payload[:size]), Element('Parts'))


if __name__ == '__main__':
    unittest.main()
