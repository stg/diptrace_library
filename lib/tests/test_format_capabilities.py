"""Capability declarations agree with actual adapter boundaries."""
import unittest

from lib import ConversionReport, format_capabilities, new_schematic, parse, serialize
from lib.schematic.formats.dch.binary import MAX_KNOWN_VERSION, MIN_VERSION
from lib.schematic.formats.dch.versions import xml_application_version


class CapabilityTests(unittest.TestCase):
    def test_every_declared_output_is_written_and_read(self):
        document = new_schematic()
        for format in ('dch', 'asc', 'dchxml'):
            for version in format_capabilities(format).write_versions:
                with self.subTest(format=format, version=version):
                    data = serialize(document, format=format, version=version, report=ConversionReport())
                    restored = parse(data, format=format)
                    self.assertTrue(restored.complete)
                    if format == 'dchxml':
                        self.assertIn(xml_application_version(version).encode(), data)
                    else:
                        self.assertEqual(restored.metadata['source_version'], version)

    def test_read_limits_and_public_defaults_use_declared_policy(self):
        binary = format_capabilities('.DCH')
        self.assertEqual((MIN_VERSION, MAX_KNOWN_VERSION), (min(binary.read_versions), max(binary.read_versions)))
        data = serialize(new_schematic(), format='dch')
        self.assertEqual(parse(data, format='dch').metadata['source_version'], binary.default_write_version)
        self.assertFalse(binary.supports_write(True))
        self.assertFalse(binary.supports_read('46'))
        self.assertEqual(binary.output_version(), binary.default_write_version)

    def test_unsupported_versions_need_explicit_earlier_fallback(self):
        binary = format_capabilities('dch')
        latest = max(binary.write_versions)
        with self.assertRaises(ValueError):
            binary.output_version(latest + 1)
        self.assertEqual(binary.output_version(latest + 1, fallback=True), latest)
        with self.assertRaises(ValueError):
            binary.output_version(min(binary.write_versions) - 1, fallback=True)
        for format in ('dch', 'asc', 'dchxml'):
            with self.assertRaises(ValueError):
                serialize(new_schematic(), format=format, version=latest + 1)
        with self.assertRaises(ValueError):
            format_capabilities('pcb')
