"""Panel choices and authored tab positions remain data, without geometry work."""
from decimal import Decimal
import unittest

from lib.common.asc import loads, dumps
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.errors import PcbError
from lib.pcb.model import board_records
from lib.pcb.tests.test_asc_core import fixture


def source():
    syntax = loads(fixture())
    board = syntax.one('/Board')
    fields = dict(PanelX=2, PanelY=3, PanelDX=6, PanelDY=9, RailShow='Y',
                  RailLeft=3, RailRight=6, RailTop=9, RailBottom=12,
                  Locked='N', Toplock='Y', Bottomlock='N', RotateMarkings='N',
                  OriginX=12, OriginY=-6, CompFontSize=Decimal('2.5'),
                  CompFontName='Example', RelSchem='board.dch',
                  Panelize_Type=1, Panelize_TabWidth=12, Panelize_TabRadius=3,
                  Panelize_TabStep=90, Panelize_HoleDiam=Decimal('2.4'),
                  Panelize_HoleStep=3, Panelize_HoleInset=-1, Panelize_HoleKeepout=6,
                  Panelize_TabsDone='Y', Panelize_CombinedRadius=Decimal('1.5'),
                  Panelize_KeepMaterial='N', Panelize_BorderTabs=2, Panelize_Single='Y')
    for name, value in fields.items():
        board.add(name, value)
    horizontal, vertical = board.add('Panelize_HorzTabX'), board.add('Panelize_VertTabY')
    for value in (12, -3, Decimal('1.125')):
        horizontal.add('pt', value)
    for value in (15, 9):
        vertical.add('pt', value)
    return dumps(syntax, preserve=False)


class AscPanelTests(unittest.TestCase):
    def test_panel_settings_and_tab_order_enter_the_typed_shared_model(self):
        result = assemble_core(prepare_core(source()))
        board = result.document.one('/Board')
        original_x = result.components[17]['X']
        panel = board.one('Panel')
        self.assertIs(panel.schema, board_records.PANEL)
        self.assertEqual(panel['HoleDiam'], Decimal('2.4'))
        self.assertTrue(panel['PanelizeSingle'])
        self.assertTrue(panel['TabsDone'])
        self.assertFalse(panel['KeepMaterial'])
        self.assertEqual(panel['HoleInset'], -1)
        positions = panel.select('HorzTabsX/Item')
        self.assertEqual([row['Position'] for row in positions], [12, -3, Decimal('1.125')])
        self.assertEqual([row.values for row in panel.select('VertTabsY/Item')], [(15,), (9,)])
        positions[0]['Position'] = 18
        positions[0].move_to(positions[0].parent)
        self.assertEqual([row['Position'] for row in panel.select('HorzTabsX/Item')],
                         [-3, Decimal('1.125'), 18])
        panel['TabWidth'] = 30
        self.assertTrue(panel['TabsDone'])  # Editing data does not recalculate tabs.
        self.assertEqual(result.components[17]['X'], original_x)
        self.assertIsNone(board.child('Panelize_Type'))
        self.assertIsNone(board.child('Panelize_HorzTabX'))
        with self.assertRaises(TypeError):
            positions[0]['Position'] = 'here'

    def test_board_authoring_fields_are_typed_and_keep_their_distinct_meanings(self):
        result = assemble_core(prepare_core(source()))
        board = result.document.one('/Board')
        original_x = result.components[17]['X']
        self.assertEqual((board['PanelX'], board['PanelY'], board['PanelDX'], board['PanelDY']), (2, 3, 6, 9))
        self.assertFalse(board['Locked'])
        self.assertTrue(board['Toplock'])
        self.assertFalse(board['CompRotate'])
        self.assertEqual(board['CompFontSize'], Decimal('2.5'))
        self.assertEqual(board['RelSchem'], 'board.dch')
        self.assertIsNone(board.child('RotateMarkings'))
        board['OriginX'] = 90
        board['CompRotate'] = True
        self.assertEqual(result.components[17]['X'], original_x)
        with self.assertRaises(TypeError):
            board['PanelX'] = 'two'

    def test_optional_panel_data_is_not_created_when_absent(self):
        result = assemble_core(prepare_core(fixture()))
        self.assertIsNone(result.document.one('/Board').child('Panel'))

    def test_cached_extents_do_not_compete_with_current_geometry(self):
        expected = assemble_core(prepare_core(source())).components[17]
        syntax = loads(source())
        board = syntax.one('/Board')
        for name, value in dict(Xmin=90, Ymin=80, Xmax=-70, Ymax=-60).items():
            board.add(name, value)
        result = assemble_core(prepare_core(dumps(syntax, preserve=False)))
        board = result.document.one('/Board')
        self.assertFalse(any(board.child(name) is not None for name in ('Xmin', 'Ymin', 'Xmax', 'Ymax')))
        self.assertEqual((result.components[17]['X'], result.components[17]['Y']),
                         (expected['X'], expected['Y']))
        with self.assertRaisesRegex(PcbError, 'cached coordinate'):
            prepare_core(dumps(syntax, preserve=False).replace('(Xmin 90)', '(Xmin "invalid")'))

    def test_duplicate_and_malformed_panel_data_fail(self):
        for before, after, message in (
            ('(Panelize_Type 1)', '(Panelize_Type 1) (Panel (Type 2))', 'ambiguous Type'),
            ('(Panelize_Single "Y")', '(Panelize_Single "yes")', 'boolean'),
            ('(pt 12)', '(pt 12 13)', 'expected 1 pt values'),
            ('(pt 12)', '(pt "twelve")', 'invalid numeric'),
            ('(Panelize_HorzTabX', '(Panelize_HorzTabX 3', 'expected tab positions'),
            ('(RotateMarkings "N")', '(RotateMarkings "N") (CompRotate "Y")', 'ambiguous'),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(PcbError, message):
                prepare_core(source().replace(before, after))


if __name__ == '__main__':
    unittest.main()
