"""Binary layer/style choices are modernized into single model facts."""
from types import SimpleNamespace
import unittest

from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.tests.test_core_assembly import fixture
from lib.pcb.tests.test_routing_assembly import trace


class RulesAssemblyTests(unittest.TestCase):
    def test_layers_styles_classes_and_stack_members_bind_without_duplicate_indices(self):
        decoded = fixture()
        board = decoded.board
        layers = board.add('Layers')
        for index, name in enumerate(('Top', 'Inner', 'Bottom')):
            layer = layers.add('Layer', name)
            layer.add('Number', 40+index*10)  # This bookkeeping value is not the layer selector.
            layer.add('NetNumber', -1)
            layer.add('Enabled', True)
        vias = board.add('ViaStyles')
        through = vias.add('ViaStyle', 'Through', True, 2, 1, 123, 456)
        bounded = vias.add('ViaStyle', 'Blind', False, 1, 0.5, 0, 1)
        fixed_outer = vias.add('ViaStyle', 'Fixed outer span', False, 1, 0.5, 0, 2)
        classes = board.add('NetClasses')
        classes.add('NetClass', 'Default')
        selected_class = classes.add('NetClass', 'Sensitive')
        component = board.one('Components/Component')
        component.add('ConnectedLayer', 1)
        component.add('ViaStyle', -1)
        net = board.one('Nets/Net')
        net.add('NetClass', 1)
        route = trace(net.add('Traces'), 9, (0, 41, 5, 0), (0, 41, 12, 0))
        for point in route.trace.one('Points').children():
            point.add('Lay', 2)
            point.add('ViaStyle', 1)
        stack_item = board.add('LayerStackItems').add('LayerStackItem', 0)
        stack_item.add('Lay', 1)
        stack_item.add('Material').add('Name', 'Copper')
        decoded.upgrades = SimpleNamespace(nets=(SimpleNamespace(net=net, traces=(route,)),), separate_traces=())
        result = assemble_rules(decoded)
        top, inner, bottom = result.layers.values()
        self.assertIsNone(through['Span'])
        self.assertEqual((through['Lay1'], through['Lay2']), (0, 2))
        self.assertEqual(bounded['Span'], (top, inner))
        self.assertEqual(fixed_outer['Span'], (top, bottom))
        self.assertFalse(fixed_outer['Through'])
        self.assertIs(component['Layer'], inner)
        self.assertIs(net['Class'], selected_class)
        self.assertIs(stack_item['Layer'], inner)
        point = route.trace.one('Points/Point[1]')
        self.assertIs(point['Layer'], bottom)
        self.assertIs(point['Via'], bounded)
        for owner, name in ((point, 'Lay'), (point, 'ViaStyle'), (component, 'ConnectedLayer'),
                            (net, 'NetClass'), (stack_item, 'Lay'), (inner, 'Number')):
            self.assertIsNone(owner.child(name))
        bottom.move_to(layers, 1)
        self.assertEqual((point['Lay'], component['ConnectedLayer'], stack_item['Lay']), (1, 2, 2))
        self.assertEqual(bounded['Lay2'], 2)
        self.assertFalse(result.document.complete)


if __name__ == '__main__':
    unittest.main()
