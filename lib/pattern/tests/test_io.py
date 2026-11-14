"""Standalone pattern adapters meet the shared file/buffer contract."""
import unittest

from lib.pattern.formats import io
from lib.pattern.model import new_library, new_pattern, new_pad
from lib.tests.library_io_contract import LibraryIOContract


class PatternIOTests(LibraryIOContract,unittest.TestCase):
    api, family, native, xml = io, 'pattern', 'lib', 'libxml'
    pad_path = '/Library/Patterns/Pattern/Pads/Pad[1]'

    def make_document(self):
        document = new_library('Examples')
        pattern = document.one('/Library/Patterns').append(new_pattern('Example'))
        for number,x in (('1',-3),('2',3)):
            pattern.one('Pads').append(new_pad(number,x=x))
        return document


if __name__=='__main__':
    unittest.main()
