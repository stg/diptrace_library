"""Distinct canonical values catch default-pad reader/writer permutations."""
from pathlib import Path
import unittest

from lib.pattern.formats.lib.read import parse as read_binary
from lib.pattern.formats.lib.write import encode
from lib.pattern.formats.asc.read import parse as read_asc
from lib.pattern.formats.libxml.read import parse as read_xml

FIXTURES = Path(__file__).with_name('fixtures')


class DefaultPadGeometryTests(unittest.TestCase):
    def test_canonical_binary_ascii_and_xml_agree_on_each_default_scalar(self):
        # Ordinary XML authors Corner37, XOff.21mm and YOff-.13mm. Canonical
        # conversions expose the corresponding named values and stream cells.
        for version in (24, 26):
            for suffix, reader in (('lib', read_binary), ('asc', read_asc), ('libxml', read_xml)):
                with self.subTest(version=version, format=suffix):
                    document = reader((FIXTURES/f'default_pad_{version}.{suffix}').read_bytes())
                    pattern = document.one('/Library/Patterns/Pattern')
                    self.assertEqual(37, pattern['PadCorner'])
                    self.assertAlmostEqual(.63, pattern['PadShape_X'], delta=.00005)
                    self.assertAlmostEqual(.39, pattern['PadShape_Y'], delta=.00005)

    def test_writer_uses_the_independently_observed_scalar_window(self):
        # The compact numbers37,.63,.39 occur consecutively in both canonical
        # binaries. Checking emitted cells independently prevents a matching
        # decoder error from hiding a writer error in a self round trip.
        window = bytes.fromhex('3ba06f50 3b9ae29c 3b9ad93c')
        for version in (24, 26):
            self.assertEqual(1, (FIXTURES/f'default_pad_{version}.lib').read_bytes().count(window))
        document = read_xml((FIXTURES/'default_pad_input.libxml').read_bytes())
        for version in (24, 25, 26):
            with self.subTest(version=version):
                self.assertEqual(1, encode(document, version=version).count(window))
