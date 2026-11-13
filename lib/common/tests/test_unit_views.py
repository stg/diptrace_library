"""Measurement views preserve model identity, optional states and editing policy."""
import gc
import unittest
from weakref import ref

from lib.common.model import Document, Element, Value
from lib.common.measurements import using_units
from lib.common.schema import Field, Record
from lib.common.references import Index, Guard


def fixture():
    schema = Record('Measured', {
        'Id': Field('Id', 'integer', required=True),
        'X': Field('X', 'number', required=True, unit='shared length'),
        'Y': Field('Y', 'number', required=True, unit='shared length'),
        'Width': Field('Width', 'number', unit='shared length', nullable=True),
        'Location': Field('Location', 'tuple', members=(
            Field('Key', 'integer'), Field('X', 'number', unit='shared length'),
            Field('Y', 'number', unit='shared length', nullable=True),
            Field('Angle', 'number', unit='radians'))),
    }, parameters=('Id', 'X', 'Y'))
    document = Document()
    node = document.root.append(Element('Measured', 2**70+3, 76.2, -3).bind_schema(schema))
    return document, node


class UnitViewTests(unittest.TestCase):
    def test_named_and_argument_access_share_current_facts_and_preserve_integer_identity(self):
        document, node = fixture()
        view = document.in_units('inch')
        point = view.one('Measured')
        self.assertIs(point.model, node)
        self.assertIs(point.parent, view.root)
        self.assertIs(point, view.get(node.uid))
        self.assertEqual(point['X'], 1.)
        self.assertEqual(point.scalar('X'), 1.)
        self.assertEqual(point.values[:2], (2**70+3, 1.))
        self.assertIs(type(point.values[0]), int)
        self.assertEqual(point.one('X').values, (1.,))
        point['X'] = 2.
        self.assertEqual(node['X'], 152.4)
        self.assertAlmostEqual(node.in_units('mm')['X'], 50.8)
        point.set_argument(1, 1.)
        self.assertEqual(node['X'], 76.2)
        point.one('Y').set_values(-1.)
        self.assertEqual(node['Y'], -76.2)
        self.assertIs(point.in_units('inch'), point)

    def test_defaults_are_context_local_and_do_not_rewrite_existing_views(self):
        document, node = fixture()
        with using_units('mm'):
            first = document.in_units()
            with using_units('inch'):
                self.assertEqual(document.in_units().one('Measured')['X'], 1.)
                self.assertEqual(first.units, 'mm')
                self.assertAlmostEqual(first.one('Measured')['X'], 25.4)
            self.assertEqual(document.in_units().units, 'mm')
        self.assertEqual(node['X'], 76.2)

    def test_optional_tuple_and_removed_handles_keep_their_meaning(self):
        document, node = fixture()
        point = document.in_units('mm').one('Measured')
        self.assertEqual(point.get('Width', 7), 7)
        point['Width'] = None
        self.assertIsNone(point.get('Width', 7))
        point['Width'] = 1.
        retained = point.one('Width')
        old_uid = retained.uid
        del point['Width']
        self.assertIsNone(retained.parent)
        self.assertEqual(retained.values, (1.,))
        self.assertEqual(retained.in_units('inch').values, (3/76.2,))
        self.assertEqual(retained.clone().values, (1.,))
        point['Width'] = 2.
        self.assertIsNot(retained, point.one('Width'))
        self.assertNotEqual(old_uid, point.one('Width').uid)
        point['Location'] = (2**70+3, 25., None, 1.25)
        self.assertEqual(node['Location'], (2**70+3, 75., None, 1.25))
        location = point.one('Location')
        self.assertEqual(location.values, point['Location'])
        location.set_argument(1, 1.)
        self.assertEqual(node['Location'][1], 3.)
        with self.assertRaises(ValueError):
            point.add('X', 2.)
        self.assertEqual(node['X'], 76.2)

    def test_queries_and_predicates_use_visible_units_and_default_values_stay_literal(self):
        document, node = fixture()
        point = document.in_units('inch').one('Measured')
        self.assertEqual(point.select('/Measured[X=1]'), [point])
        self.assertEqual(point.find_all('X', where=lambda field: field.values[0] > .9), [point.one('X')])
        self.assertEqual(point.get('Missing', 76.2), 76.2)
        self.assertEqual(point.scalar('Missing', 76.2), 76.2)
        with self.assertRaises(KeyError):
            point['Missing']

    def test_clone_copy_and_noop_assignments_do_not_alias_or_accumulate_rounding(self):
        document, node = fixture()
        view = document.in_units('mm')
        cloned = view.clone()
        cloned.one('Measured')['X'] = 2.
        self.assertEqual(node['X'], 76.2)
        copied = view.copy(view.one('Measured'), fields={'Id': 2**70+4, 'X': 2.})
        self.assertEqual(copied.model['X'], 6.)
        for _ in range(64):
            for units in ('mm', 'mil', 'inch'):
                point = node.in_units(units)
                point['X'] = point['X']
                point.set_argument(2, point.values[2])
        self.assertEqual((node['X'], node['Y']), (76.2, -3))
        before = node.values
        with self.assertRaises(ValueError):
            node.in_units('mm').set_values(17, 1, float('nan'))
        self.assertEqual(node.values, before)

    def test_reference_services_wrap_nodes_and_guards_and_accept_cross_unit_inputs(self):
        document, node = fixture()
        node['Width'] = 3.
        source = node
        source.add('Target', 0)
        document.root.add('Anchor')
        view = document.in_units('mm')
        link, target = view.one('Measured'), view.one('Anchor')
        reference = view.references.bind(link, target, Index(link.one('Target')),
            guards=(Guard(link.one('Width'), (1.,)),), role='test')
        self.assertIs(reference.source, link)
        self.assertIs(reference.target, target)
        self.assertEqual(reference.guards[0].values, (1.,))
        self.assertEqual(next(iter(document.references)).guards[0].values, (3.,))
        self.assertIs(view.references.incoming(target)[0], reference)
        self.assertIs(view.references.get(reference.uid), reference)
        self.assertIs(view.references.outgoing(link)[0].indices[0].field, link.one('Target'))
        with self.assertRaises(ValueError):
            link['Width'] = 2.
        self.assertEqual(node['Width'], 3.)
        document.in_units('inch').references.discard(reference)
        self.assertEqual(len(document.references), 0)
        issue = view.references.note(link, 'Missing target', Index(link.one('Target')),
                                     collections=(view.root,), guards=(Guard(link.one('Width'), (1.,)),))
        self.assertIs(view.references.issues[0], issue)
        self.assertEqual(issue.guards[0].values, (1.,))
        document.in_units('inch').references.discard_issue(issue)
        self.assertEqual(list(view.references.issues), [])

    def test_metadata_maps_are_live_and_lazy_wrappers_can_be_released(self):
        document, node = fixture()
        view = document.in_units('mm')
        view.metadata['example'] = True
        point = view.one('Measured')
        point.annotations['example'] = True
        self.assertTrue(document.metadata['example'])
        self.assertTrue(node.annotations['example'])
        handle = point.one('X')
        retained = ref(handle)
        del handle
        gc.collect()
        self.assertIsNone(retained())
        self.assertAlmostEqual(point.one('X').values[0], 25.4)
        self.assertAlmostEqual(point.inspect()['values'][1]['value'], 25.4)
        self.assertEqual(point.inspect()['units'], 'mm')

    def test_values_keep_percentage_tags_and_do_not_reuse_converted_lexemes(self):
        document, node = fixture()
        node.one('X').set_values(Value(76.2, 'number', lexeme='7.62e1'))
        argument = node.in_units('inch').arguments[1]
        self.assertEqual(argument.value, 1.)
        self.assertIsNone(argument.lexeme)
        self.assertEqual(node.arguments[1].lexeme, '7.62e1')
        node.in_units('inch').set_argument(1, argument)
        self.assertEqual(node['X'], 76.2)
        point = node.in_units('inch')
        point.set_field('Percent', Value(15, 'number', '%', '15%'))
        percent = node.one('Percent').arguments[0]
        self.assertEqual((percent.value, percent.unit, percent.lexeme), (15, '%', '15%'))

    def test_conditional_domains_receive_the_owning_record_for_both_access_styles(self):
        def domain(record, value):
            return 'shared length' if record['Physical'] else 'ratio'
        schema = Record('Conditional', {
            'Physical': Field('Physical', 'boolean'),
            'Width': Field('Width', 'number', unit='shared length', unit_selector=domain),
        })
        node = Element('Conditional').bind_schema(schema)
        node['Physical'], node['Width'] = True, 3.
        view = node.in_units('mm')
        self.assertEqual(view['Width'], 1.)
        self.assertEqual(view.one('Width').values, (1.,))
        view.one('Width').set_values(2.)
        self.assertEqual(node['Width'], 6.)
        view['Physical'] = False
        self.assertEqual(view.one('Width').values, (6.,))
        view['Width'] = 2.
        self.assertEqual(node['Width'], 2.)


if __name__ == '__main__':
    unittest.main()
