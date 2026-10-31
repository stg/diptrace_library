"""ASC board choices and hierarchy use current facts, not saved source keys."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.global_projection import project_globals, BOARD_FIELDS
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.errors import PcbError
from lib.pcb.model.hierarchy import linkage_path
from lib.pcb.tests.test_component_projection import design as component_design, project_input, signature


def design():
    source = project_input(component_design())
    board = source.one('/Board')
    for name, value in dict(RelSchem='design.dch', RelSchem_Variable='${PROJECT}/design.dch',
            ProjectDir='project', CompFontName='Arial', CompFontSize=Decimal('1.25'),
            PatternFontVector='Y', PatternFontWidth=-1, PatternFontScale=Decimal('1.1'),
            RotateMarkings='N', Locked='Y', Toplock='Y', Bottomlock='N', OriginX=12, OriginY=-6,
            AssyObjSilk='Y', AssyObjMarking='N', LockNetStructure='Y', UserField1='Order',
            UserField2='Revision', RefDes_Global_SilkShow=1, RefDes_Global_SilkAlign=7,
            Name_Global_AssyShow=2, Name_Global_AssyAlign=1, PanelX=2, PanelY=3,
            PanelDX=6, PanelDY=9, RailShow='Y', RailLeft=3, RailRight=6, RailTop=9,
            RailBottom=12, PanelExclude='N').items():
        board.add(name, value)
    field = board.add('Userfields_Global').add('Userfield')
    for name, value in dict(Name='Order', Value='ABC', SilkShow=1, SilkAlign=2, AssyShow=2, AssyAlign=7).items():
        field.add(name, value)
    variants = board.add('AssemblyVariants')
    variants.add('AssemblyVariant', 'Full')
    variants.add('AssemblyVariant', 'Reduced')
    sheets = board.add('Hierarchy_Sheets')
    sheets.add('HSheet', 'Controller', 40).add('pt', 91, 'Top block')
    sheets.add('HSheet', 'Channel', 12).add('pt', 107, 'Nested block')
    component = board.one('Components/Component')
    component.one('HiddenId').set_values(75)
    path = component.one('Hidden_Path')
    path.set_values(3)
    for key in (91, 107, 75):
        path.add('pt', key)
    return assemble_graphics(prepare_core(dumps(source, preserve=False))).document


def reopen(document, *, report=None):
    source = project_input(document)
    for row in tuple(project_globals(document.one('/Board'), report=report).children()):
        row.move_to(source.one('/Board'))
    return assemble_graphics(prepare_core(dumps(source, preserve=False))).document


def global_signature(document):
    board = document.one('/Board')
    return {name: board.get(name) for name in BOARD_FIELDS} | {
        name: signature(board.one(name)) for name in ('Userfields_Global', 'AssemblyVariants', 'HierarchySheets')}


class GlobalProjectionTests(unittest.TestCase):
    def test_globals_markings_user_fields_variants_and_hierarchy_round_trip(self):
        document = design()
        before, report = dumps(document, preserve=False), ConversionReport()
        rebuilt = reopen(document, report=report)
        self.assertEqual(global_signature(rebuilt), global_signature(document))
        self.assertEqual(global_signature(reopen(rebuilt)), global_signature(document))
        self.assertEqual(dumps(document, preserve=False), before)
        self.assertEqual(report.notices, [])
        self.assertEqual(linkage_path(rebuilt.one('/Board/Components/Component')), (91, 107, 75))
        self.assertIsNone(document.one('/Board/Userfields_Global').child('Userfield'))

    def test_persistent_block_keys_rename_and_order_remain_distinct_from_refdes(self):
        document = design()
        board = document.one('/Board')
        sheet = board.one('HierarchySheets/HSheet[1]')
        block = sheet.one('UpdateIds/UId')
        block['Id'], block['Name'] = 104, 'Renamed instance'
        sheet['Number'], sheet['Name'] = 44, 'Renamed sheet'
        sheet.move_to(sheet.parent)
        board.one('AssemblyVariants/AssemblyVariant[1]').move_to(board.one('AssemblyVariants'))
        component = board.one('Components/Component')
        component['HiddenId'], component['RefDes'] = 80, 'U12'
        output = project_globals(board)
        self.assertEqual(output.one('Hierarchy_Sheets/HSheet[2]').values, ('Renamed sheet', 44))
        self.assertEqual(output.one('Hierarchy_Sheets/HSheet[2]/pt').values, (104, 'Renamed instance'))
        rebuilt = reopen(document)
        self.assertEqual(linkage_path(rebuilt.one('/Board/Components/Component')), (104, 107, 80))
        self.assertEqual(rebuilt.one('/Board/Components/Component')['RefDes'], 'U12')
        self.assertEqual(global_signature(rebuilt), global_signature(document))

    def test_known_options_warn_while_selection_is_quiet_information(self):
        document = design()
        board = document.one('/Board')
        board['CompFontMono'], board['SchemNetClasses'], board['ShieldGroup'] = True, True, 0
        board['Selected'] = True
        report = ConversionReport()
        output = project_globals(board, report=report)
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'board-compfontmono', 'board-schemnetclasses', 'board-shieldgroup'})
        self.assertEqual([notice.rule for notice in report.infos], ['board-selection'])
        self.assertFalse(any(output.child(name) is not None for name in ('CompFontMono','SchemNetClasses','ShieldGroup','Selected')))
        self.assertEqual((board['CompFontMono'],board['SchemNetClasses'],board['ShieldGroup']), (True,True,0))

    def test_unmapped_owned_content_fails_before_silently_dropping_it(self):
        for path in ('Userfields_Global/UserField', 'HierarchySheets/HSheet[1]', 'AssemblyVariants/AssemblyVariant[1]'):
            document = design()
            document.one('/Board/'+path).add('Unmapped', 12)
            with self.subTest(path=path), self.assertRaises(PcbError):
                project_globals(document.one('/Board'))

    def test_legacy_global_user_field_spelling_is_normalized_but_bad_headers_fail(self):
        for kind in ('Userfield', 'UserField'):
            document = design()
            source = project_input(document)
            fields = source.one('/Board').add('Userfields_Global')
            fields.add(kind).add('Name', 'Code')
            current = assemble_graphics(prepare_core(dumps(source, preserve=False))).document
            self.assertEqual([row['Name'] for row in current.select('/Board/Userfields_Global/UserField')],
                             ['Code', 'Order'])
        source.one('/Board/Userfields_Global').children()[0].set_values('unexpected header')
        with self.assertRaisesRegex(PcbError, 'named global user-field'):
            prepare_core(dumps(source, preserve=False))


if __name__ == '__main__':
    unittest.main()
