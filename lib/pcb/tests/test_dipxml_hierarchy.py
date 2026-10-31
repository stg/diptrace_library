"""XML hierarchy paths share the DIP/ASC model and reference maintenance."""
import unittest

from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.model.hierarchy import BLOCK_ROLE, linkage_path
from lib.pcb.tests.test_dipxml_electrical import prepared
from lib.pcb.tests.test_dipxml_settings import source as settings_source


SHEETS = '''<HierarchySheets>
  <HSheet Number="6"><Name>Input</Name><UpdateIds>
    <UId Name="93"><Name>Block 1</Name></UId></UpdateIds></HSheet>
  <HSheet Number="42"><Name>Control</Name><UpdateIds>
    <UId Name="700"><Name>Nested</Name></UId></UpdateIds></HSheet>
</HierarchySheets>'''
PATH = '<HierarchyPath><Item>93</Item><Item>700</Item><Item>77</Item></HierarchyPath>'


def source():
    return settings_source().replace('<Board>', '<Board>'+SHEETS, 1).replace(
        '<Name>Device</Name>', '<Name>Device</Name>'+PATH)


def design(text=None):
    return assemble_rules(prepared(source() if text is None else text)).document


class PcbXmlHierarchyTests(unittest.TestCase):
    def test_import_consumes_the_repeated_terminal_and_preserves_named_block_keys(self):
        document = design()
        component = document.one('/Board/Components/Component')
        sheets = document.select('/Board/HierarchySheets/HSheet')
        self.assertEqual([(s['Name'], s['Number']) for s in sheets], [('Input', 6), ('Control', 42)])
        blocks = document.select('/Board/HierarchySheets/HSheet/UpdateIds/UId')
        self.assertEqual([(b['Id'], b['Name']) for b in blocks], [(93, 'Block 1'), (700, 'Nested')])
        self.assertEqual([s['Id'] for s in component.select('HierarchyPath/Item')], [93, 700])
        self.assertEqual(linkage_path(component), (93, 700, 77))
        self.assertIs(document.references.outgoing(component.one('HierarchyPath/Item[2]'), role=BLOCK_ROLE)[0].target,
                      blocks[1])
        self.assertEqual(component['RefDes'], 'U1')

    def test_key_edits_and_reordering_remain_coherent_without_a_companion_file(self):
        document = design()
        component = document.one('/Board/Components/Component')
        sheets = document.select('/Board/HierarchySheets/HSheet')
        sheets[1].move_to(sheets[0].parent, 0)
        block = sheets[0].one('UpdateIds/UId')
        block['Id'] = 400
        block['Name'] = 'Renamed'
        self.assertEqual(linkage_path(component), (400, 700, 77))
        self.assertEqual(component['RefDes'], 'U1')
        with self.assertRaises(ReferenceError):
            block['Id'] = 700
        self.assertEqual(block['Id'], 400)
        document.references.validate()

    def test_unavailable_block_keys_remain_explicit_current_references(self):
        document = design(source().replace('<Item>700</Item>', '<Item>701</Item>'))
        component = document.one('/Board/Components/Component')
        step = component.one('HierarchyPath/Item[2]')
        self.assertEqual(step['Id'], 701)
        self.assertTrue(document.references.unresolved_slot(step))
        self.assertEqual(len(document.references.issues), 1)
        clone = document.clone()
        self.assertEqual(linkage_path(clone.one('/Board/Components/Component')), (93, 701, 77))

    def test_syntactically_invalid_and_contradictory_links_fail(self):
        for before, after in (('<Item>700</Item>', '<Item>7.5</Item>'),
                              ('UId Name="93"', 'UId Name="no key"'),
                              ('<Item>77</Item>', '<Item>78</Item>'),
                              ('<Name>Block 1</Name>', '<Name>A</Name><Name>B</Name>')):
            with self.subTest(after=after), self.assertRaises(ValueError):
                design(source().replace(before, after))


if __name__ == '__main__':
    unittest.main()
