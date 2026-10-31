"""Material stacks use copper identities and independent editable materials."""
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib.common.references import Property
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.model.objects import new_document, new_layer
from lib.pcb.model.stackup import default_stackup
from lib.pcb.tests.test_core_assembly import fixture


def attach_stack(document):
    board = document.one('/Board')
    proposal = default_stackup(board.select('Layers/Layer'))
    board['LayerStackName'] = proposal.name
    board.append(proposal.items)
    for item, layer in proposal.copper_layers:
        item['Layer'] = layer
    return proposal


class StackupTests(unittest.TestCase):
    def test_two_layer_default_contains_editable_materials_in_shared_units(self):
        document = new_document()
        proposal = attach_stack(document)
        materials = proposal.items.select('LayerStackItem/Material')
        self.assertEqual(proposal.name, '2 Layers Default Stackup')
        self.assertEqual([material['Name'] for material in materials],
                         ['Solder Resist', 'Copper 1 Oz', 'FR-4', 'Copper 1 Oz', 'Solder Resist'])
        self.assertEqual([material['Thickness'] for material in materials],
                         [Decimal('.03'), Decimal('.104394'), Decimal('4.5'),
                          Decimal('.104394'), Decimal('.03')])
        self.assertEqual([material['Type'] for material in materials], [2, 0, 2, 0, 2])
        self.assertEqual([item['Lay'] for item in proposal.items.children()], [-1, 0, -1, 1, -1])
        materials[1]['Thickness'] = Decimal('.2')
        self.assertEqual(materials[3]['Thickness'], Decimal('.104394'))
        self.assertIsNone(materials[1].child('Type'))
        document.validate()

    def test_multilayer_defaults_have_one_identity_for_each_copper_layer(self):
        for count in (4, 6, 8, 10, 12, 14, 16):
            with self.subTest(count=count):
                document = new_document()
                layers = document.one('/Board/Layers')
                for index in range(count-2):
                    layers.append(new_layer(f'Inner {index+1}'))
                proposal = attach_stack(document)
                self.assertEqual(len(proposal.items.children()), 5*count//2+1)
                self.assertEqual([item['Layer'] for item in proposal.items.children()
                                  if item['Layer'] is not None], layers.children())
                document.validate()

    def test_nonstandard_count_uses_the_nearest_sufficient_standard_template(self):
        for count, template in ((1, 2), (3, 4), (5, 6), (17, 16), (20, 16)):
            with self.subTest(count=count):
                layers = [new_layer(f'Copper {index}') for index in range(count)]
                proposal = default_stackup(layers)
                self.assertEqual(proposal.name, f'{template} Layers Default Stackup')
                self.assertEqual([layer for _, layer in proposal.copper_layers], layers)
                self.assertEqual(proposal.items.children()[0].one('Material')['Name'], 'Solder Resist')
                self.assertEqual(proposal.items.children()[-1].one('Material')['Name'], 'Solder Resist')

    def test_material_classification_and_copies_follow_layer_edits_incrementally(self):
        document = new_document()
        proposal = attach_stack(document)
        item, layer = proposal.copper_layers[0]
        material = item.one('Material')
        probe = document.root.add('Probe', 0)
        document.references.bind(probe, material, Property(probe, 'Type'), role='probe')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            layer['Type'] = 1
            self.assertEqual((material['Type'], probe.values), (1, (1,)))
            item['Layer'] = proposal.copper_layers[1][1]
            self.assertEqual((material['Type'], probe.values), (0, (0,)))
            layer['Type'] = 0
            self.assertEqual(probe.values, (0,))
            item['Layer'] = None
            self.assertEqual((material['Type'], probe.values), (2, (2,)))
        with self.assertRaisesRegex(TypeError, 'calculated'):
            material['Type'] = 0
        document.validate()

    def test_clone_remaps_copper_links_and_keeps_materials_independent(self):
        document = new_document()
        proposal = attach_stack(document)
        duplicate = document.clone()
        copper = duplicate.one('/Board/LayerStackItems/LayerStackItem[2]')
        top = duplicate.one('/Board/Layers/Layer[1]')
        self.assertIs(copper['Layer'], top)
        top['Type'] = 1
        self.assertEqual(copper.one('Material')['Type'], 1)
        self.assertEqual(proposal.items.children()[1].one('Material')['Type'], 0)
        duplicate.validate()

    def test_import_builds_absent_stack_and_consumes_redundant_material_type(self):
        decoded = fixture()
        decoded.upgrades = SimpleNamespace(nets=(), separate_traces=())
        layers = decoded.board.add('Layers')
        for index, name in enumerate(('Top', 'Bottom')):
            layer = layers.add('Layer', name)
            layer.add('Number', index)
            layer.add('Type', 1 if index == 0 else 0)
        result = assemble_rules(decoded)
        board = result.document.one('/Board')
        self.assertEqual(board['LayerStackName'], '2 Layers Default Stackup')
        self.assertEqual(len(board.select('LayerStackItems/LayerStackItem')), 5)
        self.assertEqual(board.one('LayerStackItems/LayerStackItem[2]/Material')['Type'], 1)

    def test_import_preserves_authored_nonempty_stack(self):
        decoded = fixture()
        decoded.upgrades = SimpleNamespace(nets=(), separate_traces=())
        layers = decoded.board.add('Layers')
        for index in range(2):
            layer = layers.add('Layer', f'Copper {index}')
            layer.add('Number', index)
            layer.add('Type', 1 if index == 0 else 0)
        decoded.board.add('LayerStackName', 'My materials')
        items = decoded.board.add('LayerStackItems')
        for index in range(2):
            item = items.add('LayerStackItem', index)
            item.add('Lay', index)
            material = item.add('Material')
            material.add('Name', 'Custom copper')
            material.add('Type', 0)
            material.add('Thickness', Decimal('.234'))
        result = assemble_rules(decoded)
        self.assertEqual(result.document.one('/Board')['LayerStackName'], 'My materials')
        self.assertEqual(len(items.children()), 2)
        material = items.children()[0].one('Material')
        self.assertEqual((material['Type'], material['Thickness']), (1, Decimal('.234')))
        self.assertIsNone(material.child('Type'))


if __name__ == '__main__':
    unittest.main()
