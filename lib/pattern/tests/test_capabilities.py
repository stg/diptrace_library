"""Capability versions describe actual emitted standalone pattern headers."""
import unittest
from unittest.mock import patch

import lib

from lib.common.document_families import input_identity
from lib.common.errors import UnsupportedFileError
from lib.common.conversion import ConversionReport
from lib.pattern.model import new_library
from lib.pattern.formats.capabilities import format_capabilities
from lib.pattern.formats.lib.write import encode
from lib.pattern.formats.asc.write import dumps as ascii_text
from lib.pattern.formats.libxml.write import dumps as xml_text


class CapabilityTests(unittest.TestCase):
    def test_every_declared_output_version_is_the_actual_header(self):
        for key, write in (('lib',encode),('asc',ascii_text),('libxml',xml_text)):
            capabilities = format_capabilities(key)
            self.assertEqual('pattern',capabilities.family)
            for version in capabilities.write_versions:
                with self.subTest(format=key,version=version):
                    result = write(new_library(),version=version,report=ConversionReport())
                    identity = input_identity(result)
                    self.assertEqual(('pattern',key,version),(identity.family,identity.format,identity.version))
            result = write(new_library(),report=ConversionReport())
            self.assertEqual(capabilities.output_version(),input_identity(result).version)

    def test_exact_versions_errors_and_recognition_do_not_activate_the_family(self):
        from lib import format_capabilities as public_capabilities
        self.assertTrue(format_capabilities('.LIB').supports_read(17))
        self.assertFalse(format_capabilities('lib').supports_read(16))
        self.assertFalse(format_capabilities('lib').supports_write(23))
        self.assertEqual(26,format_capabilities('lib').output_version(27,fallback=True))
        self.assertTrue(format_capabilities('libxml').supports_read('5.2'))
        with self.assertRaises(UnsupportedFileError) as caught:
            format_capabilities('dch')
        self.assertEqual(('pattern','dch','format'),
                         (caught.exception.family,caught.exception.format,caught.exception.reason))
        unavailable = {name: adapter for name, adapter in lib._FAMILY_ADAPTERS.items() if name != 'pattern'}
        with patch.dict(lib._FAMILY_ADAPTERS, unavailable, clear=True):
            with self.assertRaises(UnsupportedFileError):
                public_capabilities('lib')


if __name__=='__main__':
    unittest.main()
