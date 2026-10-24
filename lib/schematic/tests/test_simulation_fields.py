"""Simulator expressions are named facts; positional arrays belong to adapters."""
import unittest

from lib import ConversionReport, Element, new_schematic, parse, parse_source, serialize
from lib.schematic.model.refs import bind_schematic_references
from lib.schematic.model.simulation import SIMULATION_FIELDS


SIMULATOR = '/Schematic/ssimulator'


class SimulationFieldTests(unittest.TestCase):
    def test_named_settings_are_the_only_stored_arguments(self):
        doc = new_schematic()
        for own, public, names in SIMULATION_FIELDS:
            group = doc.one(SIMULATOR+'/'+own)
            self.assertEqual(group.schema.name, public)
            self.assertEqual(tuple(child.kind for child in group.children()), names)
            self.assertEqual(group.arguments, ())
            self.assertTrue(all(isinstance(item, Element) for item in group.items))
        self.assertEqual(doc.one(SIMULATOR+'/signals').arguments, ())

    def test_named_expression_edits_survive_every_format_pair(self):
        doc = new_schematic()
        simulator = doc.one(SIMULATOR)
        simulator['tp'] = 9
        ac = simulator.one('sim_ac')
        ac['Variation'] = 'dec'
        ac['NumberOfPoints'] = '200'
        ac['StartFrequency'] = '1k'
        ac['StopFrequency'] = '{limit * 2}'
        simulator.one('sim_tran')['Step'] = '2.5u'
        for first in ('dch', 'asc', 'dchxml'):
            intermediate = parse(serialize(doc, format=first, report=ConversionReport()), format=first)
            for second in ('dch', 'asc', 'dchxml'):
                with self.subTest(first=first, second=second):
                    restored = parse(serialize(intermediate, format=second, report=ConversionReport()), format=second)
                    settings = restored.one(SIMULATOR+'/sim_ac')
                    self.assertEqual(settings['StartFrequency'], '1k')
                    self.assertEqual(settings['StopFrequency'], '{limit * 2}')
                    self.assertEqual(restored.one(SIMULATOR+'/sim_tran')['Step'], '2.5u')
                    self.assertEqual(settings.children('pt'), [])
        self.assertIs(doc.one('//sim_ac[StartFrequency="1k"]'), ac)

    def test_source_inspection_keeps_array_syntax_separate(self):
        data = serialize(new_schematic(), format='asc')
        source = parse_source(data, format='asc')
        self.assertEqual(len(source.select(SIMULATOR+'/sim_ac/pt')), 4)
        current = source.as_schematic()
        self.assertEqual(current.one(SIMULATOR+'/sim_ac')['StartFrequency'], '#')
        self.assertEqual(len(source.select(SIMULATOR+'/sim_ac/pt')), 4)

    def test_prefix_and_additional_arguments_remain_typed_and_ordered(self):
        doc = new_schematic()
        group = doc.one(SIMULATOR+'/sim_ac')
        del group['StopFrequency']
        restored = parse(serialize(doc, format='dch'), format='dch')
        partial = restored.one(SIMULATOR+'/sim_ac')
        self.assertNotIn('StopFrequency', partial)
        self.assertEqual(partial['StartFrequency'], '#')
        group['StopFrequency'] = '1G'
        item = group.add('Item', 'additional-expression')
        bind_schematic_references(doc)
        self.assertEqual(item['Value'], 'additional-expression')
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                doc.one(SIMULATOR)['tp'] = 9
                restored = parse(serialize(doc, format=format), format=format)
                self.assertEqual(restored.one(SIMULATOR+'/sim_ac/Item')['Value'], 'additional-expression')
        clone = doc.clone()
        clone.one(SIMULATOR+'/sim_ac/Item')['Value'] = 'changed'
        self.assertEqual(item['Value'], 'additional-expression')

    def test_wrong_setting_types_fail_before_mutation(self):
        simulator = new_schematic().one(SIMULATOR)
        settings = simulator.one('sim_tran')
        before = settings['Step']
        with self.assertRaises(TypeError):
            settings['Step'] = 0.001
        self.assertEqual(settings['Step'], before)
        with self.assertRaises(TypeError):
            simulator.one('OptionsDC')['Iteration'] = True
        self.assertEqual(simulator.one('OptionsDC')['Iteration'], 100)

    def test_older_xml_item_spelling_maps_to_the_current_named_argument(self):
        doc = new_schematic()
        simulator = doc.one(SIMULATOR)
        simulator['tp'] = 10
        simulator.one('sim_digital')['GroupBuses'] = '+'
        data = serialize(doc, format='dchxml', version=51, report=ConversionReport())
        syntax = parse_source(data, format='dchxml')
        self.assertEqual(syntax.one('/Source/Schematic/Simulator/Digital/Item').values, ('+',))
        loaded = parse(data, format='dchxml')
        settings = loaded.one(SIMULATOR+'/sim_digital')
        self.assertEqual(settings['GroupBuses'], '+')
        self.assertEqual(settings.children('Item'), [])
