"""XML graphics share current geometry and identity edits with other inputs."""
from decimal import Decimal
import unittest

from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.tests.test_dipxml_classes import source as electrical_source
from lib.pcb.tests.test_dipxml_electrical import prepared


GEOMETRY = '''<BoardOutline Locked="Y" Selected="Y" ShieldGroup="3"><Points>
  <Point X="1" Y="2"/><Point X="3" Y="4" Arc="Y"/><Point X="5" Y="2"/>
</Points></BoardOutline>
<Groups><Group Id="90"/></Groups>
<Shapes>
  <Shape Id="23" Type="Text" Layer="Signal/Plane" LayId="8" Group="90" NetId="7" Angle="8.7"
      FontSize="4" FontSizeFloat="4.5" FontWidth="0.2" FontScale="1.2" FontMono="Y"
      HorzAlign="Left" VertAlign="Top" TextAlign="Right" LineWidth="0.3">
    <FontName>Example Font</FontName><TextLines><TextLine>First</TextLine><TextLine>Second</TextLine></TextLines>
    <Points><Item X="2" Y="-3"/></Points>
  </Shape>
  <Shape Id="51" Type="Picture" Layer="Top Assy" PictureRaster="Y" PictureWidth="7" PictureHeight="5"
      PictureTransparent="25" PictureFlipped="Y">
    <Points><Item X="4" Y="6"/></Points>
    <PictureFile><Path>images/mark.png</Path><Var>${PROJECT}/images/mark.png</Var></PictureFile>
    <PictureVector Width="8" Height="9"><Polygons><Polygon><Points>
      <Point X="1" Y="2"/><Point X="3" Y="4"/><Point X="5" Y="6"/>
    </Points></Polygon></Polygons></PictureVector>
  </Shape>
</Shapes>
<CopperPours><CopperPour Id="37" Lay="8" NetId="7" Group="90" Poured="Y" RegionsDone="Y"
    MinimumArea="4" LineWidth="0.2" Spoke="4 spoke 45" Type="Cross 90" RatlineMode="All Ratlines">
  <Points><Point X="1" Y="2"/><Point X="3" Y="4"/><Point X="5" Y="2"/></Points>
</CopperPour></CopperPours>'''


def source():
    return electrical_source().replace('Version="5.3"', 'Version="5.3.5.1"').replace('</Board>', GEOMETRY+'</Board>')


def design(text=None):
    return assemble_graphics(prepared(text or source()))


class PcbXmlGraphicTests(unittest.TestCase):
    def test_group_selection_survives_xml_and_disabled_groups_normalize_away(self):
        from lib.common.conversion import ConversionReport
        from lib.pcb.formats.dipxml.resource_output import project_groups
        current = design(source().replace('<Group Id="90"/>',
            '<Group Id="90" Selected="Y"/><Group Id="91" Enabled="N"/>')).document
        group = current.one('/Board/Groups/Group')
        self.assertTrue(group['Selected'])
        self.assertTrue(group['Enabled'])
        report = ConversionReport()
        output = project_groups(current.one('/Board'), report=report)
        self.assertIs(output.one('Group')['Selected'], True)
        self.assertEqual(len(output.children()), 1)
        self.assertNotIn('group-attributes', {n.rule for n in report.warnings})

    def test_outline_drawings_pours_and_groups_bind_to_the_same_model(self):
        result = design()
        document, board = result.document, result.document.one('/Board')
        shape, pour, group = result.drawings[23], result.pours[37], result.groups[90]
        self.assertTrue(board['Locked'])
        self.assertTrue(board['Selected'])
        self.assertEqual(board['ShieldGroup'], 3)
        self.assertEqual([p.values for p in board.select('Points/pt')],
                         [(3, -6, False), (9, -12, True), (15, -6, False)])
        self.assertIs(shape['Group'], group)
        self.assertIs(shape['LayerTarget'], result.rules.layers[1])
        self.assertIs(pour['Layer'], shape['LayerTarget'])
        self.assertIs(shape['Net'], result.rules.routing.core.nets[7])
        self.assertIs(pour['Net'], shape['Net'])
        self.assertEqual((shape['Layer'], shape['Type'], shape['TextAngle']), (3, 6, Decimal('8.7')))
        self.assertEqual(shape.one('Points/pt').values, (6, 9))
        self.assertNotIn('Points_New', shape.schema.children)
        self.assertEqual([line['Text'] for line in shape.select('TextLine/pt')], ['First', 'Second'])
        self.assertEqual((shape['FontSize'], shape['FontWidth'], shape['PenWidth']),
                         (Decimal('4.5'), Decimal('.6'), Decimal('.9')))
        self.assertTrue(shape['FontMono'])
        self.assertEqual((shape['TextHorz'], shape['TextVert'], shape['TextAlign']), (-1, -1, 1))
        self.assertTrue(pour['Poured'])
        self.assertIsNone(pour.child('Fill'))
        self.assertEqual(pour['MinimumArea'], 36)
        self.assertEqual((pour['Type'], pour['Spoke'], pour['RatlineMode']), (4, 3, 1))
        document.references.validate()

    def test_literal_picture_paths_and_owned_vector_geometry_require_no_external_files(self):
        picture = design().drawings[51]
        self.assertEqual((picture['Picture_File'], picture['Picture_File_Variable']),
                         ('images/mark.png', '${PROJECT}/images/mark.png'))
        self.assertTrue(picture['PictureRaster'])
        self.assertTrue(picture['PictureFlipped'])
        self.assertEqual((picture['PictureWidth'], picture['PictureHeight']), (21, 15))
        self.assertEqual(picture['PictureTransparent'], 25)
        vector = picture.one('PictureVector')
        self.assertEqual((vector['Width'], vector['Height']), (24, 27))
        vertex = vector.one('Polygons/Polygon/Points/Item[2]')
        self.assertEqual((vertex['X'], vertex['Y']), (9, -12))
        vertex['X'] = 8
        self.assertEqual(vertex['X'], 8)

    def test_identity_edits_and_clones_preserve_targets_and_removal_constraints(self):
        result = design()
        shape, pour, group = result.drawings[23], result.pours[37], result.groups[90]
        layer, net = shape['LayerTarget'], shape['Net']
        layer.move_to(layer.parent, 2)
        layer['Name'] = 'Changed'
        net['Name'] = 'Power'
        shape.one('Points/pt')['X'] = 17
        self.assertEqual((shape['LayId'], pour['Lay']), (2, 2))
        self.assertEqual(pour['Net']['Name'], 'Power')
        with self.assertRaises(ReferenceError):
            result.document.remove(group)
        clone = result.document.clone()
        copied = clone.one('/Board/Shapes/Shape[1]')
        self.assertIsNot(copied['Group'], group)
        self.assertIs(copied['Group']._owner(), clone)
        self.assertEqual(copied.one('Points/pt')['X'], 17)
        clone.references.validate()

    def test_physical_lengths_areas_and_scalar_fields_have_distinct_units(self):
        result = design(source().replace('Units="mm"', 'Units="mil"'))
        shape, pour = result.drawings[23], result.pours[37]
        self.assertEqual(pour['MinimumArea'], Decimal('4')*Decimal('.0762')**2)
        self.assertEqual(shape['FontWidth'], Decimal('.01524'))
        self.assertEqual(shape['FontSize'], Decimal('4.5'))
        self.assertEqual(shape['TextAngle'], Decimal('8.7'))
        self.assertEqual(pour['SpokeWidth'], Decimal('.99'))  # Omitted reset default is already in model units.

    def test_missing_optional_fields_use_verified_loader_defaults(self):
        text = electrical_source().replace('</Board>', '''<Shapes><Shape Id="1"/></Shapes>
          <CopperPours><CopperPour Id="2"/></CopperPours></Board>''')
        result = design(text)
        shape, pour = result.drawings[1], result.pours[2]
        self.assertEqual((shape['FontName'], shape['FontSize'], shape['FontWidth']), ('Tahoma', 1, -2))
        self.assertEqual((shape['PenWidth'], shape['TextAlign']), (-1, -1))
        self.assertTrue(shape['PictureProportions'])
        self.assertFalse(pour['Poured'])
        self.assertIsNone(pour.child('Fill'))
        self.assertEqual((pour['MinimumArea'], pour['Clearance'], pour['LineWidth']),
                         (9, Decimal('.99'), Decimal('1.905')))

    def test_unknown_fields_ambiguous_ids_and_unavailable_targets_are_explicit(self):
        for before, after in (('Shape Id="51"', 'Shape Id="23"'), ('LayId="8"', 'LayId="999"'),
                              ('Group="90"', 'Group="99"'), ('Layer="Top Assy"', 'Layer="Non-Signal"'),
                              ('LineWidth="0.2"', 'UnknownSetting="0.2"'), ('Group Id="90"', 'Group Id="-1"')):
            with self.subTest(after=after), self.assertRaises(ValueError):
                design(source().replace(before, after))

    def test_non_signal_layer_keys_and_names_bind_to_current_layer_identity(self):
        layers = '''<NonSignals><NonSignal Id="81" Color="123" Side="Bottom"><Name>Notes</Name></NonSignal>
          <NonSignal Id="20"><Name>Other</Name></NonSignal></NonSignals>'''
        for selector in ('81', 'Notes'):
            text = source().replace('Layer="Top Assy"', f'Layer="Non-Signal" LayId="{selector}"')
            result = design(text.replace('</Board>', layers+'</Board>'))
            layer = result.non_signals[0]
            self.assertIs(result.drawings[51]['LayerTarget'], layer)
            self.assertEqual((layer['Name'], layer['Color'], layer['Side']), ('Notes', 123, 2))
            other = result.non_signals[1]
            self.assertEqual((other['Color'], other['Side']), (0x8A8A8A, 0))
            layer.move_to(layer.parent, 1)
            self.assertEqual(result.drawings[51]['LayId'], 1)
            result.document.references.validate()

    def test_font_stroke_version_gate_and_negative_conventions_are_applied_on_import(self):
        for version, positive, negative in (('5.3.4.9', Decimal('.2'), -3),
                                             ('5.3.5.0', Decimal('.6'), Decimal('-1.5'))):
            text = source().replace('Version="5.3.5.1"', f'Version="{version}"')
            self.assertEqual(design(text).drawings[23]['FontWidth'], positive)
            self.assertEqual(design(text.replace('FontWidth="0.2"', 'FontWidth="-1.5"')).drawings[23]['FontWidth'], negative)
            for value in (-1, -2, -3):
                self.assertEqual(design(text.replace('FontWidth="0.2"', f'FontWidth="{value}"')).drawings[23]['FontWidth'], value)


if __name__ == '__main__':
    unittest.main()
