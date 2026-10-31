"""ASC hierarchy uses persistent block identities, independently of RefDes text."""
import unittest

from lib.common.asc import loads, dumps
from lib.common.model import Value
from lib.common.references import ReferenceError
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.errors import PcbError
from lib.pcb.model.hierarchy import BLOCK_ROLE, linkage_path
from lib.pcb.tests.test_asc_core import fixture


def source():
    syntax = loads(fixture())
    board = syntax.one('/Board')
    component = board.one('Components/Component')
    component.one('HiddenId').set_values(75)
    path = component.one('Hidden_Path')
    path.set_values(3)
    for key in (91, 107, 75):
        path.add('pt', key)
    sheets = board.add('Hierarchy_Sheets')
    sheets.add('HSheet', 'Controller', 12).add('pt', 91, 'Top block')
    sheets.add('HSheet', 'Channel', 117).add('pt', 107, 'Nested block')
    return dumps(syntax, preserve=False)


class AscHierarchyTests(unittest.TestCase):
    def test_path_and_sheet_blocks_share_the_existing_identity_model(self):
        result = assemble_core(prepare_core(source()))
        component = result.components[17]
        document = result.document
        self.assertEqual(linkage_path(component), (91, 107, 75))
        sheets = document.select('/Board/HierarchySheets/HSheet')
        self.assertEqual([(sheet['Name'], sheet['Number']) for sheet in sheets],
                         [('Controller', 12), ('Channel', 117)])
        blocks = document.select('/Board/HierarchySheets/HSheet/UpdateIds/UId')
        steps = component.select('HierarchyPath/Item')
        for step, block in zip(steps, blocks):
            link, = document.references.outgoing(step, role=BLOCK_ROLE)
            self.assertIs(link.target, block)
        blocks[0]['Id'] = 104
        component['HiddenId'] = 80
        self.assertEqual(linkage_path(component), (104, 107, 80))
        sheets[0].move_to(sheets[0].parent)
        self.assertEqual(linkage_path(component), (104, 107, 80))
        self.assertIsNone(document.one('/Board').child('Hierarchy_Sheets'))
        self.assertIsNone(component.child('Hidden_Path'))
        self.assertEqual([row['Id'] for row in steps], [104, 107])
        with self.assertRaises(ReferenceError):
            blocks[1]['Id'] = 104
        self.assertEqual(blocks[1]['Id'], 107)

    def test_unknown_block_is_explicit_without_companion_discovery(self):
        result = assemble_core(prepare_core(source().replace('(pt 91 "Top block")', '')))
        step = result.components[17].one('HierarchyPath/Item[1]')
        self.assertTrue(result.document.references.unresolved_slot(step))
        self.assertEqual(step['Id'], 91)
        self.assertEqual(len(result.document.references.issues), 1)

    def test_imported_duplicate_labels_keep_independent_components_and_links(self):
        syntax = loads(source())
        components = syntax.one('/Board/Components')
        first = components.one('Component')
        first.set_argument(1, Value('D13_3', 'symbol'))
        second = first.clone()
        second.one('Number').set_values(18)
        second.one('HiddenId').set_values(804)
        path = second.one('Hidden_Path')
        for row in tuple(path.children()):
            row.detach()
        path.set_values(0)
        components.append(second)
        result = assemble_core(prepare_core(dumps(syntax, preserve=False)))
        first, second = result.components.values()
        self.assertEqual(result.document.refdes('D13_').matches('D13_3'), [first, second])
        self.assertEqual(linkage_path(first), (91, 107, 75))
        self.assertEqual(linkage_path(second), ())
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            second['RefDes'] = 'D13_003'
        second['RefDes'] = 'D14'
        self.assertEqual(first['RefDes'], 'D13_3')

    def test_malformed_or_duplicate_vocabulary_is_rejected(self):
        for before, after, message in (
            ('(Hierarchy_Sheets', '(HierarchySheets) (Hierarchy_Sheets', 'ambiguous'),
            ('(HSheet "Controller" 12', '(HSheet "Controller" 1.2', 'sheet name and identifier'),
            ('(pt 91 "Top block")', '(pt "91" "Top block")', 'block identifier and name'),
            ('(pt 91 "Top block")', '(pt 91 "Top block" (extra 1))', 'block identifier and name'),
            ('(HSheet "Controller" 12', '(HSheet "Controller" 12 (UpdateIds)', 'block identifier and name'),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(PcbError, message):
                prepare_core(source().replace(before, after))

    def test_terminal_component_identity_is_still_checked(self):
        with self.assertRaisesRegex(PcbError, 'terminal'):
            assemble_core(prepare_core(source().replace('(pt 75)', '(pt 999)')))


if __name__ == '__main__':
    unittest.main()
