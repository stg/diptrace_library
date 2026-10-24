"""Schematic calculations join the same prospective reference edit plan."""
import unittest

from lib import Document, Element, Property, ReferenceError
from lib.common.schema import Field, Record
from lib.schematic.model.objects import new_symbol_shape, new_pattern
from lib.schematic.model.definitions import CELL
from lib.schematic.model.nested_records import TERMINAL
from lib.schematic.model.refs import bind_schematic_references
from lib.schematic.tests.test_named_fields import design
from lib.tests.test_cell_text import table_document
from lib.common.schema import MISSING


COPY = Record('Copy', {'Text': Field('Text', 'text', required=True)}, ('Text',))
PART = '/Schematic/Components/Part'


def copy_of(doc, target):
    copied = doc.root.add('Copies').append(Element('Copy', *target.values).bind_schema(COPY))
    doc.references.bind(copied, target, Property(copied, target_argument=0))
    return copied


class DerivedDependencyTests(unittest.TestCase):
    def test_property_chain_refreshes_bound_text_on_bind_edit_and_retarget(self):
        doc = design()
        part = doc.one(PART)
        row = next(item for item in part.select('Shapes/Shape') if item['FontType'] == 2).one('TextLine/pt')
        first = doc.root.append(Element('Copy', 'R20').bind_schema(COPY))
        second = doc.root.append(Element('Copy', 'R30').bind_schema(COPY))
        link = doc.references.bind(part, first, Property(part.one('RefDes'), 'Text'))
        copied = copy_of(doc, row)
        self.assertEqual((part['RefDes'], row['Text'], copied['Text']), ('R20',)*3)
        first['Text'] = 'R21'
        self.assertEqual((part['RefDes'], row['Text'], copied['Text']), ('R21',)*3)
        doc.references.retarget(link, second)
        self.assertEqual((part['RefDes'], row['Text'], copied['Text']), ('R30',)*3)
        doc.validate()

    def test_label_mode_edits_update_only_bound_text(self):
        doc = design()
        part = doc.one(PART)
        shape = part.one('Shapes').append(new_symbol_shape())
        shape['Type'] = 10
        shape.one('TextLine').add('pt', 'Literal')
        part['Value'] = '22k'
        self.assertEqual(shape.one('TextLine/pt')['Text'], 'Literal')
        shape['FontType'] = 3
        self.assertEqual(shape.one('TextLine/pt')['Text'], '22k')
        shape['FontType'] = 0
        part['Value'] = '47k'
        self.assertEqual(shape.one('TextLine/pt')['Text'], '22k')
        doc.validate()

    def test_text_copy_back_to_its_component_is_rejected_before_binding(self):
        doc = design()
        part = doc.one(PART)
        row = next(item for item in part.select('Shapes/Shape') if item['FontType'] == 2).one('TextLine/pt')
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'cycle'):
            doc.references.bind(part, row, Property(part.one('RefDes'), 'Text'))
        self.assertEqual(tuple(doc.references), before)
        self.assertEqual((part['RefDes'], row['Text']), ('R1', 'R1'))

    def test_controller_cannot_enable_a_calculation_cycle(self):
        doc = design()
        part = doc.one(PART)
        shape = part.one('Shapes').append(new_symbol_shape())
        shape['Type'] = 10
        row = shape.one('TextLine').add('pt', 'R1')
        doc.references.bind(part, row, Property(part.one('RefDes'), 'Text'))
        with self.assertRaisesRegex(ReferenceError, 'cycle'):
            shape['FontType'] = 2
        self.assertEqual((shape['FontType'], part['RefDes'], row['Text']), (0, 'R1', 'R1'))
        doc.validate()

    def test_bound_label_content_cannot_become_a_second_authored_fact(self):
        doc = design()
        part = doc.one(PART)
        shape = next(item for item in part.select('Shapes/Shape') if item['FontType'] == 2)
        row = shape.one('TextLine/pt')
        with self.assertRaisesRegex(TypeError, 'calculated'):
            row['Text'] = 'Conflicting label'
        self.assertEqual(row['Text'], part['RefDes'])
        with self.assertRaisesRegex(TypeError, 'calculated'):
            shape['ShowPart'] = not shape['ShowPart']
        shape['FontType'] = 0
        row['Text'] = 'Literal label'
        part['RefDes'] = 'R99'
        self.assertEqual(row['Text'], 'Literal label')
        doc.validate()

    def test_conflicting_copy_into_bound_text_fails_at_binding_and_retargeting(self):
        doc = design()
        part = doc.one(PART)
        shape = next(item for item in part.select('Shapes/Shape') if item['FontType'] == 2)
        row = shape.one('TextLine/pt')
        good = doc.root.append(Element('Copy', 'R1').bind_schema(COPY))
        bad = doc.root.append(Element('Copy', 'Different').bind_schema(COPY))
        with self.assertRaisesRegex(ReferenceError, 'managed projection'):
            doc.references.bind(shape, bad, Property(row, 'Text'))
        reference = doc.references.bind(shape, good, Property(row, 'Text'))
        with self.assertRaisesRegex(ReferenceError, 'managed projection'):
            doc.references.retarget(reference, bad)
        self.assertIs(doc.references.get(reference.uid).target, good)
        self.assertEqual(row['Text'], 'R1')
        doc.validate()

    def test_named_cell_row_copies_follow_current_row_height_count(self):
        doc = table_document(columns=(5, 5), rows=(5, 5))
        table = doc.one('/Schematic/Tables/Table')
        heights, cells = table.one('RowHeights'), table.one('Cells')
        cell = cells.children()[3]
        copied = doc.root.add('CellRow', 1)
        doc.references.bind(copied, cell, Property(copied, 'Row'))
        added = heights.add('pt', 5)
        self.assertEqual((cell['Column'], cell['Row'], copied.values), (1, 0, (0,)))
        self.assertIsNone(cell.child('Row'))
        self.assertIn(cell, doc.select('/Schematic/Tables/Table/Cells/Cell[Row=0]'))
        added.detach()
        self.assertEqual((cell['Row'], copied.values), (1, (1,)))
        doc.validate()

    def test_named_terminal_count_copies_follow_collection_and_clone_independently(self):
        doc = Document()
        pattern = doc.root.append(new_pattern())
        copied = doc.root.add('TerminalCount', 0)
        doc.references.bind(copied, pattern, Property(copied, 'PadTerminalCount'))
        terminal = pattern.append(Element('PadTerminal').bind_schema(TERMINAL))
        for name, definition in TERMINAL.fields.items():
            if definition.default is not MISSING and definition.getter is None:
                terminal[name] = definition.default
        self.assertEqual(copied.values, (1,))
        cloned = doc.clone()
        cloned.one('/Pattern').append(terminal.clone())
        self.assertEqual(cloned.one('/TerminalCount').values, (2,))
        self.assertEqual(copied.values, (1,))
        terminal.detach()
        self.assertEqual(copied.values, (0,))
        doc.validate()
        cloned.validate()

    def test_bound_text_dependents_update_with_the_component(self):
        doc = design()
        part = doc.one(PART)
        shape = next(item for item in part.select('Shapes/Shape') if item['FontType'] == 2)
        row = shape.one('TextLine/pt')
        copied = copy_of(doc, row)
        part['RefDes'] = 'R12'
        self.assertEqual((row.values, copied['Text']), (('R12',), 'R12'))
        doc.validate()

    def test_optional_deletion_propagates_its_derived_empty_text(self):
        doc = design()
        part = doc.one(PART)
        shape = part.one('Shapes').append(new_symbol_shape())
        shape.set_field('Type', 10)
        shape.set_field('FontType', 6)
        row = shape.one('TextLine').add('pt', part['Datasheet'])
        bind_schematic_references(doc)
        copied = copy_of(doc, row)
        del part['Datasheet']
        self.assertNotIn('Datasheet', part)
        self.assertEqual((row.values, copied['Text']), (('',), ''))

    def test_conflicting_managed_text_fails_before_renaming_the_component(self):
        doc = design()
        part = doc.one(PART)
        part['Manufacturer'] = 'R1'
        shape = next(item for item in part.select('Shapes/Shape') if item['FontType'] == 2)
        row = shape.one('TextLine/pt')
        doc.references.bind(shape, part, Property(row, 'Manufacturer'))
        with self.assertRaisesRegex(ReferenceError, 'managed projection'):
            part['RefDes'] = 'R12'
        self.assertEqual(part['RefDes'], 'R1')
        self.assertEqual(row.values, ('R1',))

    def test_named_reference_mode_edit_preserves_existing_hierarchy_relationship(self):
        doc = design()
        part = doc.one(PART)
        part.set_field('PartType', 4)
        bind_schematic_references(doc)
        reference = doc.references.outgoing(part, role='hierarchy-page')[0]
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            part['PartType'] = 0
        self.assertEqual(part['PartType'], 4)
        self.assertIs(doc.references.get(reference.uid).target, doc.one('/Schematic/Pages/Page'))
        doc.references.discard(reference)
        part['PartType'] = 0

    def test_unresolved_hierarchy_mode_cannot_change_its_meaning_silently(self):
        doc = design()
        part = doc.one(PART)
        part.set_field('PartType', 4)
        part.set_field('Number1', 99)
        bind_schematic_references(doc)
        issue = next(item for item in doc.references.issues if item.source is part)
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            part['PartType'] = 0
        self.assertEqual(part['PartType'], 4)
        self.assertEqual(part['Number1'], 99)
        doc.references.discard_issue(issue)
        part['PartType'] = 0
