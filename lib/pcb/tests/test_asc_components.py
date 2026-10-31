"""PCB ASC shorthand expands to the same footprint ownership as binary input."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.asc import loads
from lib.pcb.formats.asc.components import unpack_component


SOURCE = '''(Component "Device" R003
  (Number 17) (Enabled "Y") (X 10) (Y 20) (Angle 7.854)
  (Value "Y") (Pattern "Footprint") (Type 10) (Width 12) (Height 8)
  (PadTerminals
    (PadTerminal (Type 2) (X 1) (Y 2) (Angle 0.37)
      (ShapeWidth 3) (ShapeHeight 4) (ShapeCorner 5) (ShapePoints)))
  (Pads
    (Pad 1 "A" "Contact" 2 3
      (Number 9) (NetNumber 73) (Angle 0.37) (PadWidth 4) (PadHeight 5)
      (PadShape 3) (SurfacePad "Y") (PadPoints (pt 1 2))
      (TopMask_State 3) (BotMask_State 2) (TopPaste_State 1) (BotPaste_State 0)
      (CustomSwell -1000) (CustomShrink -1000) (IntOwner -1)
      (PadTerminals)
      (Teardrop_TJunction 2) (Teardrop_TJunction_Length 0.6)))
  (Shapes
    (Shape 1 "N" 2 0 1 1 0 0 0 "old label" "Font" "Y" 6 1 -1 7.854 0.3 0)
      (Width 0.7) (Points (pt 2 3) (pt 4 5))
      (TextLine (pt "Y")) (Marking_Generated "Y"))
  (Holes (Hole "Y" "N" 1 2 3 1 -1))
  (Dimensions)
  (Model3D (Model3DFile "model.step")
    (pt 0 0 0 1 2 3 1 1 1 "N" "Y" 0)
    (IPC_X 4) (IPC_Y 5) (ModelType 1) (KeepPins "Y"))
  (Hidden_Path 2 (pt 91) (pt 75)) (AssemblyExclude 0)
  (InternalConnection_Records (pt 9 11))
  (InternalConnections
    (IntCon (ConnectAll "N") (PadNum (pt 9) (pt 11)) (Line (pt 9 11)))))'''


def component(text=SOURCE):
    return loads(text).one('/Component')


class AscComponentTests(unittest.TestCase):
    def test_unquoted_numeric_and_empty_refdes_are_text(self):
        for token, expected in (('003', '003'), ('0', '0'), ('1', '1'), ('', ''),
                                ('""', '""'), ('"R(1)"', '"R(1)"'), ('R-1', 'R-1')):
            with self.subTest(token=token):
                node = component(SOURCE.replace('"Device" R003', '"Device" '+token))
                unpack_component(node)
                self.assertEqual(node.values, ('Device', expected))

    def test_classification_names_share_the_current_rows_and_consume_only_valid_counts(self):
        text = SOURCE.replace('(Pattern "Footprint")', '''(Pattern "Footprint")
          (Component_CategoryTypes 1 (Component_Type "Function" "Passive" 7 19))
          (Pattern_CategoryTypes 1 (Pattern_Type "Package" "Small" 3 11))''')
        node = unpack_component(component(text))
        for path in ('Component_CategoryTypes', 'Pattern/Pattern_CategoryTypes'):
            self.assertEqual(node.one(path).values, ())
            self.assertEqual([row.kind for row in node.one(path).children()], ['CategoryType'])
        self.assertEqual(node.one('Pattern/Pattern_CategoryTypes/CategoryType').values,
                         ('Package', 'Small', 3, 11))
        with self.assertRaisesRegex(ValueError, 'count'):
            unpack_component(component(text.replace('(Pattern_CategoryTypes 1', '(Pattern_CategoryTypes 2')))

    def test_current_multiline_text_supersedes_the_compatibility_header(self):
        text = SOURCE.replace('(TextLine (pt "Y"))',
                              '(TextLines (TextLine "first") (TextLine "") (TextLine "third"))')
        node = unpack_component(component(text))
        shape = node.one('Pattern/Shapes/Shape')
        self.assertIsNone(shape.child('TextLines'))
        self.assertEqual([line.values for line in shape.select('TextLine/pt')],
                         [('first',), ('',), ('third',)])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            unpack_component(component(SOURCE.replace('(TextLine (pt "Y"))',
                '(TextLine (pt "Y")) (TextLines (TextLine "other"))')))

    def test_named_pad_thermals_enter_the_shared_selector_assembly(self):
        node = component()
        thermal = node.one('Pads/Pad').add('CustomSpokes').add('CustomSpoke')
        for name, value in dict(Layer=-1, Type=2, Spoke=4, Width=Decimal('1.5')).items():
            thermal.add(name, value)
        unpack_component(node)
        self.assertEqual(thermal.values, (-1, 2, 4, Decimal('1.5')))
        self.assertEqual(thermal.children(), [])

    def test_current_geometry_and_pattern_ownership_replace_flat_syntax(self):
        node = unpack_component(component())
        pattern = node.one('Pattern')
        self.assertEqual(node.values, ('Device', 'R003'))
        self.assertEqual(pattern.values, ('Footprint',))
        self.assertIsNone(node.child('Pads'))
        self.assertIsNone(node.child('Width'))
        self.assertEqual(pattern['Width'], 12)
        self.assertTrue(node['Enabled'])
        self.assertEqual(node['Value'], 'Y')
        self.assertEqual(node['Angle'], Decimal('7.854'))
        pad = pattern.one('Pads/Pad')
        self.assertEqual(pad.values, (1, 'A', 'Contact', 2, 3))
        self.assertEqual(pad['Number_New'], 9)
        self.assertEqual(pad['DisableTopMask'], 3)
        self.assertEqual(pad['PadAngle'], Decimal('.37'))
        self.assertEqual(pad.one('PadPoints_New/pt').values, (1, 2))
        self.assertEqual(pad.one('TeardropParams')['TJuncLength'], Decimal('.6'))
        shape = pattern.one('Shapes/Shape')
        self.assertEqual(shape['Width'], Decimal('.7'))
        self.assertEqual(shape['Layer'], 2)
        self.assertEqual(shape['TextAngle'], Decimal('7.854'))
        self.assertIsNone(shape.child('Points'))
        self.assertEqual([p.values for p in shape.select('Points_New/pt')], [(2, 3), (4, 5)])
        self.assertEqual(shape.one('TextLine/pt').values, ('Y',))
        self.assertTrue(shape['MarkingGenerated'])
        self.assertEqual(pattern.one('Holes/Hole').values, (True, False, 1, 2, 3, 1, -1))

    def test_terminals_model_placement_and_hierarchy_counts_become_owned_data(self):
        node = unpack_component(component())
        terminal = node.one('Pattern/PadTerminal')
        self.assertEqual(terminal.values, (0,))
        self.assertEqual(terminal['Angle'], Decimal('.37'))
        self.assertIsNone(node.one('Pattern').child('PadTerminals'))
        model = node.one('Pattern/Model3D')
        self.assertEqual(model.one('Offset')['Y'], 2)
        self.assertEqual((model['Mirror'], model['NoSearch'], model['KeepPins']), (False, True, True))
        self.assertEqual((model['IPC_XOff'], model['IPC_YOff'], model['Type']), (4, 5, 1))
        self.assertIsNone(model.child('pt'))
        self.assertEqual([p.values for p in node.select('HierarchyPath/Item')], [(91,), (75,)])
        self.assertEqual(node.one('AssemblyExclude').values, ())
        self.assertEqual(node.one('InternalConnections/IntCon/PadId/Item[1]').values, (9,))
        self.assertIs(node.one('InternalConnections/IntCon')['ConnectAll'], False)

    def test_ambiguous_aliases_bad_boolean_counts_and_headers_fail(self):
        invalid = (
            SOURCE.replace('(Number 9)', '(Number 9) (Number_New 9)'),
            SOURCE.replace('(Enabled "Y")', '(Enabled "maybe")'),
            SOURCE.replace('(Hidden_Path 2', '(Hidden_Path 3'),
            SOURCE.replace('(Pad 1 "A" "Contact" 2 3', '(Pad 1 "A" "Contact" 2'),
            SOURCE.replace('(pt 0 0 0 1 2 3 1 1 1 "N" "Y" 0)', '(pt 0 0 0)'),
        )
        for text in invalid:
            with self.subTest(text=text[:40]), self.assertRaises(ValueError):
                unpack_component(component(text))

    def test_adapter_expansion_does_not_plan_live_authoring_edits(self):
        node = component()
        owner = node._owner()
        with patch.object(owner.references, 'plan_collections', side_effect=AssertionError('live edit plan')):
            unpack_component(node)
        self.assertTrue(owner._automatic_structure)
        self.assertEqual(node.one('Pattern')['Width'], 12)


if __name__ == '__main__':
    unittest.main()
