"""Named editing uses one model across all schematic formats."""
import unittest

from lib import Element, Index, ReferenceError, ConversionReport, new_schematic, parse
from lib.schematic.model.objects import new_symbol, new_pin, new_symbol_shape
from lib.schematic.model.refs import bind_schematic_references


def design():
    doc = new_schematic()
    part = doc.one('/Schematic/Components').append(new_symbol('Device', 'R1'))
    part.set_field('Width', 12)
    part.set_field('Height', 9)
    part['Value'] = '1k'
    part['Datasheet'] = 'example.pdf'
    part.one('Pins').append(new_pin())
    bind_schematic_references(doc)
    return parse(doc.to_dch_bytes(), format='dch')


class NamedFieldTests(unittest.TestCase):
    def test_document_display_fields_are_named_and_convert_without_a_rebuild(self):
        doc = design()
        self.assertEqual(doc.root.schema.name, 'SchematicDocument')
        doc.root['Scale'] = 125
        doc.root['Xpos'], doc.root['Ypos'] = 12, -9
        for kind in ('dch', 'asc'):
            with self.subTest(kind=kind):
                restored = parse(getattr(doc, 'to_'+kind+'_bytes')(report=ConversionReport()),
                                 format=kind, report=ConversionReport())
                self.assertEqual((restored.root['Scale'], restored.root['Xpos'], restored.root['Ypos']),
                                 (125, 12, -9))
        with self.assertRaises(TypeError):
            doc.root['Scale'] = 'large'
        doc.validate()

    def test_identification_header_is_named_and_does_not_select_output_or_bindings(self):
        doc = design()
        header = doc.one('/Source')
        header['Version'] = 999
        header['Type'] = 'Inspection label'
        part = doc.one('/Schematic/Components/Part')
        copied = doc.copy(part, fields={'RefDes': 'R2'})
        self.assertTrue(doc.references.outgoing(copied, role='component-page'))
        result = parse(doc.to_dch_bytes(version=52, report=ConversionReport()), format='dch')
        self.assertEqual(result.metadata['source_version'], 52)
        self.assertEqual(result.one('/Source')['Type'], 'DipTrace-Schematic')
        self.assertEqual(result.one('/Schematic/Components/Part[RefDes="R2"]')['Value'], copied['Value'])

    def test_canonical_records_reject_unnamed_adapter_tail_values(self):
        doc = design()
        part = doc.one('/Schematic/Components/Part')
        part.set_values(*part.values, 123)  # Bypass the named API deliberately.
        with self.assertRaisesRegex(ValueError, 'unnamed values'):
            doc.validate()
        with self.assertRaisesRegex(ValueError, 'unnamed values'):
            doc.to_dch_bytes(report=ConversionReport())

    def test_diagnostic_annotations_cannot_hide_unknown_data_from_writers(self):
        doc = design()
        unknown = doc.one('/Schematic/Components/Part').add('UnmappedFact', 42)
        unknown.annotations['asc_omit'] = 'diagnostic only'
        for kind in ('dch', 'asc', 'dchxml'):
            report = ConversionReport()
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'unsupported schematic field'):
                getattr(doc, 'to_'+kind+'_bytes')(report=report)
            self.assertEqual(len(report.errors), 1)

    def test_calculated_names_work_in_selectors(self):
        doc = design()
        pin = doc.one('//Pin[Index=0]')
        self.assertEqual(pin['Index'], 0)
        pin.parent.append(new_pin())
        pin.move_to(pin.parent, 1)
        self.assertIs(doc.one('//Pin[Index=1]'), pin)

    def test_named_edits_from_each_format_drive_each_output(self):
        source = design()
        for incoming in ('dch', 'asc', 'dchxml'):
            doc = parse(getattr(source, 'to_'+incoming+'_bytes')(report=ConversionReport()), format=incoming)
            part = doc.one('//Part[RefDes="R1"]')
            part['RefDes'] = 'R12'
            part.set('Value', '22k')
            part.one('Pins/Pin')['X'] = 7
            self.assertEqual(doc.one('//Part[RefDes="R12"]'), part)
            self.assertEqual(part.get('Value'), '22k')
            for outgoing in ('dch', 'asc', 'dchxml'):
                with self.subTest(incoming=incoming, outgoing=outgoing):
                    loaded = parse(getattr(doc, 'to_'+outgoing+'_bytes')(report=ConversionReport()), format=outgoing)
                    current = loaded.one('//Part[RefDes="R12"]')
                    self.assertEqual(current['Value'], '22k')
                    self.assertEqual(current.one('Pins/Pin')['X'], 7)

    def test_names_are_fields_and_not_duplicate_positional_storage(self):
        part = design().one('//Part')
        self.assertTrue(all(isinstance(item, Element) for item in part.items))
        self.assertEqual(part.one('RefDes').values, ('R1',))
        self.assertEqual(part.values, ('Device', 'R1'))
        part['Name'] = 'Changed'
        self.assertEqual(part.values, ('Changed', 'R1'))
        self.assertEqual(part.schema.field('RefDes').kind, 'text')

    def test_optional_deletion_remains_absent_while_output_gets_required_defaults(self):
        doc = design()
        part = doc.one('//Part')
        del part['Datasheet']
        self.assertNotIn('Datasheet', part)
        self.assertIsNone(part.get('Datasheet'))
        for outgoing in ('dch', 'asc', 'dchxml'):
            loaded = parse(getattr(doc, 'to_'+outgoing+'_bytes')(report=ConversionReport()), format=outgoing)
            self.assertEqual(loaded.one('/Schematic/Components/Part')['Datasheet'], '')
            self.assertNotIn('Datasheet', part)

    def test_rename_updates_bound_text_immediately_but_leaves_literal_text(self):
        doc = design()
        part = doc.one('//Part')
        bound = next(shape for shape in part.select('Shapes/Shape') if shape.scalar('FontType') == 2)
        literal = part.one('Shapes').append(new_symbol_shape())
        literal.set_field('Type', 10)
        literal.one('TextLine').add('pt', 'R1')
        literal.one('Points_New').add('pt', 0, 0)
        part['RefDes'] = 'R12'
        self.assertEqual(bound.one('TextLine/pt').values, ('R12',))
        self.assertEqual(literal.one('TextLine/pt').values, ('R1',))

    def test_derived_index_follows_order_without_becoming_editable_data(self):
        doc = design()
        pins = doc.one('//Part/Pins')
        first = pins.one('Pin')
        second = pins.append(new_pin())
        self.assertEqual((first['Index'], second['Index']), (0, 1))
        second.move_to(pins, 0)
        self.assertEqual((first['Index'], second['Index']), (1, 0))
        self.assertIsNone(first.child('Index'))
        with self.assertRaises(TypeError):
            first['Index'] = 5
        with self.assertRaises(TypeError):
            del first['Index']

    def test_bound_text_repair_failure_leaves_authoring_value_and_text_unchanged(self):
        doc = design()
        part = doc.one('//Part')
        bound = next(shape for shape in part.select('Shapes/Shape') if shape.scalar('FontType') == 3)
        extra = bound.one('TextLine').add('pt', 'extra authored row')
        pointer = doc.root.add('Dependency', 1)
        doc.references.bind(pointer, extra, Index(pointer))
        with self.assertRaisesRegex(ReferenceError, 'referenced text row'):
            part['Value'] = 'changed'
        self.assertEqual(part['Value'], '1k')
        self.assertEqual([row.values for row in bound.one('TextLine').children()], [('1k',), ('extra authored row',)])

    def test_bound_text_follows_new_component_ownership_within_and_between_documents(self):
        for separate_document in (False, True):
            with self.subTest(separate_document=separate_document):
                source = design()
                part = source.one('/Schematic/Components/Part')
                shape = next(item for item in part.select('Shapes/Shape') if item['FontType'] == 2)
                row = shape.one('TextLine/pt')
                destination = new_schematic() if separate_document else source
                other = destination.one('/Schematic/Components').append(new_symbol('Other', 'R8'))
                shape.move_to(other.one('Shapes'))
                self.assertEqual(row['Text'], 'R8')
                other['RefDes'] = 'R9'
                self.assertEqual(row['Text'], 'R9')
                self.assertIs(shape.one('TextLine/pt'), row)
                source.validate()
                destination.validate()


if __name__ == '__main__':
    unittest.main()
