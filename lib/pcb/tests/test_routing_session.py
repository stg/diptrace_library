"""Ordinary import clears transient sessions while retaining the saved board."""
from decimal import Decimal
from importlib import import_module
import unittest
from unittest.mock import patch

from lib.common import asc
from lib.common.binary import BinaryWriter
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.dip.binary import DipError
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.routing_session import read_routing_session
from lib.pcb.tests.test_dip_output import configured_document


def session(populated):
    """Synthetic session values, independent of the board they accompany."""
    writer, counts = BinaryWriter(), {}
    size = 2 if populated else 0

    def values(kind, count):
        for index in range(count):
            value = {'integer': -index-1, 'number': Decimal(index)+Decimal('.1234'),
                     'boolean': index % 2 == 0}[kind]
            getattr(writer, kind)(value)

    def count(label):
        counts.setdefault(label, len(writer.buffer))
        writer.integer(size)
        return range(size)

    def points():
        for _ in count('trace points'):
            values('integer', 9)
            values('number', 6)
            values('boolean', 4)

    def side():
        for _ in count('side points'):
            values('number', 4)
            values('integer', 3)
            values('boolean', 2)

    def segment():
        values('integer', 6)
        for _ in count('center points'):
            values('number', 2)
            values('integer', 9)
            values('boolean', 2)
            side()
            side()

    values('boolean', 3)
    values('integer', 5)
    for _ in range(2):
        for _ in count('selections'):
            writer.integer(12)
    for _ in count('routes'):
        values('integer', 11)
        values('number', 3)
        points()
        values('number', 2)
        values('integer', 8)
        points()
        for _ in count('trace history'):
            writer.integer(4)
            writer.boolean(True)
            values('integer', 8)
            points()
    values('integer', 4)
    values('number', 2)
    segment()
    segment()
    for _ in range(2):
        values('number', 4)
        values('integer', 3)
        values('boolean', 2)
    for _ in count('pair history'):
        segment()
        writer.integer(9)
        values('boolean', 2)
    return bytes(writer.buffer), counts


def cursor(payload, version=62):
    header = b'\x07DTBOARD'+(1_000_000+version).to_bytes(3, 'big')
    return Reader(header+payload)


class RoutingSessionTests(unittest.TestCase):
    def test_normal_import_discards_only_the_session_in_every_output_revision(self):
        binary = import_module('lib.pcb.formats.dip.write')
        ordinary_paths = binary.write_variable_paths
        document = configured_document()
        for populated in (False, True):
            payload, _ = session(populated)

            def with_session(writer, *args, **options):
                ordinary_paths(writer, *args, **options)
                self.assertEqual(writer.buffer[-1], 0)
                writer.buffer[-1:] = b'\x01'+payload

            for version in io.format_capabilities('dip').write_versions:
                with self.subTest(populated=populated, version=version):
                    baseline = io.parse(binary.encode(document, version=version, report=ConversionReport()),
                                        report=ConversionReport())
                    with patch.object(binary, 'write_variable_paths', with_session):
                        encoded = binary.encode(document, version=version, report=ConversionReport())
                    report = ConversionReport()
                    restored = io.parse(encoded, report=report)
                    self.assertEqual(asc.dumps(restored, preserve=False), asc.dumps(baseline, preserve=False))
                    notices = [row for row in report.notices if row.rule == 'interactive-routing-session']
                    self.assertEqual(len(notices), 1)
                    self.assertEqual((notices[0].severity, notices[0].operation, notices[0].format),
                                     ('info', 'import', 'dip'))
                    restored.validate()
                    self.assertEqual(binary.encode(restored, version=version, report=ConversionReport()),
                                     binary.encode(baseline, version=version, report=ConversionReport()))

    def test_collection_consumption_stops_at_the_following_field(self):
        suffix = BinaryWriter()
        suffix.integer(357)
        for populated in (False, True):
            payload, _ = session(populated)
            for version in (53, 54, 58, 60, 62):
                with self.subTest(populated=populated, version=version):
                    reader = cursor(payload+suffix.buffer, version)
                    read_routing_session(reader)
                    self.assertEqual(reader.integer(), 357)
                    self.assertEqual(reader.pos, len(reader.data))

    def test_truncation_is_rejected_instead_of_returning_a_partial_board(self):
        for populated in (False, True):
            payload, _ = session(populated)
            for length in (0, 2, 17, len(payload)//2, len(payload)-1):
                with self.subTest(populated=populated, length=length), self.assertRaises(DipError):
                    read_routing_session(cursor(payload[:length]))

    def test_invalid_counts_and_flags_are_still_validated(self):
        payload, counts = session(True)
        for name, offset in counts.items():
            for value in (-1, 1_000_000):
                changed = bytearray(payload)
                changed[offset:offset+3] = (1_000_000+value).to_bytes(3, 'big')
                with self.subTest(count=name, value=value), self.assertRaises(DipError):
                    read_routing_session(cursor(changed))
        for offset in (0, len(payload)-1):
            changed = bytearray(payload)
            changed[offset] = 2
            with self.subTest(flag=offset), self.assertRaisesRegex(DipError, 'invalid boolean'):
                read_routing_session(cursor(changed))


if __name__ == '__main__':
    unittest.main()
