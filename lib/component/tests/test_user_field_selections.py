"""Component fields are shared identities; template text remains independent."""
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.references import ReferenceError
from lib.component.formats import io
from lib.component.model import new_library, new_component, new_part, new_drawing


def example(*, fields=2, code=21):
    document = new_library('Example')
    component = document.one('/Library/Components').append(new_component('Device', 'U'))
    users = component.one('UserFields')
    for index in range(fields):
        users.add('UserField', f'Field{index}', f'Value{index}', 0)
    first = component.one('Parts/Part')
    second = component.one('Parts').append(new_part('Gate B'))
    shapes = []
    for index, part in enumerate((first, second)):
        shape = new_drawing(kind=10)
        shape['FontType'] = code
        shape.one('TextLine').add('pt', f'Template{index}')
        shape.one('Points_New').add('pt', 0, 0)
        part.one('Shapes').append(shape)
        shapes.append(shape)
    return document, component, users.children('UserField'), shapes


class UserFieldSelectionTests(unittest.TestCase):
    def test_both_parts_follow_reorder_rename_and_retarget_without_text_refresh(self):
        document, _, fields, shapes = example()
        self.assertTrue(all(shape['UserField'] is fields[1] for shape in shapes))
        fields[1].move_to(fields[1].parent, index=0)
        fields[1]['Name'], fields[1]['Value'] = 'Renamed', 'Changed'
        self.assertEqual([20, 20], [shape['FontType'] for shape in shapes])
        shapes[0]['UserField'] = fields[0]
        self.assertEqual([21, 20], [shape['FontType'] for shape in shapes])
        self.assertEqual(['Template0', 'Template1'], [shape.one('TextLine/pt')['Text'] for shape in shapes])
        with self.assertRaises(ReferenceError):
            fields[1].detach()
        document.validate()

    def test_named_activation_literal_choices_and_optional_recreation(self):
        document, _, fields, shapes = example(code=0)
        shape = shapes[0]
        shape['FontType'] = 21
        self.assertIs(fields[1], shape['UserField'])
        with self.assertRaises(ValueError):
            shape['FontType'] = 0
        shape['UserField'] = None
        self.assertEqual(0, shape['FontType'])
        shape['FontType'] = 1
        self.assertIsNone(shape['UserField'])
        shape['UserField'] = None
        self.assertEqual(1, shape['FontType'])
        del shape['FontType']
        shape['UserField'] = fields[0]
        self.assertEqual(20, shape['FontType'])
        self.assertEqual('Template0', shape.one('TextLine/pt')['Text'])
        document.validate()

    def test_wrong_scope_assignment_and_moves_are_atomic(self):
        document, component, fields, shapes = example(code=0)
        foreign = document.one('/Library/Components').append(new_component('Other', 'U'))
        unavailable = foreign.one('UserFields').add('UserField', 'Other', 'Other', 0)
        shape = shapes[0]
        del shape['FontType']
        before = model_text(document)
        with self.assertRaises(ReferenceError):
            shape['UserField'] = unavailable
        self.assertEqual(before, model_text(document))
        self.assertIsNone(shape.child('FontType'))
        shape['UserField'] = fields[0]
        before = model_text(document)
        with self.assertRaises(ReferenceError):
            shape.move_to(foreign.one('Parts/Part/Shapes'))
        self.assertEqual(before, model_text(document))
        self.assertIs(component.one('Parts/Part[1]/Shapes'), shape.parent)
        document.validate()

    def test_clone_and_copy_map_owned_fields_but_share_external_selections(self):
        document, component, fields, shapes = example()
        copied_shape = document.copy(shapes[0], parent=shapes[1].parent)
        self.assertIs(fields[1], copied_shape['UserField'])
        copied_component = document.copy(component)
        copied_field = copied_component.one('UserFields/UserField[2]')
        self.assertTrue(all(shape['UserField'] is copied_field
                            for shape in copied_component.select('Parts/Part/Shapes/Shape')))
        self.assertIsNot(fields[1], copied_field)
        clone = document.clone()
        self.assertIs(clone.one(fields[1].path), clone.one(shapes[0].path)['UserField'])
        document.remove(copied_shape)
        document.validate()
        clone.validate()

    def test_copy_with_a_new_scalar_selection_activates_its_relationship(self):
        document, _, fields, shapes = example(code=0)
        copied = document.copy(shapes[0], fields={'FontType': 20})
        self.assertIs(fields[0], copied['UserField'])
        self.assertIsNone(shapes[0]['UserField'])
        document.validate()

    def test_unavailable_selection_survives_every_output_without_rewriting_text(self):
        document, _, _, shapes = example(fields=1, code=42)
        before = model_text(document)
        self.assertEqual(2, len(document.references.issues))
        with self.assertRaises(ReferenceError):
            _ = shapes[0]['UserField']
        for format in ('eli', 'asc', 'elixml'):
            with self.subTest(format=format):
                current = document
                for _ in range(3):
                    report = ConversionReport()
                    current = io.parse(io.serialize(current, format=format, report=report), report=report)
                    rebuilt = current.select('/Library/Components/Component/Parts/Part/Shapes/Shape')
                    self.assertEqual([42, 42], [shape['FontType'] for shape in rebuilt])
                    self.assertEqual(['Template0', 'Template1'],
                                     [shape.one('TextLine/pt')['Text'] for shape in rebuilt])
                    self.assertEqual(2, len(current.references.issues))
                    self.assertEqual([], report.errors)
                    self.assertTrue(report.warnings)
        self.assertEqual(before, model_text(document))
        document.validate()

    def test_missing_selection_guards_scope_and_can_be_resolved_or_cleared(self):
        for clear in (False, True):
            with self.subTest(clear=clear):
                document, component, fields, shapes = example(fields=1, code=42)
                users = component.one('UserFields')
                before = model_text(document)
                with self.assertRaises(ReferenceError):
                    users.add('UserField', 'Extra', 'Extra', 0)
                with self.assertRaises(ReferenceError):
                    shapes[0]['Type'] = 1
                self.assertEqual(before, model_text(document))
                for shape in shapes:
                    shape['UserField'] = None if clear else fields[0]
                    self.assertEqual(0 if clear else 20, shape['FontType'])
                self.assertEqual([], document.references.issues)
                users.add('UserField', 'Extra', 'Extra', 0)
                document.validate()

    def test_type_changes_activate_or_guard_selected_text(self):
        document, _, fields, shapes = example(code=0)
        shape = shapes[0]
        shape['Type'] = 1
        shape['FontType'] = 20
        self.assertIsNone(shape['UserField'])
        shape['Type'] = 10
        self.assertIs(fields[0], shape['UserField'])
        before = model_text(document)
        with self.assertRaises(ReferenceError):
            shape['Type'] = 1
        self.assertEqual(before, model_text(document))
        shape['UserField'] = None
        shape['Type'] = 1
        document.validate()

    def test_edited_references_round_trip_in_all_three_formats(self):
        document, _, fields, shapes = example()
        fields[1].move_to(fields[1].parent, index=0)
        fields[1]['Name'] = 'Selected'
        shapes[0]['UserField'] = fields[0]
        for format in ('eli', 'asc', 'elixml'):
            with self.subTest(format=format):
                current = io.parse(io.serialize(document, format=format, report=ConversionReport()))
                output = current.select('/Library/Components/Component/Parts/Part/Shapes/Shape')
                self.assertEqual([21, 20], [shape['FontType'] for shape in output])
                self.assertEqual(['Field0', 'Selected'], [shape['UserField']['Name'] for shape in output])
                current.validate()


if __name__ == '__main__':
    unittest.main()
