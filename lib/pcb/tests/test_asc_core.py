"""ASC electrical data binds to the same PCB identities and edit constraints."""
import unittest
from decimal import Decimal

from lib.common.asc import loads, dumps
from lib.common.model import Document, Element
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.errors import PcbError
from lib.pcb.formats.import_context import ImportContext
from lib.pcb.tests.test_asc_components import SOURCE


def fixture(*, units='mil'):
    syntax = loads(SOURCE)
    part = syntax.one('/Component')
    part.add('HiddenId', -1)
    path = part.one('Hidden_Path')
    for row in path.children():
        row.detach()
    path.set_values(0)
    pads = part.one('Pads')
    first = pads.one('Pad')
    second = first.clone()
    second.set_argument(0, 2)
    second.one('Number').set_values(11)
    pads.append(second)
    for index in (0, 3):
        boundary = first.clone()
        boundary.set_argument(0, index)
        boundary.one('Number').set_values(-1)
        boundary.one('NetNumber').set_values(-1)
        pads.insert(boundary, 0) if index == 0 else pads.append(boundary)

    root = Element('')
    root.add('Source', 'DipTrace-PCBN', 53)
    root.add('Units', units)
    board = root.add('Board')
    part.move_to(board.add('Components'))
    net = board.add('Nets').add('Net', 'Supply')
    for name, value in dict(Number=73, Enabled='Y', HideConnections='N',
                            ViaSize=10, ViaRing=1, ThroughVia='Y').items():
        net.add(name, value)
    members = net.add('Component')
    members.add('pt', 17, 9)
    members.add('pt', 17, 11)
    net.add('Lines')
    return dumps(Document(root, representation='asc'), preserve=False)


class AscCoreTests(unittest.TestCase):
    def test_numeric_header_text_is_interpreted_before_lexical_cleanup(self):
        for token, expected in (('003', '003'), ('0', '0'), ('', '')):
            with self.subTest(token=token):
                text = fixture().replace('"Device" R003', '"Device" '+token)
                result = assemble_core(prepare_core(text))
                self.assertEqual(result.document.one('/Board/Components/Component')['RefDes'], expected)

    def test_ascii_membership_uses_current_identity_links_and_allows_data_edits(self):
        data = prepare_core(fixture())
        result = assemble_core(data)
        part, net = result.components[17], result.nets[73]
        self.assertEqual((part['Name'], part['RefDes']), ('Device', 'R003'))
        self.assertEqual(part['Value'], 'Y')  # Authored text is not a boolean flag.
        self.assertEqual([row['Pad'] for row in net.select('Pads/Item')],
                         [result.pads[17, 9], result.pads[17, 11]])
        self.assertTrue(all(pad['Net'] is net for pad in result.pads.values()))
        part['RefDes'] = 'R4'
        net['Name'] = 'Renamed supply'
        self.assertEqual(result.document.refdes('R').designators(), ['R4'])
        self.assertEqual(result.pads[17, 9]['Net']['Name'], 'Renamed supply')
        self.assertFalse(result.document.complete)
        self.assertIsNone(result.document.root.child('Source'))
        self.assertIsNone(net.child('ViaSize'))
        self.assertTrue(all(node._syntax is None for node in result.document.root.walk(include_self=True)))
        self.assertTrue(all(value.lexeme is None for node in result.document.root.walk(include_self=True)
                            for value in node.arguments))

    def test_stored_units_win_over_context_without_scaling_coordinates(self):
        result = assemble_core(prepare_core(fixture()), context=ImportContext(units='inch'))
        default = assemble_core(prepare_core(fixture())).components[17]
        self.assertEqual(result.document.root['Units'], 'mil')
        self.assertEqual((result.components[17]['X'], result.components[17]['Y']),
                         (default['X'], default['Y']))
        self.assertEqual(result.components[17]['Angle'], Decimal('7.854'))

    def test_source_version_does_not_apply_binary_geometry_gates_to_current_named_data(self):
        text = fixture().replace('PCBN" 53', 'PCBN" 31')
        data = prepare_core(text)
        result = assemble_core(data)
        self.assertEqual(data.source_version, 31)
        self.assertEqual(result.components[17].one('Pattern')['Width'], Decimal('4.5'))
        self.assertEqual(result.components[17]['Angle'], Decimal('7.854'))

    def test_conflicting_membership_and_bad_boolean_fail(self):
        text = fixture()
        with self.assertRaisesRegex(PcbError, 'boolean'):
            prepare_core(text.replace('(HideConnections "N")', '(HideConnections "invalid")'))
        with self.assertRaisesRegex(PcbError, 'unresolved saved net pad key'):
            assemble_core(prepare_core(text.replace('(pt 17 11)', '(pt 17 99)')))

    def test_other_ascii_families_do_not_enter_the_pcb_pipeline(self):
        with self.assertRaisesRegex(PcbError, 'source declaration'):
            prepare_core(fixture().replace('DipTrace-PCBN', 'DipTrace-Schematic'))


if __name__ == '__main__':
    unittest.main()
