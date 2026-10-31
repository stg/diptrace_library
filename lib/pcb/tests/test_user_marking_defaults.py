"""Current custom fields supply missing global display categories naturally."""
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.marking_defaults import complete_user_markings
from lib.pcb.model.objects import new_component, new_document, new_user_field
from lib.pcb.tests.test_dipxml_library import read, source as library_source


PATH = '/Board/Userfields_Global/UserField'


def xml_source(names):
    root = ElementTree.fromstring(library_source())
    component = root.find('Board/Components/Component')
    fields = component.find('AddFields')
    if fields is None:
        fields = ElementTree.SubElement(component, 'AddFields')
    fields.clear()
    for index, name in enumerate(names):
        field = ElementTree.SubElement(fields, 'AddField', dict(Name=name, Type='Text'))
        ElementTree.SubElement(field, 'Text').text = 'Content '+str(index)
    return ElementTree.tostring(root, encoding='unicode')


def add_rule(board, name, *, show=1, align=4):
    fields = board.child('Userfields_Global')
    if fields is None:
        fields = board.add('Userfields_Global')
    row = fields.add('UserField')
    row['Name'] = name
    for side in ('Silk', 'Assy'):
        row[side+'Show'], row[side+'Align'] = show, align
    return row


def signature(document):
    return [(row['Name'], row['Value'], row['SilkShow'], row['SilkAlign'],
             row['AssyShow'], row['AssyAlign']) for row in document.select(PATH)]


class UserMarkingDefaultTests(unittest.TestCase):
    def test_import_collects_names_in_order_and_normalizes_only_blank_names(self):
        report = ConversionReport()
        document = read(xml_source(('Order Code', 'ordercode', ' ', '', '\t', 'Revision')),
                        report=report)
        self.assertEqual(signature(document), [
            ('Order Code', 'ordercode', 2, 7, 2, 7),
            ('Untitled', 'untitled', 2, 7, 2, 7),
            ('\t', '\t', 2, 7, 2, 7),
            ('Revision', 'revision', 2, 7, 2, 7)])
        fields = document.select('/Board/Components/Component/UserFields/UserField')
        self.assertEqual([field['Name'] for field in fields],
                         ['Order Code', 'ordercode', 'Untitled', 'Untitled', '\t', 'Revision'])
        self.assertEqual([field['Value'] for field in fields], ['Content '+str(i) for i in range(6)])
        notices = {n.rule: n for n in report.infos}
        for rule in ('empty-user-field-name', 'user-field-marking-defaults'):
            self.assertEqual((notices[rule].operation, notices[rule].format), ('import', 'dipxml'))
        self.assertFalse(any(n.rule in ('empty-user-field-name', 'user-field-marking-defaults')
                             for n in report.warnings))

    def test_explicit_unused_and_repeated_rules_keep_their_settings_and_order(self):
        document = new_document()
        board = document.one('/Board')
        for name, show in (('Unused', 1), ('ORDER Code', 0), ('OrderCode', 1)):
            add_rule(board, name, show=show)
        component = board.one('Components').append(new_component('Device', 'U1'))
        for name in ('order code', 'Revision', 'r e v i s i o n'):
            component.one('UserFields').append(new_user_field(name, 'Unchanged'))
        renamed, added = complete_user_markings(board)
        self.assertEqual(renamed, [])
        self.assertEqual([row['Name'] for row in added], ['Revision'])
        self.assertEqual(signature(document), [
            ('Unused', 'unused', 1, 4, 1, 4), ('ORDER Code', 'ordercode', 0, 4, 0, 4),
            ('OrderCode', 'ordercode', 1, 4, 1, 4), ('Revision', 'revision', 2, 7, 2, 7)])
        self.assertEqual(complete_user_markings(board), ([], []))

    def test_disabled_components_and_cached_definition_fields_are_not_collected(self):
        document = read(xml_source(()), report=ConversionReport())
        self.assertEqual(document.select(PATH), [])
        document = new_document()
        component = document.one('/Board/Components').append(new_component('Device', 'U1'))
        component['Enabled'] = False
        component.one('UserFields').append(new_user_field('', 'Still unnamed'))
        self.assertEqual(complete_user_markings(document.one('/Board')), ([], []))
        self.assertEqual(document.select(PATH), [])
        self.assertEqual(component.one('UserFields/UserField')['Name'], '')

    def test_all_outputs_complete_new_fields_on_a_detached_view_and_stabilize(self):
        document = read(xml_source(('Order',)), report=ConversionReport())
        component = document.one('/Board/Components/Component')
        field = component.one('UserFields').append(new_user_field(' ', 'An authored value'))
        field['SilkShow'], field['SilkX'] = 1, 12
        add_rule(document.one('/Board'), 'Unused', show=0)
        before = dumps(document, preserve=False)
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                report = ConversionReport()
                data = io.serialize(document, format=format, report=report)
                current = io.parse(data, report=ConversionReport())
                self.assertEqual(signature(current), [
                    ('Order', 'order', 2, 7, 2, 7), ('Unused', 'unused', 0, 4, 0, 4),
                    ('Untitled', 'untitled', 2, 7, 2, 7)])
                saved = current.one('/Board/Components/Component/UserFields/UserField[2]')
                self.assertEqual((saved['Name'], saved['Value'], saved['SilkShow'], saved['SilkX']),
                                 ('Untitled', 'An authored value', 1, 12))
                self.assertTrue(any(n.rule == 'user-field-marking-defaults' and n.operation == 'export'
                                    for n in report.infos))
                again = io.parse(io.serialize(current, format=format, report=ConversionReport()),
                                 report=ConversionReport())
                self.assertEqual(signature(again), signature(current))
                self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
