"""PCB shares footprint facts while retaining its own family constraints."""
import unittest

from lib.common import footprint_records as common
from lib.common.footprint_objects import new_pad, new_pattern
from lib.common.model import Element
from lib.schematic.model import definitions as schematic
from lib.schematic.model.objects import new_pattern as new_schematic_pattern
from lib.pcb.model import definitions as pcb
from lib.pcb.model.objects import new_component, new_pad as new_pcb_pad


class SharedFootprintModelTests(unittest.TestCase):
    def test_shared_schemas_have_one_definition_and_pcb_extends_relationships(self):
        for name in ('PATTERN', 'PAD', 'PAD_STYLE', 'PATTERN_SHAPE', 'DIMENSION', 'HOLE', 'MODEL3D', 'SUPPLIERS'):
            self.assertIs(getattr(schematic, name), getattr(common, name))
        for name in ('PadAngle', 'PadShape_New', 'PadHole', 'StringNumber'):
            self.assertIs(pcb.PAD.fields[name], common.PAD.fields[name])
        self.assertNotIn('Net', common.PAD.fields)
        self.assertIn('Net', pcb.PAD.fields)
        self.assertEqual(pcb.PAD.fields['PadAngle'].kind, 'number')
        self.assertTrue(pcb.PAD.fields['NetNumber'].readonly)

    def test_shared_constructors_do_not_require_document_specific_bookkeeping(self):
        pattern = new_pattern('Shared')
        self.assertEqual(pattern.one('Pads').children(), [])
        self.assertEqual(pattern.one('Shapes').children(), [])
        for record in (pattern, new_pad('1')):
            record.schema.validate_fields(record)
            record.schema.validate_children(record)
        placed = new_component('Example', 'U1')
        self.assertEqual(placed.one('Pattern/Pads').children(), [])
        pad = placed.one('Pattern/Pads').append(new_pcb_pad('A1'))
        self.assertIs(pad.schema, pcb.PAD)
        self.assertNotIn('Number_New', pad.schema.fields)
        # The established schematic adapter keeps its boundary-slot policy.
        schematic_pattern = new_schematic_pattern('Shared')
        self.assertEqual(len(schematic_pattern.select('Pads/Pad')), 2)
        self.assertTrue(all(p.annotations['reserved'] for p in schematic_pattern.select('Pads/Pad')))

    def test_placement_does_not_own_duplicate_template_collections(self):
        template = new_pattern('Template')
        component = new_component('Example', 'U1')
        placed = component.one('Pattern')
        for name in ('InternalConnections', 'UserFields', 'Pattern_Groups'):
            with self.subTest(collection=name):
                self.assertIsNotNone(template.child(name))
                self.assertIn(name, template.schema.children)
                self.assertIsNone(placed.child(name))
                self.assertNotIn(name, placed.schema.children)
        self.assertIsNotNone(component.child('UserFields'))
        self.assertIn('IntConRecords', component.schema.children)
        placed.schema.validate_children(placed)

    def test_binding_never_discards_populated_definition_collections(self):
        for name in ('InternalConnections', 'UserFields', 'Pattern_Groups'):
            with self.subTest(collection=name):
                component = Element('Component', 'Example', 'U1')
                pattern = component.append(new_pattern('Template'))
                collection = pattern.one(name)
                row = collection.add('Unmapped', 1)
                with self.assertRaisesRegex(ValueError, 'belongs to'):
                    pcb.establish_records(component)
                self.assertIs(collection.parent, pattern)
                self.assertEqual(collection.children(), [row])


if __name__ == '__main__':
    unittest.main()
