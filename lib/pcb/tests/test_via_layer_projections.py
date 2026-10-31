"""Style spans own via layer exclusions through ordinary atomic model edits."""
import unittest
from unittest.mock import patch

from lib.common.model import Element
from lib.common.references import Property, ReferenceError
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.model.objects import new_layer, new_via_style
from lib.pcb.model.via_layers import layer_targets
from lib.pcb.tests.test_via_dimension_projections import state
from lib.pcb.tests.test_xml_via_masks import via_document, COMPONENT, PAD


def design():
    document = via_document()
    layers = document.one('/Board/Layers')
    for name in ('Inner 1', 'Inner 2', 'Inner 3'):
        layers.insert(new_layer(name), len(layers.children())-1)
    return document, layers.children('Layer'), document.one(COMPONENT)['Via']


class ViaLayerProjectionTests(unittest.TestCase):
    def test_span_edits_update_every_via_and_retain_surviving_rows(self):
        document, layers, style = design()
        pad = document.one(PAD)
        copied = document.copy(document.one(COMPONENT), fields={'RefDes': 'V2'})
        with patch.object(document, 'rebuild', side_effect=AssertionError('unexpected rebuild')):
            style['Span'] = (layers[1], layers[3])
            self.assertEqual(layer_targets(pad), (layers[0], layers[4]))
            bottom = pad.select('BlindLayer/Item')[-1]
            style['Span'] = (layers[0], layers[3])
            self.assertEqual(layer_targets(pad), (layers[4],))
            self.assertIs(pad.one('BlindLayer/Item'), bottom)
            self.assertEqual(layer_targets(copied.one('Pattern/Pads/Pad')), (layers[4],))
            style['Span'] = None
            self.assertEqual(layer_targets(pad), ())
        document.validate()

    def test_stack_insertion_and_reordering_update_exclusions_by_identity(self):
        document, layers, style = design()
        style['Span'] = (layers[1], layers[3])
        pad, stack = document.one(PAD), layers[0].parent
        first = pad.select('BlindLayer/Item')[0]
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            added = stack.insert(new_layer('New top'), 0)
            self.assertEqual(layer_targets(pad), (added, layers[0], layers[4]))
            layers[2].move_to(stack, 0)
            self.assertEqual(layer_targets(pad), (layers[2], added, layers[0], layers[4]))
        self.assertIs(pad.select('BlindLayer/Item')[2], first)
        document.validate()

    def test_managed_rows_cannot_be_changed_independently(self):
        document, layers, style = design()
        style['Span'] = (layers[1], layers[3])
        pad = document.one(PAD)
        row = pad.select('BlindLayer/Item')[0]
        before = state(document)
        for edit in (lambda: row.set('Layer', layers[2]),
                     lambda: document.remove(row),
                     lambda: row.move_to(row.parent, 1),
                     lambda: pad.one('BlindLayer').append(Element('Item'))):
            with self.assertRaises(ReferenceError):
                edit()
            self.assertEqual(state(document), before)
        document.validate()

    def test_dependent_row_removal_is_checked_before_the_span_changes(self):
        document, layers, style = design()
        style['Span'] = (layers[1], layers[3])
        row = document.one(PAD).select('BlindLayer/Item')[0]
        probe = document.root.add('Probe', 0)
        link = document.references.bind(probe, row, Property(probe, 'Lay'), role='probe')
        before = state(document)
        with self.assertRaisesRegex(ReferenceError, 'referenced content'):
            style['Span'] = (layers[0], layers[3])
        self.assertEqual(state(document), before)
        document.references.discard(link)
        style['Span'] = (layers[0], layers[3])
        self.assertEqual(layer_targets(document.one(PAD)), (layers[4],))
        document.validate()

    def test_retargeting_and_releasing_materialize_the_current_exclusions(self):
        document, layers, style = design()
        component, pad = document.one(COMPONENT), document.one(PAD)
        other = style.parent.append(new_via_style('Blind', size=6, hole_size=2))
        other['Span'] = (layers[1], layers[3])
        link = document.references.outgoing(component, role='via-style')[0]
        document.references.retarget(link, other)
        self.assertEqual(layer_targets(pad), (layers[0], layers[4]))
        rows = tuple(pad.select('BlindLayer/Item'))
        component['Via'] = None
        other['Span'] = None
        self.assertEqual(tuple(pad.select('BlindLayer/Item')), rows)
        rows[0]['Layer'] = layers[2]
        component['Via'] = other
        self.assertEqual(layer_targets(pad), ())
        document.validate()

    def test_type_and_enabled_transitions_release_and_restore_the_style(self):
        for record, field, disabled, enabled in (('Pattern', 'Type', 14, 16), ('', 'Enabled', False, True)):
            with self.subTest(field=field):
                document, layers, style = design()
                style['Span'] = (layers[1], layers[3])
                component, pad = document.one(COMPONENT), document.one(PAD)
                owner = component.one(record) if record else component
                owner[field] = disabled
                style['Span'] = None
                self.assertEqual(layer_targets(pad), (layers[0], layers[4]))
                pad.select('BlindLayer/Item')[0]['Layer'] = layers[2]
                owner[field] = enabled
                self.assertEqual(layer_targets(pad), ())
                document.validate()

    def test_clone_remaps_layers_and_does_not_share_derived_rows(self):
        document, layers, style = design()
        style['Span'] = (layers[1], layers[3])
        cloned = document.clone()
        cloned_style = cloned.one(COMPONENT)['Via']
        cloned_layers = cloned.select('/Board/Layers/Layer')
        self.assertEqual(layer_targets(cloned.one(PAD)), (cloned_layers[0], cloned_layers[4]))
        cloned_style['Span'] = None
        self.assertEqual(layer_targets(document.one(PAD)), (layers[0], layers[4]))
        self.assertEqual(layer_targets(cloned.one(PAD)), ())
        cloned.validate()
        document.validate()

    def test_first_assignment_and_direct_span_retarget_use_the_same_projection(self):
        document, layers, style = design()
        component, pad = document.one(COMPONENT), document.one(PAD)
        component['Via'] = None
        style['Span'] = (layers[1], layers[3])
        self.assertEqual(layer_targets(pad), ())
        component['Via'] = style
        self.assertEqual(layer_targets(pad), (layers[0], layers[4]))
        link = document.references.outgoing(style, role='via-span-from')[0]
        document.references.retarget(link, layers[2])
        self.assertEqual(layer_targets(pad), (layers[0], layers[1], layers[4]))
        before = state(document)
        with self.assertRaises(ReferenceError):
            document.references.retarget(link, layers[4])
        self.assertEqual(state(document), before)
        document.validate()

    def test_bounded_style_round_trips_every_output_profile_without_conflict(self):
        document, layers, style = design()
        style['Span'] = (layers[1], layers[3])
        before = state(document)
        for format, capabilities in FORMATS.items():
            for version in capabilities.write_versions:
                with self.subTest(format=format, version=version):
                    report = ConversionReport()
                    payload = io.serialize(document, format=format, version=version, report=report)
                    rebuilt = io.parse(payload, report=ConversionReport())
                    self.assertEqual([row['Lay'] for row in rebuilt.one(PAD).select('BlindLayer/Item')], [0, 4])
                    self.assertFalse(any(notice.rule == 'static-via-style' for notice in report.warnings))
                    self.assertEqual(state(document), before)
                    rebuilt.validate()


if __name__ == '__main__':
    unittest.main()
