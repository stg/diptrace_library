"""Standalone XML imports owned physical facts rather than cache wrappers."""
import unittest

from lib.common.errors import UnsupportedFileError
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import ReferenceError
from lib.pattern.formats.libxml.read import parse


XML = '''<?xml version="1.0" encoding="utf-8"?>
<Library Type="DipTrace-PatternLibrary" Name="Example" Hint="A small library" Version="4.3.0.5" Units="mm">
<PadStyles><PadStyle Name="Default" Type="Surface" Side="Top" HoleType="Round" Hole="0">
<MainStack Shape="Rectangle" Width="2" Height="1" XOff="0" YOff="0"/>
</PadStyle></PadStyles>
<Patterns><Pattern Type="Free" RefDes="R" Width="10" Height="5">
<Name>Example footprint</Name><Value>Example value</Value>
<Groups><Item Id="8" Enabled="Y" X="1" Y="2"/></Groups>
<DefPad Style="Default"/>
<Pads><Pad Id="7" Style="Default" X="1" Y="2" Group="8"><Number>1</Number></Pad>
<Pad Id="17" Style="Default" X="3" Y="4"><Number>2</Number></Pad></Pads>
<Shapes><Shape Id="30" Type="Line" PadId="17" Group="8" LineWidth="0.2">
<Points><Item X="0" Y="0"/><Item X="1" Y="1"/></Points>
</Shape></Shapes>
</Pattern></Patterns></Library>'''


class PatternXmlReadTests(unittest.TestCase):
    def test_unused_style_declarations_are_not_independent_authoring_facts(self):
        source = XML.replace('</PadStyles>', '''<PadStyle Name="Unused" Type="Surface" Side="Top">
            <MainStack Shape="Rectangle" Width="3.75" Height="1"/>
            </PadStyle></PadStyles>''')
        report = ConversionReport()
        document = import_diagnostics('libxml')(parse)(source, report=report)
        library = document.one('/Library')
        self.assertIsNone(library.child('PadStyles'))
        self.assertNotIn('PadStyles', library.schema.children)
        self.assertEqual(6, library.one('Patterns/Pattern')['PadWidth'])
        self.assertEqual(['unused-pad-styles'], [n.rule for n in report.notices])
        self.assertEqual('info', report.notices[0].severity)
        document.validate()

    def test_metadata_geometry_and_template_values(self):
        document = parse(XML)
        pattern = document.one('/Library/Patterns/Pattern')
        self.assertEqual('Example', document.one('/Library')['Name'])
        self.assertEqual('Example footprint', pattern['Name'])
        self.assertEqual('Example value', pattern['Value'])
        self.assertEqual('R', pattern['RefDes'])
        pads = pattern.one('Pads').children('Pad')
        self.assertEqual(2, len(pads))
        # XML physical coordinates modernize into the same centered local frame
        # as a saved library. Relative geometry and the authored origin survive.
        self.assertEqual((-3, .75), (pads[0]['X'], pads[0]['Y']))
        self.assertEqual((12,13.5), (pattern['Width'],pattern['Height']))
        self.assertEqual((-6,6.75), (pattern['OriginX'],pattern['OriginY']))
        self.assertEqual((6,-6), (pads[1]['X']-pads[0]['X'],pads[1]['Y']-pads[0]['Y']))
        self.assertEqual('1', pads[0]['StringNumber'])
        document.validate()

    def test_public_keys_resolve_to_model_identities(self):
        document = parse(XML)
        pattern = document.one('/Library/Patterns/Pattern')
        pads = pattern.one('Pads').children('Pad')
        group = pattern.one('Pattern_Groups').one('pt')
        shape = pattern.one('Shapes').one('Shape')
        self.assertIs(group, pads[0]['Group'])
        self.assertIs(group, shape['Group'])
        self.assertIs(pads[1], shape['Pad'])
        self.assertEqual((1, 2), (pads[0]['Id'], pads[1]['Id']))
        self.assertEqual(2, shape['PadId'])
        with self.assertRaises(TypeError):
            pads[0]['Id'] = 7
        pads[1].move_to(pattern.one('Pads'), index=0)
        self.assertIs(pads[0], pattern.one('Pads').children('Pad')[1])
        self.assertIs(pads[1], shape['Pad'])
        self.assertEqual(1, shape['PadId'])
        document.validate()

    def test_documented_group_tag_has_the_same_identity_semantics(self):
        document = parse(XML.replace('<Item Id="8"', '<Group Id="8"'))
        pad = document.one('/Library/Patterns/Pattern/Pads/Pad[1]')
        self.assertIs(document.one('/Library/Patterns/Pattern/Pattern_Groups/pt'), pad['Group'])
        document.validate()

    def test_absent_value_is_not_invented(self):
        document = parse(XML.replace('<Value>Example value</Value>', ''))
        self.assertIsNone(document.one('/Library/Patterns/Pattern').get('Value'))

    def test_serialization_token_is_not_an_authored_library_identity(self):
        document = parse(XML.replace('Version="4.3.0.5"', 'Version="5.3.5.1" UID32="4294967295"'))
        library = document.one('/Library')
        self.assertNotIn('UID32', library.schema.fields)
        self.assertIsNone(library.child('UID32'))
        self.assertIsNone(document.clone().one('/Library').child('UID32'))
        document.validate()

    def test_supplier_details_are_typed_editable_model_content(self):
        text = XML.replace('<Name>Example footprint</Name>', '''<Name>Example footprint</Name>
            <Suppliers><PartNumber>Demo-123</PartNumber><Supplier>Example supplier</Supplier>
            <Currency>EUR</Currency></Suppliers>''')
        document = parse(text)
        supplier = document.one('/Library/Patterns/Pattern/Suppliers')
        self.assertEqual('Demo-123', supplier['PartNumber'])
        supplier['PartNumber'] = 'Updated-123'
        self.assertEqual('Updated-123', supplier['PartNumber'])
        self.assertEqual((False,)*4, document.one('/Library/Patterns/Pattern')['Verification'])
        document.validate()

    def test_unknown_fields_and_versions_fail_explicitly(self):
        with self.assertRaises(ValueError):
            parse(XML.replace('<Name>Example footprint</Name>', '<Unknown>data</Unknown>'))
        with self.assertRaises(UnsupportedFileError):
            parse(XML.replace('4.3.0.5', '9.0'))

    def test_unavailable_group_is_explicit(self):
        document = parse(XML.replace('Group="8"', 'Group="99"'))
        pad = document.one('/Library/Patterns/Pattern/Pads/Pad[1]')
        self.assertEqual(99, pad['GroupId'])
        with self.assertRaises(ReferenceError):
            pad['Group']
        self.assertEqual(2, len(document.references.issues))
        document.validate()

    def test_zero_drawing_pad_selector_is_unassigned_even_with_a_zero_pad_key(self):
        for key in ('7', '0'):
            with self.subTest(pad_key=key):
                source = XML.replace('Id="7" Style=', f'Id="{key}" Style=').replace('PadId="17"', 'PadId="0"')
                document = parse(source)
                shape = document.one('/Library/Patterns/Pattern/Shapes/Shape')
                self.assertIsNone(shape['Pad'])
                self.assertEqual(-1, shape['PadId'])
                self.assertFalse(document.references.issues)
                document.validate()

    def test_other_missing_drawing_pad_keys_remain_unresolved(self):
        document = parse(XML.replace('PadId="17"', 'PadId="999"'))
        shape = document.one('/Library/Patterns/Pattern/Shapes/Shape')
        self.assertEqual(999, shape['UnresolvedPadId'])
        with self.assertRaises(ReferenceError):
            shape['Pad']
        self.assertTrue(document.references.issues)
        document.validate()

    def test_missing_group_can_be_resolved_or_cleared(self):
        document = parse(XML.replace('Group="8"', 'Group="99"'))
        pattern = document.one('/Library/Patterns/Pattern')
        pad = pattern.one('Pads/Pad[1]')
        pad['Group'] = pattern.one('Pattern_Groups/pt')
        self.assertIsNone(pad.child('UnresolvedGroupId'))
        pattern.one('Shapes/Shape')['Group'] = None
        self.assertEqual(0, len(document.references.issues))
        document.validate()


if __name__ == '__main__':
    unittest.main()
