"""A selected via style is the single source of its pad dimensions."""
import unittest
from unittest.mock import patch

from lib.common.asc import dumps as model_text
from lib.common.references import ReferenceError
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.model.objects import new_via_style, new_pad
from lib.pcb.tests.test_xml_via_masks import via_document, COMPONENT, PAD


def dimensions(pad):
    return tuple(pad[name] for name in ('PadWidth_New', 'PadHeight_New', 'PadHole', 'PadHoleH'))


def state(document):
    return model_text(document, preserve=False), tuple(document.references)


class ViaDimensionProjectionTests(unittest.TestCase):
    def test_style_edits_update_all_dependent_pads_without_rebuild(self):
        document = via_document()
        component, pad = document.one(COMPONENT), document.one(PAD)
        copied = document.copy(component, fields={'RefDes': 'V2'})
        with patch.object(document, 'rebuild', side_effect=AssertionError('unexpected rebuild')):
            component['Via']['Size'] = 6
            component['Via']['HoleSize'] = 2
        self.assertEqual(dimensions(pad), (6, 6, 2, 2))
        self.assertEqual(dimensions(copied.one('Pattern/Pads/Pad')), (6, 6, 2, 2))
        self.assertEqual(tuple(component.one('Pattern')[name] for name in ('Width', 'Height', 'PadWidth', 'PadHeight')),
                         (6, 6, 6, 6))
        document.references.validate()

    def test_controlled_dimensions_and_fixed_geometry_reject_independent_edits(self):
        document = via_document()
        pad = document.one(PAD)
        before = state(document)
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            pad['PadWidth_New'] = 6
        self.assertEqual(state(document), before)
        with self.assertRaises(ReferenceError):
            pad['PadCorner'] = 2
        self.assertEqual(state(document), before)

    def test_retarget_and_release_keep_the_last_current_geometry(self):
        document = via_document()
        component, pad = document.one(COMPONENT), document.one(PAD)
        style = document.one('/Board/ViaStyles').append(new_via_style('Large', size=6, hole_size=2))
        with patch.object(document, 'rebuild', side_effect=AssertionError('unexpected rebuild')):
            component['Via'] = style
            self.assertEqual(dimensions(pad), (6, 6, 2, 2))
            component['Via'] = None
            style['Size'] = 7
            self.assertEqual(dimensions(pad), (6, 6, 2, 2))
            pad['PadWidth_New'] = 5
            component['Via'] = style
            self.assertEqual(dimensions(pad), (7, 7, 2, 2))
        document.references.validate()

    def test_graph_retarget_updates_dimensions_and_foreign_targets_fail_atomically(self):
        document = via_document()
        component, pad = document.one(COMPONENT), document.one(PAD)
        style = document.one('/Board/ViaStyles').append(new_via_style('Large', size=6, hole_size=2))
        reference = document.references.outgoing(component, role='via-style')[0]
        document.references.retarget(reference, style)
        self.assertEqual(dimensions(pad), (6, 6, 2, 2))
        foreign = via_document().one(COMPONENT)['Via']
        before = state(document)
        with self.assertRaises(ReferenceError):
            document.references.retarget(reference, foreign)
        self.assertEqual(state(document), before)
        document.references.validate()

    def test_type_changes_release_and_restore_dimension_projections(self):
        document = via_document()
        component, pad = document.one(COMPONENT), document.one(PAD)
        pattern = component.one('Pattern')
        style = component['Via']
        with patch.object(document, 'rebuild', side_effect=AssertionError('unexpected rebuild')):
            pattern['Type'] = 14
            pad['PadWidth_New'] = 5
            style['Size'] = 7
            self.assertEqual(pad['PadWidth_New'], 5)
            pattern['Type'] = 16
            self.assertEqual(dimensions(pad), (7, 7, style['HoleSize'], style['HoleSize']))
        document.references.validate()

    def test_invalid_type_change_is_atomic(self):
        document = via_document()
        pattern, pad = document.one(COMPONENT+'/Pattern'), document.one(PAD)
        pattern['Type'] = 14
        pad['PadShape_New'] = 2
        before = state(document)
        with self.assertRaises(ReferenceError):
            pattern['Type'] = 16
        self.assertEqual(state(document), before)
        self.assertFalse(document.references.manages(pad.one('PadWidth_New')))
        pad['PadShape_New'] = 0
        pattern['Type'] = 16
        self.assertTrue(document.references.manages(pad.one('PadWidth_New')))
        document.references.validate()

    def test_enabled_changes_release_and_restore_projections(self):
        document = via_document()
        component, pad = document.one(COMPONENT), document.one(PAD)
        style = component['Via']
        component['Enabled'] = False
        pad['PadWidth_New'] = 5
        style['Size'] = 7
        self.assertEqual(pad['PadWidth_New'], 5)
        component['Enabled'] = True
        self.assertEqual(pad['PadWidth_New'], 7)
        document.references.validate()

    def test_clone_owns_its_style_and_component_removal_releases_copies(self):
        document = via_document()
        cloned = document.clone()
        cloned.one(COMPONENT)['Via']['Size'] = 7
        self.assertEqual(cloned.one(PAD)['PadWidth_New'], 7)
        self.assertNotEqual(document.one(PAD)['PadWidth_New'], 7)
        component = document.one(COMPONENT)
        document.remove(component)
        document.one('/Board/ViaStyles/ViaStyle')['Size'] = 8
        document.references.validate()
        cloned.references.validate()

    def test_a_second_pad_cannot_be_attached_to_a_controlled_static_via(self):
        document = via_document()
        pads = document.one(COMPONENT+'/Pattern/Pads')
        extra = new_pad('2')
        before = state(document)
        with self.assertRaises(ReferenceError):
            pads.append(extra)
        self.assertIsNone(extra.parent)
        self.assertEqual(state(document), before)
        document.references.validate()

    def test_style_edits_export_with_consistent_dimensions_in_every_profile(self):
        document = via_document()
        style = document.one(COMPONENT)['Via']
        style['Size'], style['HoleSize'] = 6, 2
        before = state(document)
        for format, capabilities in FORMATS.items():
            for version in capabilities.write_versions:
                with self.subTest(format=format, version=version):
                    payload = io.serialize(document, format=format, version=version, report=ConversionReport())
                    rebuilt = io.parse(payload, report=ConversionReport())
                    self.assertEqual(dimensions(rebuilt.one(PAD)), (6, 6, 2, 2))
                    pattern = rebuilt.one(COMPONENT+'/Pattern')
                    self.assertEqual(tuple(pattern[name] for name in ('Width', 'Height', 'PadWidth', 'PadHeight')),
                                     (6, 6, 6, 6))
                    self.assertEqual(state(document), before)
                    rebuilt.references.validate()


if __name__ == '__main__':
    unittest.main()
