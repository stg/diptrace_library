"""Shared design behavior does not depend on diagnostic import metadata."""
import unittest

from lib import Document, ExportReport, new_schematic, parse, parse_source
from lib.schematic.model.objects import (new_symbol, new_pin, new_symbol_shape)
from lib.schematic.model.refs import (bind_schematic_references)


class DocumentViewTests(unittest.TestCase):
    def sample(self):
        document = new_schematic(sheet_name='Programmatic data')
        part = document.one('/Schematic/Components').append(new_symbol('Connector', 'J1'))
        part.one('Pins').append(new_pin())
        bind_schematic_references(document)
        return document

    def test_all_imports_and_exports_work_without_provenance(self):
        document = self.sample()
        for source in ('dch', 'asc', 'dchxml'):
            data = getattr(document, 'to_'+source+'_bytes')(report=ExportReport())
            imported = parse(data, format=source)
            expected = {target: getattr(imported, 'to_'+target+'_bytes')(report=ExportReport())
                        for target in ('dch', 'asc', 'dchxml')}
            imported.metadata.clear()
            self.assertEqual(imported.representation, 'schematic')
            for current in (imported, imported.clone(), imported.as_schematic()):
                self.assertEqual(current.metadata, {})
                for target in expected:
                    with self.subTest(source=source, target=target):
                        output = getattr(current, 'to_'+target+'_bytes')(report=ExportReport())
                        self.assertEqual(output, expected[target])

    def test_source_views_normalize_without_diagnostic_format_tags(self):
        document = self.sample()
        for format in ('asc', 'dchxml'):
            data = getattr(document, 'to_'+format+'_bytes')(report=ExportReport())
            source = parse_source(data, format=format)
            source.metadata.clear()
            self.assertEqual(source.representation, format)
            self.assertEqual(source.clone().representation, format)
            shared = source.as_schematic()
            self.assertEqual(shared.representation, 'schematic')
            self.assertEqual(shared.one('/Schematic/Components/Part').values, ('Connector', 'J1'))
            self.assertTrue(shared.to_dch_bytes(report=ExportReport()))

    def test_reference_binding_and_reordering_are_independent_of_provenance(self):
        document = self.sample()
        part = document.one('/Schematic/Components/Part')
        fields = part.one('UserFields')
        first = fields.add('UserField', 'First', 'one')
        fields.add('UserField', 'Second', 'two')
        marking = part.one('Shapes').append(new_symbol_shape())
        marking.set_field('FontType', 20)
        marking.set_field('MarkingGenerated', True)
        document.metadata.clear()
        bind_schematic_references(document)
        link = document.references.outgoing(marking, role='marking-user-field')[0]
        self.assertIs(link.target, first)
        first.move_to(fields, 1)
        document.rebuild()
        self.assertEqual(marking.scalar('FontType'), 21)
        self.assertIs(link.target, first)

    def test_view_and_completeness_cannot_be_claimed_by_provenance_flags(self):
        document = Document()
        document.metadata.update(source_format='dch', binary_consumed=True, dch_output_ready=True)
        with self.assertRaisesRegex(ValueError, 'complete shared schematic'):
            document.to_dch_bytes()
        document = self.sample()
        document.complete = False
        for target in ('dch', 'asc', 'dchxml'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                getattr(document, 'to_'+target+'_bytes')()
        with self.assertRaises(AttributeError):
            document.representation = 'asc'


if __name__ == '__main__':
    unittest.main()
