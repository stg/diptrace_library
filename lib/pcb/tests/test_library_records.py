"""Cached symbol identity and data do not acquire PCB placement semantics."""
import unittest
from decimal import Decimal

from lib.common.library_records import CACHE, SLOT, DEFINITION
from lib.common.symbol_records import SYMBOL, PIN, DRAWING, DRAWINGS
from lib.common.drawing_records import POINT, POINTS, TEXT_LINE, TEXT_LINES
from lib.common.footprint_objects import new_pad, new_pattern_drawing
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.model.definitions import definition, PAD
from lib.pcb.model import library_records as cached
from lib.pcb.tests.test_core_assembly import fixture
from lib.schematic.model import definitions as schematic


def design():
    decoded = fixture()
    slots = decoded.board.add('CacheLib').add('Slots')
    slot = slots.add('Slot', 12, 'catalog.lib')
    variant = slot.add('Definition', 7)
    part = variant.add('Part', 'Device definition', 'U')
    part.add('Manufacturer', 'Example supplier')
    part.add('Datasheet', 'docs/device.pdf')
    shape = part.add('Shapes').add('Shape', 17)
    shape.add('Type', 10)
    shape.add('TextAngle', .37)
    shape.add('Name', 'superseded scalar')
    shape.add('Orientation', 3)
    shape.add('TextLine').add('pt', 'Current text')
    shape.add('Points_New').add('pt', 1, 2)
    pins = part.add('Pins')
    for index in range(2):
        pin = pins.add('Pin', index, index*3, 0)
        pin.add('Name', 'Signal '+str(index))
        pin.add('StringNumber', str(index+1))
    pattern = variant.add('Pattern', 'Footprint')
    shapes = pattern.add('Shapes')
    for index, kind in enumerate((0, 7, 0)):
        drawing = shapes.append(new_pattern_drawing(index, kind=kind))
        drawing.add('ShieldGroup', 23)
    pads = pattern.add('Pads')
    for index, key in enumerate((-1, 1, -1)):
        pad = pads.append(new_pad('1' if key >= 0 else '', index=index))
        pad['Number_New'] = key
    return assemble_core(decoded)


class LibraryRecordTests(unittest.TestCase):
    def test_schematic_and_pcb_share_fields_with_owning_relationship_constraints(self):
        result = design()
        document = result.document
        cache = document.one('/Board/CacheLib')
        slot = cache.one('Slots/Slot')
        variant = slot.one('Definition')
        part = variant.one('Part')
        pin = part.one('Pins/Pin[1]')
        for actual, expected in ((cache.schema, CACHE), (slot.schema, SLOT),
                                 (variant.schema, DEFINITION), (part.schema, cached.SYMBOL), (pin.schema, cached.PIN)):
            self.assertIs(actual, expected)
        for name, field in SYMBOL.fields.items():
            if name != 'ModelNote':
                self.assertIs(part.schema.fields[name], field)
        self.assertNotIn('ModelNote', part.schema.fields)
        for name, field in PIN.fields.items():
            if name != 'Group':
                self.assertIs(pin.schema.fields[name], field)
        self.assertEqual(pin.schema.fields['Group'].kind, 'reference')
        self.assertIs(schematic.CACHED_PART, SYMBOL)
        self.assertIs(schematic.CACHED_PIN, PIN)
        self.assertIs(schematic.SLOT, SLOT)
        self.assertIs(schematic.DEFINITION, DEFINITION)
        self.assertEqual((slot['Index'], variant['Index']), (0, 0))
        self.assertIsNone(slot.child('Index'))
        self.assertEqual(document.refdes('U').designators(), ['U1'])

    def test_definition_fields_and_pins_are_editable_without_affecting_placement(self):
        result = design()
        document = result.document
        part = document.one('/Board/CacheLib/Slots/Slot/Definition/Part')
        part['RefDes'] = 'D'
        part['Datasheet'] = 'docs/updated.pdf'
        pin = part.one('Pins/Pin[1]')
        pin['Name'] = 'Input'
        pin['X'] = 9
        self.assertEqual(result.components[41]['RefDes'], 'U1')
        self.assertEqual(result.pads[41, 5]['Name'], '')
        pin.move_to(pin.parent, 1)
        self.assertEqual(pin['Index'], 1)
        self.assertEqual(pin['X'], 9)
        copied = document.clone()
        copied.one('/Board/CacheLib/Slots/Slot/Definition/Part')['Datasheet'] = 'docs/copy.pdf'
        self.assertEqual(part['Datasheet'], 'docs/updated.pdf')

    def test_cached_footprints_cannot_be_bound_as_placed_pcb_pads(self):
        result = design()
        pad = result.document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern/Pads/Pad')
        self.assertIsNot(definition(pad), PAD)
        self.assertNotIn('Net', PIN.fields)
        self.assertNotIn('X', SYMBOL.fields)

    def test_cached_shield_group_is_typed_pcb_data_independent_of_local_group(self):
        result = design()
        drawing = result.document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern/Shapes/Shape')
        self.assertIs(drawing.schema, cached.PATTERN_DRAWING)
        self.assertEqual(drawing['ShieldGroup'], 23)
        self.assertIsNone(drawing['Group'])
        drawing['ShieldGroup'] = 42
        copy = result.document.clone().one(drawing.path)
        self.assertEqual(copy['ShieldGroup'], 42)

    def test_cached_drawings_share_schema_and_keep_only_current_text_and_angle(self):
        document = design().document
        shapes = document.one('/Board/CacheLib/Slots/Slot/Definition/Part/Shapes')
        shape = shapes.one('Shape')
        for node, schema in ((shapes, cached.DRAWINGS), (shape, cached.DRAWING),
                (shape.one('Points_New'), POINTS), (shape.one('Points_New/pt'), POINT),
                (shape.one('TextLine'), TEXT_LINES), (shape.one('TextLine/pt'), TEXT_LINE)):
            self.assertIs(node.schema, schema)
        self.assertIs(schematic.SYMBOL_SHAPE, DRAWING)
        self.assertIs(shape.schema.fields['PenWidth'], DRAWING.fields['PenWidth'])
        self.assertIsNone(shape.child('Name'))
        self.assertIsNone(shape.child('Orientation'))
        self.assertEqual(shape['Index'], 0)
        self.assertEqual(shape['TextAngle'], Decimal('.37'))
        shape.one('TextLine/pt')['Text'] = 'Edited text'
        shape.one('Points_New/pt')['X'] = 8
        cloned = document.clone()
        copy = cloned.one('/Board/CacheLib/Slots/Slot/Definition/Part/Shapes/Shape')
        copy.one('Points_New/pt')['Y'] = 12
        self.assertEqual(shape.one('Points_New/pt').values, (8, 2))
        self.assertEqual(copy.one('TextLine/pt')['Text'], 'Edited text')


if __name__ == '__main__':
    unittest.main()
