"""PCB XML placement and footprint data use shared physical model records."""
from decimal import Decimal
from types import SimpleNamespace
import unittest

from lib.common.model import Element
from lib.common.units import XmlUnits
from lib.common.xml_records import XmlRecord
from lib.common import footprint_records
from lib.pcb.model.definitions import PATTERN
from lib.pcb.formats.dipxml.syntax import loads
from lib.pcb.formats.dipxml.patterns import read_patterns
from lib.pcb.formats.dipxml.components import read_component
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.errors import PcbError


SOURCE = '''<Source Type="DipTrace-PCB" Version="5.3" Units="mm">
<Library Type="DipTrace-PatternLibrary" Version="5.3" Units="mm">
  <PadStyles><PadStyle Name="S" Type="Surface" Side="Top">
    <MainStack Shape="Rectangle" Width="1.2" Height="2.4" Corner="0"/>
  </PadStyle></PadStyles>
  <Patterns><Pattern PatternStyle="P" RefDes="U" Type="Free" Width="5" Height="3">
    <Name>Package</Name><DefPad Style="S"/>
    <Pads><Pad Id="17" Style="S" X="1" Y="-2"><Number>1</Number></Pad>
          <Pad Id="41" Style="S" X="-1" Y="2"><Number>2</Number></Pad></Pads>
    <Shapes><Shape Id="9" Type="Polyline" Layer="Top Silk">
      <Points><Item X="0" Y="1"/><Item X="2" Y="-1"/></Points>
    </Shape></Shapes>
    <Model3D Units="mm" Type="File"><Rotate X="0" Y="0" Z="0"/>
      <Offset X="1" Y="-2" Z="3"/><Zoom X="1" Y="1" Z="1"/></Model3D>
  </Pattern></Patterns>
</Library>
<Board><CopperLayers><Lay Id="0"><Name>Top</Name></Lay>
  <Lay Id="1"><Name>Bottom</Name></Lay></CopperLayers><Components>
  <Component Id="8" UpdateId="77" PatternStyle="P" X="10" Y="-20" Angle="7.8"
       Side="Bottom" Flip="Y" HorzFlip="Y" GridAlign="Pad" MarkingFontSize="5" MarkingFontSizeFloat="5.25">
    <Name>Device</Name><RefDes>U1</RefDes><Value>10K</Value>
    <RefDesMarking><Silk Show="Show" Align="Position" Horz="Left" Vert="Top" X="1" Y="2" Angle="1.1"/>
      <Assy Show="Common" Align="Common" Horz="Center" Vert="Bottom" X="0" Y="0"/></RefDesMarking>
    <LibPath><Path>parts.lib</Path><Var>${PARTS}/parts.lib</Var></LibPath>
    <Pads><Pad Id="17" NetId="7" InternalConnection="-1">
      <TeardropParams Smd="1" SmdWidth="20" SmdLength="0.75"/></Pad>
      <Pad Id="41" NetId="-1" InternalConnection="-1"/></Pads>
  </Component>
</Components></Board></Source>'''


def prepared(text=SOURCE, *, units=None):
    syntax = loads(text)
    source = syntax.one('/Source')
    units = units or XmlUnits(source.scalar('Units'))
    library = XmlRecord(source.one('Library'))
    patterns, _ = read_patterns(library, units=units)
    component = read_component(XmlRecord(source.one('Board/Components/Component')), patterns=patterns, units=units)
    return patterns, component


def core():
    patterns, placed = prepared()
    root = Element('')
    root.add('Units', 'mm')
    board = root.add('Board')
    board.add('DesignCache_Count', -1)
    board.add('Components').append(placed.component)
    net = board.add('Nets').add('Net', 'Supply')
    net.add('Number', 7)
    net.add('Enabled', True)
    net.add('Pads').add('Item', 8, placed.pad_positions[17])
    net.add('Traces')
    return assemble_core(SimpleNamespace(root=root, board=board)), patterns


class PcbXmlComponentTests(unittest.TestCase):
    def test_placed_mask_paste_override_does_not_modify_the_physical_template(self):
        text = SOURCE.replace('<TeardropParams Smd=', '<MaskPaste CustomSwell="0" CustomShrink="0"/>'
                              '<TeardropParams Smd=', 1)
        patterns, placed = prepared(text)
        index = placed.pad_positions[17]
        pad = placed.component.one('Pattern/Pads').children('Pad')[index]
        self.assertEqual((pad['CustomSwell_New'], pad['CustomShrink_New']), (0, 0))
        template = next(iter(patterns.values())).element.one('Pads').children('Pad')[index]
        self.assertEqual((template['CustomSwell_New'], template['CustomShrink_New']), (-1000, -1000))

    def test_custom_field_owns_its_silk_and_assembly_markings_directly(self):
        text = SOURCE.replace('<Value>10K</Value>', '''<Value>10K</Value>
          <AddFields><AddField Type="Text"><Name>Revision</Name><Text>A</Text>
            <Silk Show="Show" Align="Position" X="2" Y="3" Angle="0.5"/>
            <Assy Show="Hide" Align="Center"/></AddField></AddFields>''')
        _, placed = prepared(text)
        field = placed.component.one('UserFields/UserField')
        self.assertEqual(field.values, ('Revision', 'A', 0))
        self.assertEqual((field['SilkShow'], field['SilkAlign'], field['SilkX'], field['SilkY']), (1, 8, 6, -9))
        self.assertEqual((field['SilkAngle'], field['AssyShow'], field['AssyAlign']), (Decimal('.5'), 2, 1))

    def test_shared_footprints_and_unit_axis_conversion(self):
        patterns, placed = prepared()
        template = patterns['P'].element
        pad = placed.component.one('Pattern/Pads/Pad[2]')
        self.assertIs(template.schema, PATTERN)
        self.assertIs(template.schema.fields['PadWidth'], footprint_records.PATTERN.fields['PadWidth'])
        self.assertIs(pad.schema, footprint_records.PAD)
        self.assertEqual((pad['X'], pad['Y'], pad['PadWidth_New'], pad['PadHeight_New']),
                         (Decimal('-2.4'), 6, Decimal('3.6'), Decimal('7.2')))
        self.assertEqual(template.one('Pads/Pad[2]')['X'], 3)
        self.assertEqual(template.one('Model3D/Offset').values, ())
        self.assertEqual(template.one('Model3D/Offset')['Y'], 6)
        self.assertEqual(placed.pad_positions, {17: 1, 41: 2})
        self.assertEqual(template.one('Pads/Pad[2]').get('NetNumber'), None)
        self.assertEqual(pad['NetNumber'], 7)

    def test_placement_angles_marks_and_paths_remain_independent_data(self):
        _, placed = prepared()
        component = placed.component
        for name, expected in dict(X=30, Y=60, Angle=Decimal('7.8'), HiddenId=77,
                BottomSide=True, Flipped=True, HorizontalFlip=True, GsType=0,
                MarkingFontSize=Decimal('5.25'), RefDes_SilkShow=1, RefDes_SilkAlign=8,
                RefDes_SilkHorz=-1, RefDes_SilkVert=-1, RefDes_SilkX=3, RefDes_SilkY=-6,
                RefDes_SilkAngle=Decimal('1.1'), LibPath='parts.lib', LibPath_Variable='${PARTS}/parts.lib',
                BaseName='Package').items():
            with self.subTest(name=name):
                self.assertEqual(component[name], expected)
        self.assertEqual(component.one('Pattern/Pads/Pad[2]/TeardropParams')['SmdWidth'], 20)

    def test_component_template_defaults_and_instance_overrides_are_distinct(self):
        text = SOURCE.replace('<Name>Package</Name>', '<Name>Package</Name><Value>Template value</Value>')
        patterns, placed = prepared(text)
        self.assertEqual(patterns['P'].defaults['Value'], 'Template value')
        self.assertEqual(placed.component['Value'], '10K')
        _, inherited = prepared(text.replace('<Value>10K</Value>', ''))
        self.assertEqual(inherited.component['Value'], 'Template value')
        _, cleared = prepared(text.replace('<Value>10K</Value>', '<Value/>'))
        self.assertEqual(cleared.component['Value'], '')
        self.assertIsNone(placed.component.one('Pattern').child('Value'))
        self.assertIsNone(placed.component.one('Pattern').child('RefDes'))
        self.assertIsNone(placed.component.one('Pattern').child('Pattern_Manufacturer'))

    def test_template_manufacturer_is_component_metadata_and_missing_clearance_inherits(self):
        text = SOURCE.replace('<Name>Package</Name>', '<Name>Package</Name><Manufacturer>Maker</Manufacturer>')
        _, placed = prepared(text)
        self.assertEqual(placed.component['Manufacturer'], 'Maker')
        self.assertEqual(placed.component['PlacementClearance'], -1)
        self.assertEqual(placed.component['ShowFiducial'], 0)

    def test_special_instance_type_and_component_classification_do_not_change_template(self):
        text = SOURCE.replace('Id="8" UpdateId=', 'Type="Pad" Id="8" UpdateId=')
        text = text.replace('<Value>10K</Value>', '<Value>10K</Value><Category Index="4"><Name>Board item</Name></Category>')
        patterns, placed = prepared(text)
        self.assertEqual((patterns['P'].element['Type'], placed.component.one('Pattern')['Type']), (0, 14))
        self.assertEqual(placed.component['Component_CategoryName'], 'Board item')
        self.assertEqual(placed.component['Component_CategoryIndex'], 4)
        self.assertEqual(patterns['P'].element['Pattern_CategoryIndex'], -1)

    def test_xml_pad_keys_enter_the_existing_electrical_identity_assembly(self):
        result, patterns = core()
        document, component, net = result.document, result.components[8], result.nets[7]
        first = result.pads[8, 1]
        self.assertIs(first['Net'], net)
        self.assertIs(net.one('Pads/Item')['Pad'], first)
        # The asymmetric drawing shifts the installed local frame by 0.6.
        self.assertEqual(first['X'], -patterns['P'].element.one('Pads/Pad[2]')['X']+Decimal('.6'))
        component['RefDes'] = 'U7'
        net['Name'] = 'Renamed'
        self.assertEqual((first['Net']['Name'], document.refdes('U').designators()), ('Renamed', ['U7']))
        self.assertIsNone(first.child('Number_New'))
        self.assertFalse(document.complete)

    def test_missing_duplicate_or_unknown_pad_or_style_is_not_guessed(self):
        for before, after in (('PatternStyle="P" X=', 'PatternStyle="missing" X='),
                              ('<Pad Id="41" NetId=', '<Pad Id="99" NetId='),
                              ('<Pad Id="41" NetId=', '<Pad Id="17" NetId='),
                              ('Style="S" X="1"', 'Style="missing" X="1"')):
            with self.subTest(change=after), self.assertRaises(ValueError):
                prepared(SOURCE.replace(before, after))

    def test_unknown_authored_fields_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'unsupported XML fields'):
            prepared(SOURCE.replace('<Value>10K</Value>', '<Value>10K</Value><NotImplemented>keep</NotImplemented>'))


if __name__ == '__main__':
    unittest.main()
