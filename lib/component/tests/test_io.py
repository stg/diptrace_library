"""Standalone component adapters meet the shared file/buffer contract."""
import unittest

from lib.component.formats import io
from lib.component.model import new_library, new_component, new_pattern, new_pad, new_pin
from lib.tests.library_io_contract import LibraryIOContract


class ComponentIOTests(LibraryIOContract,unittest.TestCase):
    api, family, native, xml = io, 'component', 'eli', 'elixml'
    pad_path = '/Library/Components/Component/Pattern/Pads/Pad[1]'

    def make_document(self):
        document = new_library('Examples')
        component = document.one('/Library/Components').append(new_component('Example','U'))
        pattern = component.append(new_pattern('Physical'))
        part = component.one('Parts/Part')
        for number,x in (('1',-3),('2',3)):
            pad = pattern.one('Pads').append(new_pad(number,x=x))
            pin = part.one('Pins').append(new_pin())
            pin['X'],pin['StringNumber'],pin['Pad'] = x,number,pad
        return document


if __name__=='__main__':
    unittest.main()
