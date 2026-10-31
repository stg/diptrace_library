"""Public PCB cache data enters the same owned definitions and relationships."""
from decimal import Decimal
import unittest

from lib.common.asc import loads, dumps
from lib.common.references import ReferenceError
from lib.common import library_metadata
from lib.common import user_fields
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.model import library_records
from lib.schematic.model import definitions as schematic
from lib.pcb.tests.test_asc_core import fixture


def declared(owner, name, *values):
    return owner.add('cl_'+name, *values)


def source(*, multipart=False):
    syntax = loads(fixture())
    board = syntax.one('/Board')
    folders = board.add('ProjectLibs_Folders', 1)
    folders.add('Folder', 'parts')
    folders.add('Folder_Variable', '%projectdir%/parts')
    cache = board.add('CacheLib')
    category = declared(cache, 'Categories', 1).add('cl_Category', 'Components', 91, 1)
    declared(category, 'Type', 'Standard', 7, 1).add('cl_SubType', 'Passive', 11)
    declared(cache, 'Subfolders', 1).add('cl_Subfolder', 'Connectors')
    components = declared(cache, 'Components')
    component = declared(components, 'Component')
    part = declared(component, 'Part', 'Device definition', 'U')
    for name, value in dict(Enabled='Y', PartType=0, OriginX=0, OriginY=0,
                            CategoryName='Components', CategoryIndex=91).items():
        declared(part, name, value)
    declared(part, 'CategoryTypes', 1).add('cl_CategoryType', 'Standard', 'Passive', 7, 11)
    declared(part, 'ModelBody', '.model TEST D()', '', '* editable model')
    declared(part, 'UserFields').add('cl_UserField', 'Supplier', 'Example', 0, 1, 8, 1, 0, 3, 4, Decimal('.2'))
    declared(part, 'Verification', 'Y', *('N',)*6)
    pin = declared(declared(part, 'Pins'), 'Pin', 0, 3, 4)
    for name, value in dict(Enabled='Y', Number=2, Name='Input', Group=0).items():
        declared(pin, name, value)
    drawing = declared(declared(part, 'Shapes'), 'Shape', 0)
    for name, value in dict(Enabled='Y', Type=10, Orientation=Decimal('.35'), Width=Decimal('.6'),
                            Name='superseded', Group=0).items():
        declared(drawing, name, value)
    declared(drawing, 'TextLines').add('cl_TextLine', 'Current symbol text')
    declared(drawing, 'Points').add('cl_pt', 6, 9)
    declared(part, 'Groups').add('cl_pt', 'Y', 0, 0, 0)
    pattern = declared(component, 'Pattern', 'Physical package')
    for name, value in dict(Type=0, Width=30, Height=18, Manufacturer='Maker', Datasheet='docs/device.pdf',
                            CategoryName='Components', CategoryIndex=91, TopMask_State=2).items():
        declared(pattern, name, value)
    declared(pattern, 'CategoryTypes', 0)
    declared(pattern, 'UserFields').add('cl_UserField', 'Assembly', 'Top side', 0)
    declared(pattern, 'PossibleNames', 1).add('cl_PossibleName', 'Alternative package')
    declared(pattern, 'PadTerminals')
    pads = declared(pattern, 'Pads')
    for index, key in enumerate((-1, 1, 2, -1)):
        pad = declared(pads, 'Pad', index, str(index), '', index*3, 0)
        for name, value in dict(Number=key, Group=0, PadWidth=3, PadHeight=6, PadShape=2,
                                TopMask_State=1, CustomSwell_New=Decimal('.6'), CustomSwell=Decimal('.6'),
                                CustomShrink_New=-1000, CustomShrink=-1000).items():
            declared(pad, name, value)
        declared(pad, 'PadTerminals')
        declared(pad, 'Point').add('cl_pt', 1, 2)
    shapes = declared(pattern, 'Shapes')
    for kind in (0, 7, 0):
        declared(shapes, 'Shape', kind, 'N', 1, 0, 0, 0, 0, 0, 0, 'old', 'Example', 'Y',
                 2, 1, -1, Decimal('.35'), Decimal('.3'), 0)
        declared(shapes, 'Point').add('cl_pt', 12, 6)
        declared(shapes, 'TextLines').add('cl_TextLine', 'Current footprint text')
        declared(shapes, 'Group', 0)
    declared(pattern, 'Holes')
    dimension = declared(declared(pattern, 'Dimensions'), 'Dimension', 0)
    for name, value in dict(Enabled='Y', Locked='N', VectorFont='Y', ShowUnits='N',
                            Type=0, Connected1=-1, Connected2=-1, Group=-1).items():
        declared(dimension, name, value)
    declared(pattern, 'Pattern_Groups').add('cl_pt', 'Y', 0, 0, 0)
    declared(pattern, 'InternalConnections').add('cl_IntCon', 1, 2)
    model = declared(pattern, 'Model3D')
    declared(model, 'Model3DFile', 'parts/package.step')
    declared(model, 'pt', 0, 0, 0, 0, 0, 0, 1, 1, 1, 'N', 'N', -1)
    if multipart:
        second = part.clone()
        second.set_argument(0, 'Second section')
        component.insert(second, 1)
    declared(components, 'Component')  # An empty library slot remains a slot.
    paths = cache.add('Design_Cache_Specific')
    declared(paths, 'pt', 'catalog.eli', '%projectdir%/catalog.eli')
    declared(paths, 'pt', '', '')
    return dumps(syntax, preserve=False)


class AscCacheTests(unittest.TestCase):
    def test_physical_and_symbol_data_are_owned_typed_and_editable(self):
        result = assemble_core(prepare_core(source()))
        document = result.document
        slot, empty = document.select('/Board/CacheLib/Slots/Slot')
        part, pattern = slot.one('Definition/Part'), slot.one('Definition/Pattern')
        self.assertFalse(empty.children('Definition'))
        self.assertEqual(slot['VariablePath'], '%projectdir%/catalog.eli')
        self.assertIs(part.schema, library_records.SYMBOL)
        self.assertEqual(part['Name'], 'Device definition')
        self.assertEqual(part['Datasheet'], 'docs/device.pdf')
        self.assertIsNone(pattern.child('Datasheet'))
        self.assertNotIn('ModelNote', part.schema.fields)
        lines = part.select('ModelBody/Line')
        self.assertEqual([line['Text'] for line in lines], ['.model TEST D()', '', '* editable model'])
        lines[1]['Text'] = '* added comment'
        self.assertEqual(pattern['Pattern_Manufacturer'], 'Maker')
        self.assertEqual(pattern['TopMask_State'], 2)
        pads = pattern.select('Pads/Pad')
        self.assertEqual([pad['DisableTopMask'] for pad in pads], [1, 1])
        self.assertEqual([pad['CustomSwell_New'] for pad in pads], [Decimal('.6')]*2)
        self.assertTrue(all(pad.child('CustomSwell') is None for pad in pads))
        self.assertIsNone(pads[0].child('Number_New'))
        self.assertNotIn('Net', pads[0].schema.fields)
        self.assertEqual(pads[0].one('PadPoints_New/pt').values, (1, 2))
        drawing = pattern.one('Shapes/Shape')
        self.assertEqual(drawing['TextAngle'], Decimal('.35'))
        self.assertEqual(drawing.one('Points_New/pt').values, (12, 6))
        self.assertEqual(drawing.one('TextLine/pt')['Text'], 'Current footprint text')
        symbol_drawing = part.one('Shapes/Shape')
        self.assertEqual(symbol_drawing['TextAngle'], Decimal('.35'))
        self.assertEqual(symbol_drawing.one('Points_New/pt').values, (6, 9))
        self.assertEqual(symbol_drawing.one('TextLine/pt')['Text'], 'Current symbol text')
        self.assertIsNone(symbol_drawing.child('Name'))
        self.assertIsNone(symbol_drawing.child('Orientation'))
        self.assertIs(drawing['Group'], pattern.one('Pattern_Groups/pt'))
        self.assertIs(symbol_drawing['Group'], part.one('Groups/pt'))
        dimension = pattern.one('Dimensions/Dimension')
        self.assertIs(dimension['ShowUnits'], False)
        self.assertIs(dimension['VectorFont'], True)
        dimension['ShowUnits'] = True
        self.assertEqual(result.components[17]['Name'], 'Device')

    def test_pad_assignment_and_internal_pair_follow_reorder_without_rebuild(self):
        result = assemble_core(prepare_core(source()))
        local = result.cached_footprints[0]
        part = local.pattern.parent.one('Part')
        pair = local.pattern.one('InternalConnections/IntCon')
        self.assertEqual(pair.values, (1, 2))
        self.assertEqual(part.one('Pins/Pin')['Number'], 2)
        local.pads[2].move_to(local.pattern.one('Pads'), 0)
        self.assertEqual(pair.values, (2, 1))
        self.assertEqual(part.one('Pins/Pin')['Number'], 1)
        with self.assertRaises(ReferenceError):
            local.pads[2].detach()

    def test_cached_user_fields_share_data_without_placed_pcb_markings(self):
        document = assemble_core(prepare_core(source())).document
        definition = document.one('/Board/CacheLib/Slots/Slot[1]/Definition')
        symbol = definition.one('Part/UserFields/UserField')
        footprint = definition.one('Pattern/UserFields/UserField')
        self.assertIs(symbol.schema, schematic.COMPONENT_USER_FIELD)
        self.assertIs(symbol.schema, user_fields.COMPONENT_USER_FIELD)
        self.assertIs(footprint.schema, schematic.USER_FIELD)
        self.assertEqual((symbol['Name'], symbol['Value'], symbol['Align']), ('Supplier', 'Example', 8))
        self.assertEqual((symbol['X'], symbol['Y'], symbol['Angle']), (3, 4, Decimal('.2')))
        symbol['Value'] = 'Other supplier'
        symbol['X'] = 6
        footprint['Value'] = 'Bottom side'
        self.assertNotIn('SilkX', symbol.schema.fields)
        self.assertNotIn('AssyX', footprint.schema.fields)
        self.assertNotIn('X', footprint.schema.fields)
        self.assertEqual(document.one('/Board/Components/Component')['Name'], 'Device')

    def test_multipart_definitions_share_one_supplied_pattern(self):
        result = assemble_core(prepare_core(source(multipart=True)))
        slot = result.document.one('/Board/CacheLib/Slots/Slot[1]')
        first, second = slot.children('Definition')
        self.assertIsNotNone(first.child('Pattern'))
        self.assertIsNone(second.child('Pattern'))
        self.assertEqual(first.one('Part')['Datasheet'], 'docs/device.pdf')
        self.assertIsNone(second.one('Part').get('Datasheet'))
        self.assertEqual(len(result.cached_footprints), 1)
        first.move_to(slot)
        result.cached_footprints[0].pads[2].move_to(first.one('Pattern/Pads'), 0)
        self.assertEqual([definition.one('Part/Pins/Pin')['Number'] for definition in slot.children('Definition')], [1, 1])

    def test_shared_catalogue_classification_path_and_model_text_records(self):
        document = assemble_core(prepare_core(source())).document
        category = document.one('/Board/CacheLib/Categories/Category')
        self.assertIs(category.schema, schematic.CATALOG_CATEGORY)
        self.assertIs(category.schema, library_metadata.CATALOG_CATEGORY)
        category['Name'] = 'Updated catalogue'
        classification = document.one('/Board/CacheLib/Slots/Slot[1]/Definition/Part/Component_CategoryTypes/CategoryType')
        self.assertIs(classification.schema, schematic.CATEGORY_TYPE)
        self.assertEqual(classification['SubTypeIndex'], 11)
        path = document.one('/Board/ProjectLibs_Folders/Folder')
        self.assertIs(path.schema, library_metadata.LIBRARY_PATH)
        self.assertEqual((path['Path'], path['VariablePath']), ('parts', '%projectdir%/parts'))
        path['Path'] = 'other-parts'
        self.assertEqual(path['VariablePath'], '%projectdir%/parts')

    def test_invalid_counts_and_conflicting_aliases_fail_explicitly(self):
        for before, after, message in (
            ('(cl_Categories 1', '(cl_Categories 2', 'catalog record count'),
            ('(Folder_Variable "%projectdir%/parts")', '', 'path pairs'),
            ('(cl_CustomSwell 0.6)', '(cl_CustomSwell 0.9)', 'conflicting cached pad'),
            ('(cl_ShowUnits "N")', '(cl_ShowUnits maybe)', 'expected boolean'),
        ):
            with self.subTest(message=message):
                original = source()
                self.assertIn(before, original)
                with self.assertRaisesRegex(ValueError, message):
                    prepare_core(original.replace(before, after))


if __name__ == '__main__':
    unittest.main()
