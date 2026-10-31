"""Earlier PCB label choices become one current placement per label."""
import math
import unittest

from lib.common.legacy_labels import LegacyLabelSlot
from lib.pcb.formats.dip.legacy_markings import global_alignment, resolve_markings


def placements(**options):
    return resolve_markings(version=options.pop('version', 46),
                            measure_width=options.pop('measure_width', lambda name: 0), **options)


class LegacyMarkingTests(unittest.TestCase):
    def test_global_positions_upgrade_without_guessing_unknown_choices(self):
        self.assertEqual(global_alignment(0), 1)
        self.assertEqual(global_alignment(6), 7)
        self.assertEqual(global_alignment(8), 8)
        self.assertEqual(global_alignment(-1), -1)

    def test_default_automatic_refdes_resolves_to_top_without_inventing_coordinates(self):
        labels, users = placements(dimensions=(20, 5))
        self.assertEqual(labels['RefDes'], (0, 2, 0, 0, 0, 0, 0))
        self.assertEqual(labels['Name'], (0, 0, 0, 0, 0, 0, 0))
        self.assertEqual(users, ())

    def test_rotated_placement_becomes_current_explicit_text_angle_and_anchor(self):
        labels, _ = placements(dimensions=(49.53, 15.24), angle=math.pi)
        self.assertEqual(labels['RefDes'], (0, 8, 0, 1, 0, 7.62, -math.pi))

    def test_quarter_turn_uses_stable_rectangular_math(self):
        labels, _ = placements(dimensions=(10, 4), angle=math.pi/2,
                               first=LegacyLabelSlot(alignment=2, x_shift=2, y_shift=3))
        self.assertEqual(labels['RefDes'], (0, 8, 0, 1, 5, 2, -math.pi/2))

    def test_authored_shift_survives_modernization_without_rounding_to_export_precision(self):
        labels, _ = placements(dimensions=(18.8976, 5.4), first=LegacyLabelSlot(y_shift=-4.9762))
        self.assertEqual(labels['RefDes'][:4], (0, 8, 0, 1))
        self.assertAlmostEqual(labels['RefDes'][5], 2.2762)

    def test_explicit_choice_hides_its_inherited_choice_and_selects_one_current_label(self):
        labels, _ = placements(first=LegacyLabelSlot(mode=4), global_second=(1, 7))
        self.assertEqual(labels['RefDes'][0], 2)
        self.assertEqual(labels['Value'][:2], (1, 2))
        self.assertEqual(labels['Name'][1], 3)
        hidden, _ = placements(first=LegacyLabelSlot(mode=1))
        self.assertEqual(hidden['RefDes'][0], 2)
        self.assertFalse(any(value[0] == 1 for value in hidden.values()))

    def test_schema_39_separates_earlier_user_choices_from_pattern_and_datasheet(self):
        old, users = placements(version=38, user_field_count=2,
                                first=LegacyLabelSlot(mode=6), second=LegacyLabelSlot(mode=7))
        self.assertEqual([value[0] for value in users], [1, 1])
        self.assertEqual(old['Pattern'][0], 0)
        self.assertEqual(old['Datasheet'][0], 0)
        current, users = placements(version=39, user_field_count=2,
                                    first=LegacyLabelSlot(mode=6), second=LegacyLabelSlot(mode=7))
        self.assertEqual(current['Manufacturer'][0], 1)
        self.assertEqual(current['Datasheet'][0], 1)
        self.assertEqual([value[0] for value in users], [0, 0])

    def test_invalid_user_index_does_not_select_another_field(self):
        labels, users = placements(user_field_count=1, first=LegacyLabelSlot(mode=10))
        self.assertEqual(labels['RefDes'][0], 2)
        self.assertEqual(users[0][0], 0)

    def test_bottom_side_swaps_edges_but_retains_explicit_corner_coordinates(self):
        labels, _ = placements(bottom_side=True, first=LegacyLabelSlot(alignment=4))
        self.assertEqual(labels['RefDes'][1], 5)
        labels, _ = placements(bottom_side=True, dimensions=(10, 4), first=LegacyLabelSlot(alignment=6))
        self.assertEqual(labels['RefDes'], (0, 8, -1, 1, 5, -2, 0))

    def test_measured_text_width_and_outside_text_are_independent_inputs(self):
        labels, _ = placements(dimensions=(4, 20), measure_width=lambda name: 5)
        self.assertEqual(labels['RefDes'][1], 4)
        explicit, _ = placements(dimensions=(4, 20), outside_text=True, measure_width=lambda name: 5)
        self.assertEqual(explicit['RefDes'], (0, 8, 0, 1, -2, 0, math.pi/2))

    def test_repeated_category_uses_later_explicit_edge_after_earlier_shift(self):
        labels, _ = placements(dimensions=(20, 10),
            first=LegacyLabelSlot(mode=4, x_shift=2, y_shift=1),
            second=LegacyLabelSlot(mode=4, alignment=5))
        self.assertEqual(labels['Value'], (1, 5, 0, 1, 2, -6, 0))

    def test_repeated_category_later_shift_resolves_from_its_own_edge(self):
        labels, _ = placements(dimensions=(20, 10),
            first=LegacyLabelSlot(mode=4, alignment=2, x_shift=2),
            second=LegacyLabelSlot(mode=4, alignment=5, x_shift=3, y_shift=4))
        # At the right edge, the vertical shift extends X and the horizontal
        # shift moves Y; the resulting explicit text points along that edge.
        self.assertEqual(labels['Value'], (1, 8, 0, -1, 14, -3, math.pi/2))


if __name__ == '__main__':
    unittest.main()
