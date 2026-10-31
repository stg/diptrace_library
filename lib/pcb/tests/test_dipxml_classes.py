"""XML routing rules share the editable layer/style/class identity graph."""
from decimal import Decimal
import unittest

from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.tests.test_dipxml_electrical import prepared
from lib.pcb.tests.test_dipxml_layers import source as layer_source


CLASSES = '''<NetClasses>
  <NetClass Id="4" UpdateId="80" AllLayers="Y"><Name>Default</Name>
    <LayProperties><LayProperty Width="0.3" Clearance="0.2"/></LayProperties>
  </NetClass>
  <NetClass Id="70" Type="Differential Pair" AllLayers="N" AllVias="N"
      Phase="2.5" Tolerance="0.25"><Name>Special</Name>
    <LayProperties>
      <LayProperty Width="0.3"><LayerName>Bottom</LayerName><ClearanceDetails TraceToVia="0.2"/></LayProperty>
      <LayProperty Width="0.2" Neck_MaxLength="0.5"><LayerName>Top</LayerName></LayProperty>
      <LayProperty Width="0.25"><LayerName>Inner</LayerName></LayProperty>
    </LayProperties>
    <AllowedVias><ViaStyle>17</ViaStyle><ViaStyle>62</ViaStyle></AllowedVias>
    <Autorouting RouteAllLayers="N" MaxIncorrectWayValue="12.5">
      <RouteLayers><Item>Y</Item><Item>N</Item><Item>Y</Item></RouteLayers>
    </Autorouting>
  </NetClass>
</NetClasses>'''


def source():
    return layer_source().replace('<Components>', CLASSES+'<Components>', 1).replace(
        'Net Id="7"', 'Net Id="7" NetClass="70"')


class PcbXmlClassTests(unittest.TestCase):
    def test_named_per_layer_properties_and_permissions_use_shared_model_links(self):
        result = assemble_rules(prepared(source()))
        board, net = result.document.one('/Board'), result.routing.core.nets[7]
        default, special = result.classes.values()
        self.assertIs(net['Class'], special)
        self.assertEqual(net['NetClass'], 1)
        self.assertEqual((special['Phase'], special['Tolerance']), (Decimal('7.5'), Decimal('.75')))
        self.assertEqual(default['HiddenID'], 80)
        self.assertEqual(special['MaxIncorrectWayValue'], Decimal('12.5'))
        rows = special.select('LayProperties/LayProperty')
        self.assertEqual([row['LayerName'] for row in rows], ['Top', 'Inner', 'Bottom'])
        self.assertEqual([row['Width'] for row in rows], [Decimal('.6'), Decimal('.75'), Decimal('.9')])
        self.assertEqual(rows[0]['Neck_MaxLength'], Decimal('1.5'))
        self.assertEqual(rows[2].one('ClearanceDetails')['TraceToVia'], Decimal('.6'))
        self.assertEqual([item['Via'] for item in special.select('AllowedVias/ViaStyle')],
                         [result.via_styles[1], result.via_styles[0]])
        self.assertEqual([item['Layer'] for item in special.select('RouteLayers/Item')], list(result.layers.values()))
        self.assertEqual([item['Enabled'] for item in special.select('RouteLayers/Item')], [True, False, True])
        self.assertIsNone(default.one('LayProperties/LayProperty')['Layer'])
        self.assertIs(board['DefaultClass'], default)

    def test_edits_follow_identity_and_reject_invalid_removal(self):
        result = assemble_rules(prepared(source()))
        default, special = result.classes.values()
        net = result.routing.core.nets[7]
        special.move_to(special.parent, 0)
        self.assertIs(net['Class'], special)
        self.assertEqual(net['NetClass'], 0)
        layer = result.layers[2]
        layer['Name'] = 'Back'
        row = special.one('LayProperties/LayProperty[3]')
        self.assertEqual(row['LayerName'], 'Back')
        row['Width'] = 2
        self.assertEqual(row['Width'], 2)
        with self.assertRaises(ReferenceError):
            result.document.remove(special)
        self.assertIs(net['Class'], special)

    def test_missing_optional_limits_have_verified_import_defaults(self):
        result = assemble_rules(prepared(source()))
        default = result.classes[0]
        self.assertTrue(default['AllVias'])
        self.assertEqual((default['Phase'], default['Phase_ErrorLength'], default['LengthDelta']),
                         (6, 15, Decimal('7.62')))
        self.assertEqual(default['FixedLength'], -1)
        for name in ('MinLength', 'MaxLength'):
            self.assertNotIn(name, default.schema.fields)
            self.assertIsNone(default.child(name))
        row = default.one('LayProperties/LayProperty')
        self.assertEqual((row['MinWidth'], row['MaxWidth'], row['Neck_Width']), (Decimal('.03'), 300, -1))
        # XML's property loader overrides the constructor's zero default.
        self.assertEqual(row['Neck_MaxLength'], -1)

    def test_display_units_scale_lengths_but_not_the_autorouting_limit_scalar(self):
        result = assemble_rules(prepared(source().replace('Units="mm"', 'Units="mil"')))
        special = result.classes[1]
        self.assertEqual(special['Phase'], Decimal('.19050'))
        self.assertEqual(special['MaxIncorrectWayValue'], Decimal('12.5'))
        self.assertEqual(special.schema.fields['MaxIncorrectWayValue'].unit, '')

    def test_unknown_ids_ambiguous_layer_names_and_invalid_flags_fail(self):
        for before, after in (('NetClass="70"', 'NetClass="71"'),
                              ('<ViaStyle>17</ViaStyle>', '<ViaStyle>19</ViaStyle>'),
                              ('<LayerName>Bottom</LayerName>', '<LayerName>Top</LayerName>'),
                              ('<Item>N</Item>', '<Item>Maybe</Item>'),
                              ('<Item>N</Item>', ''),
                              ('NetClass Id="70"', 'NetClass Id="4"'),
                              ('Neck_MaxLength="0.5"', 'UnexpectedRule="5"')):
            with self.subTest(after=after), self.assertRaises(ValueError):
                prepared(source().replace(before, after))


if __name__ == '__main__':
    unittest.main()
