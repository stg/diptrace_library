"""Sheet and display data use the same editable records after either import."""
from decimal import Decimal
import unittest

from lib.common.asc import loads, dumps
from lib.common.model import Element
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.values import move_fields
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.sheet import read_groups, read_sheet_layout
from lib.pcb.formats.errors import PcbError
from lib.pcb.model import settings_records
from lib.pcb.tests.test_asc_core import fixture
from lib.pcb.tests.test_core_assembly import fixture as binary_fixture
from lib.pcb.tests.test_sheet import sheet_fixture


def source():
    syntax = loads(fixture())
    board = syntax.one('/Board')
    for name, value in dict(PageWidth=891, PageHeight=630, Left=-3, Top=15, Right=18,
                            Bottom=21, LayerPanel_TopAssy='Y', LayerPanel_BotOutline='N').items():
        board.add(name, value)
    settings = board.add('Settings')
    for name, value in dict(DisplayTitles='Y', DisplaySheet='N', GridSnap='N',
                            ContrastEdit='Y', ShowFiducials='N',
                            AssemblyWidth=Decimal('.36'), CompOutlineWidth=Decimal('.15'),
                            CourtyardWidth=Decimal('.18')).items():
        settings.add(name, value)
    return dumps(syntax, preserve=False)


class AscDocumentSettingsTests(unittest.TestCase):
    def test_current_unit_and_named_markings_replace_display_compatibility_slots(self):
        syntax = loads(source())
        board = syntax.one('/Board')
        settings = board.one('Settings')
        for name, value in dict(ShowText=3, TextAlign=0, ShowText2=6, TextAlign2=4,
                                RefDes_Global_SilkShow=1, RefDes_Global_SilkAlign=7,
                                Name_Global_SilkShow=2, Name_Global_SilkAlign=4).items():
            board.add(name, value)
        for name, value in dict(UnitsMM='N', UnitsMIL='Y', UnitsINCH='N', AssyPatMarkings='Y').items():
            settings.add(name, value)
        # The declaration and display switches describe one selected unit.
        result = assemble_core(prepare_core(dumps(syntax, preserve=False)))
        document, board = result.document, result.document.one('/Board')
        self.assertEqual(document.root['Units'], 'mil')
        self.assertEqual((board['RefDes_Global_SilkShow'], board['RefDes_Global_SilkAlign']), (1, 7))
        self.assertEqual((board['Name_Global_SilkShow'], board['Name_Global_SilkAlign']), (2, 4))
        self.assertFalse(any(board.child(name) is not None for name in ('ShowText', 'TextAlign', 'ShowText2', 'TextAlign2')))
        self.assertFalse(any(board.one('Settings').child(name) is not None
                             for name in ('UnitsMM', 'UnitsMIL', 'UnitsINCH', 'AssyPatMarkings')))
        board['RefDes_Global_SilkAlign'] = 3
        self.assertEqual(document.clone().one('/Board')['RefDes_Global_SilkAlign'], 3)

    def test_compatibility_display_fields_are_still_typed_and_unambiguous(self):
        for owner_path, name, value, message in (
                ('/Board', 'ShowText', 'invalid', 'numeric'),
                ('/Board', 'TextAlign2', 1.5, 'numeric'),
                ('/Board/Settings', 'UnitsMM', 'invalid', 'boolean'),
                ('/Board/Settings', 'AssyPatMarkings', 1, 'boolean')):
            syntax = loads(source())
            syntax.one(owner_path).add(name, value)
            with self.subTest(name=name), self.assertRaisesRegex(PcbError, message):
                prepare_core(dumps(syntax, preserve=False))
        syntax = loads(source())
        syntax.one('/Board').add('ShowText', 2)
        syntax.one('/Board').add('ShowText', 3)
        with self.assertRaisesRegex(PcbError, 'ambiguous ShowText'):
            prepare_core(dumps(syntax, preserve=False))

    def test_sheet_layout_is_owned_once_and_remains_editable(self):
        result = assemble_core(prepare_core(source()))
        board = result.document.one('/Board')
        sheet, settings = board.one('SheetSettings'), board.one('Settings')
        self.assertIs(sheet.schema, settings_records.SHEET)
        self.assertEqual((sheet['SheetWidth'], sheet['SheetHeight']), (891, 630))
        self.assertEqual([sheet[name+'Margin'] for name in ('Left', 'Top', 'Right', 'Bottom')],
                         [-3, 15, 18, 21])
        self.assertEqual((sheet['DisplayTitles'], sheet['DisplaySheet']), (True, False))
        self.assertFalse(any(board.child(name) is not None for name in
                             ('PageWidth', 'PageHeight', 'Left', 'Top', 'Right', 'Bottom')))
        self.assertIsNone(settings.child('DisplayTitles'))
        self.assertIsNone(sheet.child('TitleBlocks'))
        self.assertIsNone(sheet.child('BorderZones'))
        sheet['SheetWidth'] = 1260
        sheet['DisplaySheet'] = True
        copied = result.document.clone()
        copied.one('/Board/SheetSettings')['LeftMargin'] = 30
        self.assertEqual(sheet['LeftMargin'], -3)
        with self.assertRaises(TypeError):
            sheet['DisplaySheet'] = 1
        self.assertTrue(sheet['DisplaySheet'])

    def test_aliases_keep_their_boolean_sense_and_preferences_are_optional_data(self):
        settings = assemble_core(prepare_core(source())).document.one('/Board/Settings')
        self.assertTrue(settings['EditInactiveLayer'])
        self.assertFalse(settings['ShowCompFiducials'])
        self.assertFalse(settings['GridSnap'])
        self.assertEqual([settings[name] for name in
                          ('AssemblyWidth', 'CompOutlineWidth', 'CourtyardWidth')],
                         list(map(Decimal, ('.36', '.15', '.18'))))
        self.assertIsNone(settings.child('ContrastEdit'))
        self.assertIsNone(settings.child('ShowFiducials'))
        del settings['GridSnap']
        self.assertIsNone(settings.get('GridSnap'))
        with self.assertRaises(TypeError):
            settings['AssemblyWidth'] = 'wide'

    def test_layer_display_flags_are_grouped_without_inventing_missing_choices(self):
        result = assemble_core(prepare_core(source()))
        board = result.document.one('/Board')
        panel = board.one('Settings/LayerPanel')
        self.assertIs(panel.schema, settings_records.LAYER_PANEL)
        self.assertTrue(panel['TopAssy'])
        self.assertFalse(panel['BotOutline'])
        self.assertIsNone(panel.get('TopMask'))
        self.assertIsNone(board.child('LayerPanel_TopAssy'))
        panel['BotOutline'] = True
        self.assertTrue(panel['BotOutline'])

    def test_display_settings_can_create_their_owner_without_a_settings_block(self):
        syntax = loads(fixture())
        syntax.one('/Board').add('LayerPanel_TopMask', 'N')
        result = assemble_core(prepare_core(dumps(syntax, preserve=False)))
        self.assertFalse(result.document.one('/Board/Settings/LayerPanel')['TopMask'])
        self.assertIsNone(result.document.one('/Board').child('SheetSettings'))

    def test_no_sheet_data_does_not_create_a_placeholder(self):
        result = assemble_core(prepare_core(fixture()))
        self.assertIsNone(result.document.one('/Board').child('SheetSettings'))

    def test_ambiguous_or_invalid_declarations_fail(self):
        for before, after, message in (
            ('(ContrastEdit "Y")', '(ContrastEdit "Y") (EditInactiveLayer "N")', 'ambiguous'),
            ('(DisplaySheet "N")', '(DisplaySheet "perhaps")', 'boolean'),
            ('(LayerPanel_TopAssy "Y")', '(LayerPanel_TopAssy 1)', 'boolean'),
            ('(PageWidth 891)', '(PageWidth 891) (PageWidth 1260)', 'ambiguous'),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(PcbError, message):
                prepare_core(source().replace(before, after))

    def test_field_transfer_preflights_the_whole_mapping(self):
        owner, target = Element('Source'), Element('Target')
        first = owner.add('A', 1)
        owner.add('B', 2)
        target.add('Second', 3)
        with self.assertRaisesRegex(PcbError, 'ambiguous'):
            move_fields(owner, target, {'A': 'First', 'B': 'Second'})
        self.assertIs(first.parent, owner)
        self.assertEqual(first.kind, 'A')
        self.assertIsNone(target.child('First'))

    def test_binary_sheet_and_border_zones_bind_to_the_same_typed_records(self):
        data = binary_fixture()
        reader = Reader(sheet_fixture())
        read_groups(reader, Element('Unused'))
        sheet = read_sheet_layout(reader, data.board)
        result = assemble_core(data)
        self.assertIs(sheet.schema, settings_records.SHEET)
        self.assertIs(sheet.one('BorderZones').schema, settings_records.BORDER_ZONES)
        self.assertEqual(sheet['SheetWidth'], 1260)
        zones = sheet.one('BorderZones')
        self.assertEqual(zones['VertZones'], 6)
        zones['VertZones'] = 8
        self.assertEqual(result.document.one('/Board/SheetSettings/BorderZones')['VertZones'], 8)
        with self.assertRaises(TypeError):
            zones['HorzZones'] = 3.5


if __name__ == '__main__':
    unittest.main()
