"""XML connection groups retain authored policy without retaining old caches."""
import unittest

from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.tests.test_dipxml_electrical import prepared
from lib.pcb.tests.test_dipxml_settings import source as settings_source


PAIRS = '<IntConRecords><Item X="17" Y="41"/></IntConRecords>'
GROUP = '''<InternalConnections><IntCon ConnectAll="Y"><PadId><Item>41</Item><Item>17</Item></PadId>
  <Ratlines><Ratline X="41" Y="17"/></Ratlines></IntCon></InternalConnections>'''


def source():
    return settings_source().replace('<Name>Device</Name>', '<Name>Device</Name>'+PAIRS+GROUP)


def design(text=None):
    return assemble_rules(prepared(source() if text is None else text)).document


class PcbXmlInternalConnectionTests(unittest.TestCase):
    def test_authored_pair_and_policy_resolve_nonconsecutive_public_pad_keys(self):
        document = design()
        component = document.one('/Board/Components/Component')
        first, second = component.select('Pattern/Pads/Pad')
        pair = component.one('IntConRecords/Item')
        self.assertIs(pair['Pad1'], first)
        self.assertIs(pair['Pad2'], second)
        policy = component.one('InternalConnections/IntCon')
        self.assertTrue(policy['ConnectAll'])
        self.assertEqual(set(policy['Members']), {first, second})
        self.assertEqual(policy['Ratlines'], ((first, second),))
        self.assertIsNone(policy.child('PadId'))
        self.assertIsNone(policy.child('Ratlines'))
        self.assertEqual((first['InternalConnection'], second['InternalConnection']), (0, 0))
        first.move_to(first.parent, 1)
        self.assertIs(pair['Pad1'], first)
        self.assertIs(pair['Pad2'], second)
        self.assertEqual(set(policy['Members']), {first, second})

    def test_stale_display_edges_do_not_replace_current_connectivity(self):
        document = design(source().replace('<Ratline X="41" Y="17"/>', '<Ratline X="999" Y="998"/>'))
        component = document.one('/Board/Components/Component')
        self.assertEqual(len(component.one('InternalConnections/IntCon')['Ratlines']), 1)
        self.assertTrue(component.one('InternalConnections/IntCon')['ConnectAll'])
        clone = document.clone()
        clone.one('/Board/Components/Component/InternalConnections/IntCon')['ConnectAll'] = False
        self.assertTrue(component.one('InternalConnections/IntCon')['ConnectAll'])

    def test_missing_group_policy_uses_default_and_equal_labels_derive_membership(self):
        document = design(source().replace(PAIRS+GROUP, '').replace('<Number>2</Number>', '<Number>1</Number>'))
        component = document.one('/Board/Components/Component')
        self.assertFalse(component.one('InternalConnections/IntCon')['ConnectAll'])
        self.assertEqual(len(component.one('InternalConnections/IntCon')['Members']), 2)
        self.assertFalse(component.one('IntConRecords').children())

    def test_unresolved_authored_members_and_contradictory_policy_are_explicit_limits(self):
        for before, after in (('X="17" Y="41"', 'X="17" Y="99"'),
                              ('<Item>41</Item>', '<Item>99</Item>'),
                              ('<Item>41</Item>', '<Item>4.5</Item>'),
                              ('ConnectAll="Y"', 'ConnectAll="Maybe"'),
                              (GROUP, GROUP.replace('</InternalConnections>',
                                '<IntCon ConnectAll="N"><PadId><Item>17</Item><Item>41</Item></PadId></IntCon></InternalConnections>'))):
            with self.subTest(after=after), self.assertRaises(ValueError):
                design(source().replace(before, after))

    def test_pair_and_policy_edits_use_existing_ownership_guards(self):
        document = design()
        pair = document.one('/Board/Components/Component/IntConRecords/Item')
        foreign = design().one('/Board/Components/Component/Pattern/Pads/Pad[1]')
        original = pair['Pad1']
        with self.assertRaises(ReferenceError):
            pair['Pad1'] = foreign
        self.assertIs(pair['Pad1'], original)
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
