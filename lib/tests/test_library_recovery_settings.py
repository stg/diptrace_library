"""Empty template text does not erase independently selected authoring options."""
from importlib import import_module
import itertools
import unittest
import xml.etree.ElementTree as ET

from lib.pattern.tests.comparison import snapshot


class LibraryRecoverySettingsTests(unittest.TestCase):
    def test_xml_keeps_empty_and_nonempty_template_switches_in_both_families(self):
        for family, xml in (('pattern', 'libxml'), ('component', 'elixml')):
            model = import_module(f'lib.{family}.model')
            api = import_module(f'lib.{family}.formats.io')
            library = model.new_library('Examples')
            if family == 'pattern':
                pattern = library.one('/Library/Patterns').append(model.new_pattern('Physical'))
                pattern_path = '/Library/Patterns/Pattern'
            else:
                component = library.one('/Library/Components').append(model.new_component('Example', 'U'))
                pattern = component.append(model.new_pattern('Physical'))
                pattern_path = '/Library/Components/Component/Pattern'
            pattern.one('Pads').append(model.new_pad('1'))
            for text, generator, attached_model in itertools.product(('', 'Example template'), (False, True), (False, True)):
                pattern['RecoveryCode'] = text
                pattern['RecoveryCode_Generator'] = generator
                pattern['RecoveryCode_Model'] = attached_model
                before = snapshot(library)
                for version in ('4.3.0.5', '4.9.5.0', '5.3.5.1'):
                    with self.subTest(family=family, text=text, generator=generator,
                                      model=attached_model, version=version):
                        current = library
                        for _ in range(3):
                            output = api.serialize(current, format=xml, version=version)
                            current = api.parse(output)
                            restored = current.one(pattern_path)
                            self.assertEqual(text, restored['RecoveryCode'])
                            self.assertEqual(generator, restored['RecoveryCode_Generator'])
                            self.assertEqual(attached_model, restored['RecoveryCode_Model'])
                        self.assertEqual(before, snapshot(library))

    def test_default_empty_template_can_still_omit_the_xml_element(self):
        from lib.pattern.model import new_library, new_pattern
        from lib.pattern.formats import io
        library = new_library('Examples')
        library.one('/Library/Patterns').append(new_pattern('Physical'))
        output = ET.fromstring(io.serialize(library, format='libxml'))
        self.assertIsNone(output.find('Patterns/Pattern/RecoveryCode'))
