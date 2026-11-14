"""Canonical standalone ASC uses the same current component data and links."""
from pathlib import Path
import unittest

from lib.common.conversion import ConversionReport
from lib.common.errors import UnsupportedFileError
from lib.common.model import Element
from lib.common.schema import MISSING
from lib.component.formats.asc.read import parse
from lib.component.formats.eli.read import parse as parse_binary
from lib.component.model import new_library, new_component, new_pattern

FIXTURES = Path(__file__).with_name('fixtures')


def facts(document):
    result = {}
    for node in document.root.walk(include_self=True):
        if node.schema is None:
            continue
        for name, definition in node.schema.fields.items():
            if definition.getter is None and node.child(name) is None and definition.default is MISSING:
                continue
            value = node.get(name, None if definition.default is MISSING else definition.default)
            result[node.path+'/'+name] = value.path if isinstance(value, Element) else value
    return result


class AsciiReadTests(unittest.TestCase):
    def test_empty_physical_arrays_do_not_require_boundary_records(self):
        from lib.common.asc_library_output import dumps
        from lib.component.formats.asc.write import project_document, COLLECTIONS
        for name in ('', 'Empty footprint'):
            with self.subTest(name=name):
                document = new_library()
                component = document.one('/Library/Components').append(new_component('Example', 'U'))
                if name:
                    component.append(new_pattern(name))
                syntax = project_document(document)
                pattern = syntax.one('/Library/Components/Component/Pattern')
                for collection in ('Pads', 'Shapes', 'Holes'):
                    for child in pattern.one(collection).children():
                        child.detach()
                restored = parse(dumps(syntax, collections=COLLECTIONS))
                component = restored.one('/Library/Components/Component')
                self.assertEqual('Example', component['Name'])
                if name:
                    self.assertEqual(name, component.one('Pattern')['Name'])
                    self.assertEqual([], component.select('Pattern/Pads/Pad'))
                else:
                    self.assertIsNone(component.child('Pattern'))
                restored.validate()

    def test_all_named_facts_and_references_match_the_paired_binary(self):
        data = (FIXTURES/'connections.asc').read_bytes()
        before = bytes(data)
        report = ConversionReport()
        document = parse(data, report=report)
        binary = parse_binary((FIXTURES/'connections_31.eli').read_bytes())
        self.assertEqual(facts(binary), facts(document))
        self.assertEqual([], report.errors)
        self.assertEqual([], document.unresolved())
        self.assertIsNone(document.root.source)
        self.assertEqual(before, data)
        document.validate()

    def test_multipart_metadata_and_part_owned_content(self):
        for version in (31, 32, 33):
            with self.subTest(version=version):
                document = parse((FIXTURES/f'multipart_{version}.asc').read_bytes())
                component = document.one('/Library/Components/Component')
                parts = component.select('Parts/Part')
                self.assertEqual(['Gate A', 'Gate B'], [part['PartName'] for part in parts])
                self.assertEqual(['First value', 'Second value'], [part['Value'] for part in parts])
                self.assertEqual(['ExampleA', 'ExampleB'], [part['ModelString'] for part in parts])
                self.assertEqual('First note', component.one('UserFields/UserField')['Value'])
                parts[1]['Name'] = 'Renamed'
                self.assertEqual(['Renamed', 'Renamed'], [part['Name'] for part in parts])
                document.clone().validate()
                document.validate()

    def test_content_and_gate_are_checked_without_using_a_filename(self):
        text = (FIXTURES/'connections.asc').read_text(encoding='utf-8-sig')
        self.assertEqual('Example component', parse(text, source='unrelated.xml').one(
            '/Library/Components/Component')['Name'])
        for changed, reason in ((text.replace('ElementLibrary', 'UnknownLibrary', 1), 'format'),
                                (text.replace('ElementLibrary" 31', 'ElementLibrary" 32', 1), 'version')):
            with self.subTest(reason=reason), self.assertRaises(UnsupportedFileError) as raised:
                parse(changed)
            self.assertEqual(reason, raised.exception.reason)

    def test_empty_library_and_invalid_count(self):
        text = '(Source "DipTrace-ElementLibrary" 31)(Library(Name "Empty")(Hint "")(Subfolders)(Categories 0)(Components))'
        document = parse(text)
        self.assertEqual([], document.select('/Library/Components/Component'))
        document.validate()
        with self.assertRaises(ValueError):
            parse(text.replace('(Categories 0)', '(Categories 1)'))

    def test_unknown_meaningful_field_is_not_silently_discarded(self):
        text = (FIXTURES/'connections.asc').read_text(encoding='utf-8-sig')
        with self.assertRaises(NotImplementedError):
            parse(text.replace('(Enabled "Y")', '(Unexpected 123)(Enabled "Y")', 1))


if __name__ == '__main__':
    unittest.main()
