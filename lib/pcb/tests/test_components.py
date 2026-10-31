"""PCB component records keep placement, footprint and electrical data distinct."""
from decimal import Decimal
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.components import read_base_components
from lib.pcb.formats.dip.preamble import read_initial_sections
from lib.pcb.formats.dip.read import Reader
from .test_preamble import section_fixture


def component_fixture(version, *, kind=5, identifier=None, name='Resistor', refdes=None):
    writer = BinaryWriter()
    writer.buffer.extend(section_fixture(version)[:-3])

    def values(kind, *supplied):
        for value in supplied:
            if kind == 'text' and version < 38:
                data = value.encode('cp1252')
                writer.integer(len(data))
                writer.buffer.extend(data)
            else:
                getattr(writer, kind)(value)

    def component(index):
        values('boolean', True, False)
        values('integer', kind, 2, 1, 1, -1, index, 1)
        values('boolean', False)
        values('integer', 0, 0, 0, 0)
        values('number', 0, 0, 0, 0)
        values('boolean', False)
        values('integer', 0)
        values('boolean', False)
        values('integer', index+10 if identifier is None else identifier)
        values('number', 0, 0)
        values('boolean', True, False)
        values('integer', 1)
        values('text', 'Order', '0123')
        values('integer', 0, -1, -1)
        values('number', -1)
        values('boolean', False)
        values('text', 'generic.lib')
        values('integer', 1, 0)
        values('boolean', False, False, False, False)
        values('number', 12, 34, 3, 6)
        values('boolean', False)
        values('number', 0)
        values('boolean', True, False)
        values('integer', 0, 0)
        values('text', '0603')
        # Legacy dimensions are expressed for the rounded placement orientation.
        values('number', 6, 3, 1, 2, 0, 0)
        values('integer', 0)
        if version > 31:
            values('integer', 2, 20+index, 40+index)
        values('text', name, 'R'+str(index+1) if refdes is None else refdes, '1k', 'R')
        values('integer', 3)
        for pad in range(3):
            values('boolean', False)
            values('integer', pad, 0 if pad == 1 else -1)
            values('number', -1, 2)
            values('text', str(pad), 'Terminal')
            values('number', 1, 2, 0, 0)
            values('integer', 0)
            values('boolean', True)
            values('integer', 2)
            values('boolean', False)
            values('integer', 3)
            values('number', -.5, -.5, .5, -.5, 0, .5)
            values('boolean', False)
            values('integer', 1, 1, 0, 1, 0, 1, 3)
            values('number', .5)
            values('boolean', True, True, False, False, True)
            values('number', -.3, -.1)
            values('boolean', False)
        values('integer', 1, 700)
        values('number', 0, 0, 1, 1, 0, 0)
        values('boolean', True)
        values('integer', 0)
        values('text', 'Label', 'Arial')
        values('boolean', True)
        values('integer', 5)
        values('number', 1, -2)
        values('integer', 2, 0)
        values('number', .3)
        values('integer', 1)
        values('number', .5, .25)
        values('integer', 1)
        values('boolean', True)
        values('number', 1, 2, 3, 1)
        values('boolean', False)
        values('integer', 1)
        values('boolean', True, False)
        values('integer', *([0]*10))
        values('number', 0, 0, 3, 0, 0, 1, .3)
        values('integer', 0)
        values('boolean', True)
        values('text', 'Arial')
        values('integer', 5)
        values('number', 1, -2)
        values('boolean', True)
        values('number', 0)
        values('integer', 0, 0)
        values('text', 'R', 'shape.step')
        values('number', 1, 2, 3, 10, 20, 30, 1, 2, 3)
        values('boolean', True, False)

    component(0)
    component(1)
    values('integer', 0)
    writer.buffer.extend(b'END')
    return bytes(writer.buffer)


class ComponentTests(unittest.TestCase):
    def read(self, version, **options):
        reader = Reader(component_fixture(version, **options))
        root = Element('')
        state = read_initial_sections(reader, root)
        upgrades = read_base_components(reader, root.one('/Board'), state.component_count)
        self.assertEqual(reader.count('connections'), 0)
        self.assertEqual(reader.take(3), b'END')
        return upgrades

    def test_component_records_stay_aligned_across_supported_text_modes(self):
        for version in (31, 32, 33, 37, 38, 54, 62):
            with self.subTest(version=version):
                upgrades = self.read(version)
                self.assertEqual([u.component['RefDes'] for u in upgrades], ['R1', 'R2'])
                component = upgrades[0].component
                self.assertEqual((component['X'], component['Y']), (12, 34))
                self.assertEqual(component.one('Pattern')['Width'], 3)
                self.assertEqual(component.one('Pattern')['Height'], 6)
                self.assertEqual(component.one('UserFields/UserField').values, ('Order', '0123', 0))
                self.assertEqual(upgrades[0].legacy_field_bindings, (-1, -1, -1))
                self.assertEqual([item.values[0] for item in component.select('HierarchyPath/Item')],
                                 [] if version == 31 else [20, 40])
                self.assertIsNone(component.one('Pattern').child('HierarchyPath'))

    def test_pad_net_and_layer_overrides_are_independent_of_footprint_geometry(self):
        component = self.read(54)[0].component
        pad = component.one('Pattern/Pads/Pad[2]')
        self.assertEqual(pad['NetNumber'], 0)
        self.assertEqual(pad['PadWidth_New'], 1)
        self.assertTrue(pad['Locked'])
        self.assertEqual((pad['DisableTopMask'], pad['DisableBottomPaste']), (2, 2))
        self.assertEqual(pad.one('HideLayer/Item').values, (1,))
        self.assertEqual(pad.one('CustomSpokes/CustomSpoke').values, (0, 1, 3, Decimal('.5')))

    def test_shared_hole_dimension_and_model_values_use_their_named_domains(self):
        upgrade = self.read(54)[0]
        pattern = upgrade.component.one('Pattern')
        self.assertEqual(pattern.one('Holes/Hole').values, (True, False, 1, 2, 3, 1))
        self.assertEqual(pattern.one('Dimensions/Dimension')['PointerText'], 'R')
        self.assertEqual(pattern.one('Model3D/Rotate')['Y'], 20)
        self.assertEqual(pattern.one('Model3D/Offset')['Z'], 3)
        self.assertEqual(pattern.one('Model3D/Zoom')['Y'], 2)
        self.assertTrue(upgrade.drawings[0].text_marker)
        self.assertEqual(pattern.one('Shapes/Shape')['Type'], 7)
        self.assertEqual(pattern.one('Shapes/Shape/TextLine/pt').values, ('Label',))
        self.assertIsNone(pattern.one('Shapes/Shape').child('StoredData'))

    def test_early_standalone_identifier_boundary_has_its_own_version_gate(self):
        for version in (31, 32, 33, 34, 35, 54, 62):
            for identifier in (-1, 0, 19999, 20000):
                with self.subTest(version=version, identifier=identifier):
                    items = self.read(version, kind=15, identifier=identifier)
                    expected = -1 if version < 35 and identifier >= 20000 else identifier
                    self.assertEqual([item.component['HiddenId'] for item in items], [expected, expected])
                    self.assertEqual(items[0].component['RefDes'], 'R1')
                    self.assertEqual(items[0].component.one('Pattern')['OriginX'], 0)

    def test_early_pad_marker_matches_component_name_and_legacy_counter_spelling(self):
        for name, refdes in (('Pad', 'Pad1'), ('pAd', 'PAD 001 '), ('PAD', 'pad')):
            with self.subTest(name=name, refdes=refdes):
                component = self.read(34, kind=14, identifier=20000, name=name, refdes=refdes)[0].component
                self.assertEqual(component['HiddenId'], -1)
                self.assertEqual((component['Name'], component['RefDes']), (name, refdes))
                self.assertEqual(component.one('Pattern').values, ('0603',))

    def test_early_linkage_does_not_generalize_to_other_objects_or_names(self):
        for kind, name, refdes in ((16, 'Pad', 'Pad1'), (5, 'Pad', 'Pad1'),
                (14, 'Pad ', 'Pad1'), (14, 'Contact', 'Pad1'), (14, 'Pad', 'Pad1A'),
                (14, 'Pad', 'Pad1-X2'), (14, 'Pad', 'Pad\u00b2')):
            with self.subTest(kind=kind, name=name, refdes=refdes):
                component = self.read(34, kind=kind, identifier=20000, name=name, refdes=refdes)[0].component
                self.assertEqual(component['HiddenId'], 20000)


if __name__ == '__main__':
    unittest.main()
