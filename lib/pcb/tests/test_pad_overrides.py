"""Pad overrides follow copper-layer identities through ordinary edits."""
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib.common.model import Value
from lib.common.references import Property, ReferenceError
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.model.pad_records import LAYER_MEMBER, THERMAL, TEARDROP
from lib.pcb.tests.test_core_assembly import fixture


def design():
    decoded = fixture()
    decoded.upgrades = SimpleNamespace(nets=(), separate_traces=())
    layers = decoded.board.add('Layers')
    for index, name in enumerate(('Top', 'Bottom')):
        layer = layers.add('Layer', name)
        layer.add('Number', index)
        layer.add('Type', 0)
    pad = decoded.board.one('Components/Component/Pattern/Pads').children()[1]
    pad.add('HideLayer').add('Item', 1)
    pad.add('BlindLayer').add('Item', 0)
    thermals = pad.add('CustomSpokes')
    thermals.add('CustomSpoke', 1, 1, 4, Decimal('.99'))
    thermals.add('CustomSpoke', -1, 0, 0, Decimal('.33'))
    pad.add('TeardropParams').add('PadViaLength', Decimal('.7'))
    decoded.board.one('Nets/Net').add('TeardropParams').add('TraceLength', Decimal('.3'))
    return assemble_rules(decoded)


class PadOverrideTests(unittest.TestCase):
    def test_import_consumes_layer_selectors_and_keeps_global_thermal_absent(self):
        result = design()
        pad = result.routing.core.pads[41, 5]
        hidden = pad.one('HideLayer/Item')
        blind = pad.one('BlindLayer/Item')
        specific, global_setting = pad.select('CustomSpokes/CustomSpoke')
        self.assertIs(hidden.schema, LAYER_MEMBER)
        self.assertIs(specific.schema, THERMAL)
        self.assertIs(hidden['Layer'], result.layers[1])
        self.assertIs(blind['Layer'], result.layers[0])
        self.assertEqual(hidden.values, (1,))
        self.assertIs(specific['Layer'], result.layers[1])
        self.assertEqual(specific.values, (1, 1, 4, Decimal('.99')))
        self.assertIsNone(global_setting['Layer'])
        self.assertEqual(global_setting.values, (-1, 0, 0, Decimal('.33')))
        self.assertIsNone(specific.child('Lay'))
        self.assertFalse(any(isinstance(item, Value) for item in hidden.items))
        self.assertIs(pad.one('TeardropParams').schema, TEARDROP)
        self.assertIs(result.document.one('/Board/Nets/Net/TeardropParams').schema, TEARDROP)
        pad.one('TeardropParams')['PadViaLength'] = Decimal('.8')
        self.assertEqual(pad.one('TeardropParams')['PadViaLength'], Decimal('.8'))

    def test_reordering_and_retargeting_update_projections_without_global_scans(self):
        result = design()
        document = result.document
        hidden = result.routing.core.pads[41, 5].one('HideLayer/Item')
        probe = document.root.add('Probe', 0)
        document.references.bind(probe, hidden, Property(probe, 'Lay'), role='probe')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            result.layers[1].move_to(result.layers[1].parent, 0)
            self.assertEqual(probe.values, (0,))
            hidden['Layer'] = result.layers[0]
            self.assertEqual(probe.values, (1,))

    def test_duplicate_and_foreign_targets_are_rejected_atomically(self):
        result = design()
        pad = result.routing.core.pads[41, 5]
        specific, global_setting = pad.select('CustomSpokes/CustomSpoke')
        with self.assertRaises(ReferenceError):
            global_setting['Layer'] = specific['Layer']
        self.assertIsNone(global_setting['Layer'])
        other = design()
        with self.assertRaises(ReferenceError):
            specific['Layer'] = other.layers[0]
        self.assertIs(specific['Layer'], result.layers[1])

    def test_cloning_and_copying_retain_and_remap_override_relationships(self):
        result = design()
        pad = result.routing.core.pads[41, 5]
        copy = result.document.copy(pad, parent=pad.parent)
        self.assertIs(copy.one('HideLayer/Item')['Layer'], result.layers[1])
        cloned = result.document.clone()
        copied_pad = cloned.one('/Board/Components/Component/Pattern/Pads/Pad[1]')
        self.assertIs(copied_pad.one('CustomSpokes/CustomSpoke[1]')['Layer'],
                      cloned.one('/Board/Layers/Layer[2]'))
        self.assertIsNone(copied_pad.one('CustomSpokes/CustomSpoke[2]')['Layer'])

    def test_removed_override_releases_its_layer_relationship(self):
        result = design()
        pad = result.routing.core.pads[41, 5]
        hidden = pad.one('HideLayer/Item')
        result.document.remove(hidden)
        self.assertIsNone(hidden.parent)
        self.assertFalse(result.document.references.outgoing(hidden, role='copper-layer'))


if __name__ == '__main__':
    unittest.main()
