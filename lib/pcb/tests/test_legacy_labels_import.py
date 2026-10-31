"""Older marking settings import into the current editable PCB vocabulary."""
import math
from types import SimpleNamespace
import unittest

from lib.common.model import Element
from lib.common.footprint_objects import new_pattern, new_pattern_drawing
from lib.common.text.layout import TextLayout
from lib.common.text.vector import TextMetrics
from lib.pcb.formats.dip.components import ComponentUpgrade, DrawingUpgrade
from lib.pcb.formats.dip.legacy_labels_import import modernize_markings
from lib.pcb.formats.import_context import ImportContext
from lib.pcb.model.board_records import bind_records


def fixture(*, version=46, global_choices=(2, 6, 0, 6), choices=(0, 0, 0, 0),
            shifts=(0, 0, 0, 0), angle=0, extra=0, size=(20, 5)):
    root = Element('')
    board = root.add('Board')
    for name, value in dict(CompFontSize=2, CompFontName='Label font',
                            PatternFontVector=True, PatternFontWidth=-2, PatternFontScale=1).items():
        board.add(name, value)
    component = board.add('Components').add('Component')
    for name, value in dict(Name='Device', RefDes='U1', Value='Measured', Manufacturer='',
                            Datasheet='', Angle=angle, BottomSide=False).items():
        component.add(name, value)
    component.add('UserFields').add('UserField', 'Order', 'A42', 1)
    pattern = component.append(new_pattern('Package'))
    pattern['Width'], pattern['Height'] = size
    item = ComponentUpgrade(component, choices, shifts, (0, 0, extra), ())
    decoded = SimpleNamespace(root=root, board=board, header=SimpleNamespace(version=version),
        upgrades=SimpleNamespace(initial=SimpleNamespace(legacy_markings=global_choices),
                                 components=(item,)))
    return decoded, component


class LegacyLabelImportTests(unittest.TestCase):
    def test_globals_and_explicit_selection_become_named_current_fields(self):
        decoded, component = fixture(global_choices=(0, 6, 3, 6), choices=(3, 0, 0, 0))
        modernize_markings(decoded, layout=TextLayout())
        board = decoded.board
        self.assertEqual((board['RefDes_Global_SilkShow'], board['Value_Global_SilkShow']), (2, 1))
        self.assertEqual((board['Value_Global_SilkAlign'], board['Value_Global_AssyShow']), (7, 2))
        self.assertEqual((component['RefDes_SilkShow'], component['RefDes_SilkAlign']), (1, 0))
        self.assertEqual(component['Value_AssyAngle'], 0)

    def test_quarter_turn_selection_dimensions_and_extra_rotation_are_distinct(self):
        decoded, component = fixture(angle=math.pi/2, extra=90, size=(20, 5))
        modernize_markings(decoded, layout=TextLayout(lambda *args: TextMetrics(0, 20)))
        self.assertEqual(component['RefDes_SilkAlign'], 8)
        self.assertEqual((component['RefDes_SilkX'], component['RefDes_SilkY']), (0, 10))
        self.assertEqual(float(component['RefDes_SilkAngle']), -math.pi)
        self.assertEqual(float(component['Angle']), math.pi/2)  # Frame upgrade owns placement.

    def test_old_automatic_edge_uses_system_measurement_even_for_vector_drawings(self):
        calls = []

        def measure(text, family, point_size):
            calls.append((text, family, point_size))
            return TextMetrics(50, 20)

        decoded, component = fixture(size=(4, 20))
        modernize_markings(decoded, layout=TextLayout(measure))
        self.assertEqual(component['RefDes_SilkAlign'], 4)
        self.assertEqual(calls, [('U1', 'Label font', 20)])
        self.assertTrue(decoded.board['PatternFontVector'])

    def test_width_service_is_lazy_and_required_only_when_placement_needs_it(self):
        decoded, component = fixture(size=(20, 4))
        modernize_markings(decoded, layout=TextLayout())
        self.assertEqual(component['RefDes_SilkAlign'], 2)
        decoded, _ = fixture(size=(4, 20))
        with self.assertRaisesRegex(NotImplementedError, 'system font measurements'):
            modernize_markings(decoded, layout=TextLayout())

    def test_literal_outside_text_forces_explicit_placement_but_generated_text_does_not(self):
        for generated in (False, True):
            with self.subTest(generated=generated):
                decoded, component = fixture()
                shape = component.one('Pattern/Shapes').append(new_pattern_drawing(kind=7))
                shape.one('Points_New').add('pt', 100, 0)
                item = decoded.upgrades.components[0]
                decoded.upgrades.components = (ComponentUpgrade(component, item.legacy_markings,
                    item.legacy_text_positions, item.legacy_field_bindings,
                    (DrawingUpgrade(shape, (), 0, generated),)),)
                modernize_markings(decoded, layout=TextLayout())
                self.assertEqual(component['RefDes_SilkAlign'], 2 if generated else 8)

    def test_user_placement_is_owned_by_the_current_field_without_old_slot_backups(self):
        decoded, component = fixture(choices=(8, 3, 1, 0), shifts=(2, 1, 0, 0))
        modernize_markings(decoded, layout=TextLayout())
        user = component.one('UserFields/UserField')
        self.assertEqual(user.values, ('Order', 'A42', 1))
        self.assertEqual((user['SilkShow'], user['SilkAlign'], user['SilkX'], user['SilkY']), (1, 8, 2, 3.5))
        self.assertEqual(user['AssyShow'], 0)

    def test_modern_inputs_are_untouched(self):
        decoded, component = fixture(version=47)
        modernize_markings(decoded, layout=TextLayout())
        self.assertIsNone(component.child('RefDes_SilkShow'))
        self.assertIsNone(decoded.board.child('RefDes_Global_SilkShow'))

    def test_explicit_pattern_and_manufacturer_choices_are_distinct(self):
        decoded, component = fixture(global_choices=(6, 6, 0, 6), choices=(5, 0, 6, 0))
        modernize_markings(decoded, layout=TextLayout())
        self.assertEqual((component['Pattern_SilkShow'], component['Manufacturer_SilkShow']), (1, 1))
        self.assertEqual((decoded.board['Pattern_Global_SilkShow'],
                          decoded.board['Manufacturer_Global_SilkShow']), (2, 1))

    def test_older_global_pattern_selection_is_not_an_unknown_category(self):
        decoded, _ = fixture(global_choices=(5, 3, 0, 6))
        modernize_markings(decoded, layout=TextLayout())
        self.assertEqual((decoded.board['Pattern_Global_SilkShow'],
                          decoded.board['Pattern_Global_SilkAlign']), (1, 4))
        self.assertFalse(decoded.board.one('Userfields_Global').children())

    def test_each_older_global_user_slot_keeps_its_name_and_display_choices(self):
        decoded, _ = fixture(global_choices=(4, 1, 4, 4))
        decoded.board.add('UserField1', 'Order Code')
        decoded.board.add('UserField2', 'Assembly Note')
        modernize_markings(decoded, layout=TextLayout())
        bind_records(decoded.board)
        fields = decoded.board.select('Userfields_Global/UserField')
        self.assertEqual([(row['Name'], row['Value'], row['SilkShow'], row['SilkAlign'],
                           row['AssyShow'], row['AssyAlign']) for row in fields],
                         [('Order Code', 'ordercode', 1, 2, 0, 0),
                          ('Assembly Note', 'assemblynote', 1, 5, 0, 0)])
        self.assertTrue(all(row.child('Value') is None for row in fields))

    def test_repeated_global_user_names_preserve_two_ordered_display_rules(self):
        decoded, _ = fixture(global_choices=(4, 0, 4, 5))
        decoded.board.add('UserField1', 'Code')
        decoded.board.add('UserField2', 'Code')
        modernize_markings(decoded, layout=TextLayout())
        fields = decoded.board.select('Userfields_Global/UserField')
        self.assertEqual([(row['Name'], row['SilkAlign']) for row in fields], [('Code', 1), ('Code', 6)])

    def test_pcb_and_schematic_share_the_same_layout_service(self):
        from lib.schematic.layout.text_layout import TextLayout as SchematicLayout
        layout = TextLayout()
        self.assertIs(SchematicLayout, TextLayout)
        self.assertIs(ImportContext(text_layout=layout).layout, layout)
        with self.assertRaises(TypeError):
            ImportContext(text_layout=object())


if __name__ == '__main__':
    unittest.main()
