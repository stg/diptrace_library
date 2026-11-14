"""Capability versions describe actual emitted standalone component headers."""
import unittest
from unittest.mock import patch

import lib

from lib.common.document_families import input_identity
from lib.common.errors import UnsupportedFileError
from lib.common.conversion import ConversionReport
from lib.component.model import new_library
from lib.component.formats.capabilities import format_capabilities
from lib.component.formats.eli.write import encode
from lib.component.formats.asc.write import dumps as ascii_text
from lib.component.formats.elixml.write import dumps as xml_text


class CapabilityTests(unittest.TestCase):
    def test_every_declared_output_version_is_the_actual_header(self):
        for key, write in (('eli',encode),('asc',ascii_text),('elixml',xml_text)):
            capabilities = format_capabilities(key)
            self.assertEqual('component',capabilities.family)
            for version in capabilities.write_versions:
                with self.subTest(format=key,version=version):
                    result = write(new_library(),version=version,report=ConversionReport())
                    identity = input_identity(result)
                    self.assertEqual(('component',key,version),(identity.family,identity.format,identity.version))
            result = write(new_library(),report=ConversionReport())
            self.assertEqual(capabilities.output_version(),input_identity(result).version)

    def test_exact_versions_errors_and_recognition_do_not_activate_the_family(self):
        from lib import format_capabilities as public_capabilities
        self.assertTrue(format_capabilities('.ELI').supports_read(23))
        self.assertFalse(format_capabilities('eli').supports_read(22))
        self.assertFalse(format_capabilities('eli').supports_write(30))
        self.assertEqual(33,format_capabilities('eli').output_version(34,fallback=True))
        self.assertTrue(format_capabilities('elixml').supports_read('5.3'))
        self.assertFalse(format_capabilities('elixml').supports_read('5.2'))
        with self.assertRaises(UnsupportedFileError) as caught:
            format_capabilities('lib')
        self.assertEqual(('component','lib','format'),
                         (caught.exception.family,caught.exception.format,caught.exception.reason))
        unavailable = {name: adapter for name, adapter in lib._FAMILY_ADAPTERS.items() if name != 'component'}
        with patch.dict(lib._FAMILY_ADAPTERS, unavailable, clear=True):
            with self.assertRaises(UnsupportedFileError):
                public_capabilities('eli')


if __name__=='__main__':
    unittest.main()
