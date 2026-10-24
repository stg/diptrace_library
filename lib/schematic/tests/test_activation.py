"""Attaching current model data activates its links without a binding pass."""
import unittest
from dataclasses import replace
from unittest.mock import patch

from lib import ConversionReport, Element, Guard, Index, Property, ReferenceError, new_schematic, parse, serialize
from lib.schematic.model.definitions import NET
from lib.schematic.model.new import fields
from lib.schematic.model.objects import new_pin, new_symbol, new_schematic_shape, new_symbol_shape, new_net
from lib.common.schema import Field
from lib.schematic.model.pads import empty_pad


class ActivationTests(unittest.TestCase):
    def test_first_pad_domain_activates_existing_symbol_pin_assignments(self):
        doc = new_schematic()
        part = doc.one('/Schematic/Components').append(new_symbol('Connector', 'J1'))
        pin = part.one('Pins').append(new_pin())
        pin['Number'] = 1
        pad = empty_pad(1)
        pad.annotations.clear()
        pad['Number_New'] = 1
        part.one('Pattern/Pads').insert(pad, 1)
        reference = doc.references.outgoing(part, role='symbol-pin-pad')[0]
        self.assertIs(reference.target, pad)
        doc.validate()

    def test_first_pad_domain_captures_missing_assignments_without_rebinding_them(self):
        doc = new_schematic()
        part = doc.one('/Schematic/Components').append(new_symbol('Connector', 'J1'))
        pin = part.one('Pins').append(new_pin())
        pin['Number'] = 99
        pads = part.one('Pattern/Pads')
        pad = empty_pad(1)
        pad.annotations.clear()
        pad['Number_New'] = 1
        pads.insert(pad, 1)
        issue = next(issue for issue in doc.references.issues if any(index.field is pin.one('Number') for index in issue.indices))
        self.assertEqual(issue.collections, (pads,))
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            pads.insert(empty_pad(2), 2)
        self.assertEqual(pin['Number'], 99)
        doc.validate()

    def design(self):
        doc = new_schematic()
        part = doc.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
        nets = doc.one('/Schematic/Nets')
        a, b = nets.append(new_net('A')), nets.append(new_net('B'))
        return doc, part, a, b

    def test_new_component_and_cloned_content_get_current_identity_links(self):
        doc, part, _, _ = self.design()
        second = part.clone()
        second['RefDes'] = 'U2'
        doc.one('/Schematic/Components').append(second)
        self.assertEqual((part['Number'], second['Number']), (0, 1))
        self.assertIs(doc.references.outgoing(second, role='component-page')[0].target,
                      doc.one('/Schematic/Pages/Page'))
        doc.validate()
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                current = parse(serialize(doc, format=format, report=ConversionReport()),
                                format=format, report=ConversionReport())
                self.assertEqual([node['RefDes'] for node in current.select('/Schematic/Components/Part')], ['U1', 'U2'])

    def test_fresh_pin_is_canonical_before_property_users_are_registered(self):
        doc, part, _, net = self.design()
        pin = part.one('Pins').append(new_pin())
        copied = doc.root.add('CopiedNetNumber', -1)
        doc.references.bind(copied, pin, Property(copied, 'NetNumber'))
        pin['Net'] = net
        self.assertEqual(copied.values, (1,))
        pin['Net'] = None
        self.assertEqual(copied.values, (-1,))
        doc.validate()

    def test_new_pin_with_a_net_number_creates_one_ordered_identity_membership(self):
        doc, part, _, net = self.design()
        pin = new_pin()
        pin.set_field('NetNumber', 1)
        part.one('Pins').append(pin)
        self.assertIs(pin['Net'], net)
        self.assertIs(net.one('Parts/pt')['Pin'], pin)
        self.assertEqual(pin.one('NetNumber').items, ())
        self.assertFalse(doc.references.outgoing(pin, role='pin-net'))
        doc.validate()

    def test_insertion_before_existing_components_combines_membership_and_index_changes(self):
        doc, old, _, net = self.design()
        copied = doc.root.add('OriginalIndex', 0)
        doc.references.bind(copied, old, Property(copied, 'Number'))
        new = new_symbol('Inserted', 'U0')
        pin = new.one('Pins').append(new_pin())
        pin.set_field('NetNumber', 1)
        doc.one('/Schematic/Components').insert(new, 0)
        self.assertEqual((new['Number'], old['Number'], copied.values), (0, 1, (1,)))
        self.assertIs(pin['Net'], net)
        self.assertIs(net.one('Parts/pt')['Pin'], pin)
        doc.validate()

    def test_new_net_membership_updates_an_existing_pin_and_calculated_user(self):
        doc, part, _, _ = self.design()
        pin = part.one('Pins').append(new_pin())
        copied = doc.root.add('CopiedNetNumber', -1)
        doc.references.bind(copied, pin, Property(copied, 'NetNumber'))
        net = new_net('C')
        member = net.one('Parts').add('pt', 0, 0)
        doc.one('/Schematic/Nets').append(net)
        self.assertIs(member['Pin'], pin)
        self.assertIs(pin['Net'], net)
        self.assertEqual(copied.values, (2,))
        doc.validate()

    def test_failed_membership_attachment_restores_the_document_and_detached_proposal(self):
        doc, part, a, _ = self.design()
        pin = part.one('Pins').append(new_pin())
        copied = doc.root.add('CopiedNetNumber', -1)
        doc.references.bind(copied, pin, Property(copied, 'NetNumber'))
        target = copied.add('Target', 0)
        doc.references.bind(copied, a, Index(target), guards=(Guard(copied, (-1,)),))
        net = new_net('C')
        member = net.one('Parts').add('pt', 0, 0)
        before_items, before_schema = member.items, member.schema
        before_graph = tuple(doc.references)
        for node in doc.root.walk(include_self=True):
            node._dirty = False
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            doc.one('/Schematic/Nets').append(net)
        self.assertIsNone(net.parent)
        self.assertEqual((member.items, member.schema), (before_items, before_schema))
        self.assertEqual(tuple(doc.references), before_graph)
        self.assertIsNone(pin['Net'])
        self.assertEqual(copied.values, (-1,))
        self.assertFalse(doc.root.changed)
        doc.validate()

    def test_unresolved_new_pin_keeps_its_identity_and_only_guards_its_target_scope(self):
        doc, part, _, _ = self.design()
        pin = new_pin()
        pin.set_field('NetNumber', 99)
        part.one('Pins').append(pin)
        issue = next(issue for issue in doc.references.issues if issue.source is pin)
        self.assertEqual(issue.collections, (doc.one('/Schematic/Nets'),))
        self.assertEqual(pin['NetNumber'], 99)
        with self.assertRaisesRegex(ReferenceError, 'unresolved net'):
            pin['Net'] = None
        doc.one('/Schematic/Shapes').append(new_schematic_shape())
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            doc.one('/Schematic/Nets').append(new_net('Blocked'))
        doc.validate()

    def test_activation_does_not_walk_the_existing_document_or_rebind_its_graph(self):
        doc, part, _, net = self.design()
        pin = new_pin()
        pin.set_field('NetNumber', 1)
        with patch.object(doc.root, 'walk', side_effect=AssertionError('document scan')), \
             patch.object(type(doc.references), '__iter__', side_effect=AssertionError('graph scan')), \
             patch('lib.schematic.model.refs.bind_schematic_references', side_effect=AssertionError('full binding')):
            part.one('Pins').append(pin)
        self.assertIs(pin['Net'], net)
        doc.validate()

    def test_new_bound_label_uses_current_fields_and_literal_text_stays_authored(self):
        doc, part, _, _ = self.design()
        bound = new_symbol_shape()
        bound['Type'], bound['FontType'] = 10, 2
        bound.one('TextLine').add('pt', 'old placeholder')
        part.one('Shapes').append(bound)
        self.assertEqual(bound.one('TextLine/pt')['Text'], 'U1')
        literal = new_symbol_shape()
        literal['Type'], literal['FontType'] = 10, 0
        literal.one('TextLine').add('pt', 'U1')
        part.one('Shapes').append(literal)
        copied = part.clone()
        copied['RefDes'] = 'U2'
        doc.one('/Schematic/Components').append(copied)
        labels = copied.select('Shapes/Shape')
        self.assertEqual([shape.one('TextLine/pt')['Text'] for shape in labels], ['U2', 'U1'])
        self.assertEqual(bound.one('TextLine/pt')['Text'], 'U1')
        doc.validate()

    def test_new_drawing_and_simulation_signal_link_to_current_targets(self):
        doc, _, _, net = self.design()
        drawing = new_schematic_shape()
        drawing['Type'], drawing['RelatedNet'] = 10, 1
        doc.one('/Schematic/Shapes').append(drawing)
        self.assertIs(doc.references.outgoing(drawing, role='drawing-net-name')[0].target, net)
        signal = Element('signal')
        fields(signal, signal_tp=1, signal_num=1, signal_plotted=False, signal_visible=True,
               signal_display_name='', signal_color=0)
        doc.one('/Schematic/ssimulator/signals').append(signal)
        self.assertIs(doc.references.outgoing(signal, role='simulation-voltage')[0].target, net)
        net.move_to(net.parent, 0)
        self.assertEqual((drawing['RelatedNet'], signal['signal_num']), (0, 0))
        doc.validate()

    def test_accepted_classification_names_normalize_before_dependent_counts_are_planned(self):
        doc, part, a, _ = self.design()
        part.bind_schema(replace(part.schema, fields={**part.schema.fields,
            'TypeCount': Field('TypeCount', 'integer',
                getter=lambda node: len(node.one('Component_CategoryTypes').children('CategoryType')),
                collection_dependencies=lambda node: ((node.one('Component_CategoryTypes'), 'CategoryType'),))}))
        copied = doc.root.add('TypeCount', 0)
        doc.references.bind(copied, part, Property(copied, 'TypeCount'))
        target = copied.add('Target', 0)
        guard = doc.references.bind(copied, a, Index(target), guards=(Guard(copied, (0,)),))
        row = Element('Type', 'Kind', 'Subtype', 3, 4)
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            part.one('Component_CategoryTypes').append(row)
        self.assertEqual((row.kind, row.values, row.schema), ('Type', ('Kind', 'Subtype', 3, 4), None))
        self.assertIsNone(row.parent)
        doc.references.discard(guard)
        part.one('Component_CategoryTypes').append(row)
        self.assertEqual((row.kind, row['Type'], copied.values), ('CategoryType', 'Kind', (1,)))
        doc.validate()

    def test_new_bus_attachment_activates_its_connectors_reverse_owner(self):
        doc = new_schematic()
        bus = Element('Bus', 'B')
        fields(bus, Number=0, ActiveLine=-1, ActivePoint=-1, Enabled=True, Locked=False, Region=0)
        bus.add('Numbers')
        bus.add('Nets')
        bus.add('Lines')
        doc.one('/Schematic/Buses').append(bus)
        connector = Element('PageConnector', 'C', 0, 0)
        fields(connector, Number=0, Connected=False, BusNumber=-1, Page=0, Enabled=True,
               Selected=False, Region=0, Group=-1, Locked=False)
        doc.one('/Schematic/PageConnectors').append(connector)
        copied = doc.root.add('ConnectorBus', -1)
        doc.references.bind(copied, connector, Property(copied, 'BusNumber'))
        line = Element('Line')
        fields(line, Number=0, BusNumber=0, ConnectMode1=4, Connect1=0, ConnectL1=-1,
               ConnectB1=-1, ConnectMode2=0, Connect2=-1, ConnectL2=-1, ConnectB2=-1,
               Page=0, Region=0, Selected=False, Group=-1)
        points = line.add('Points')
        points.add('pt', 0, 0, 0)
        points.add('pt', 3, 0, 0)
        bus.one('Lines').append(line)
        self.assertIs(doc.references.outgoing(line, role='bus-wire-connector-1')[0].target, connector)
        self.assertIs(doc.references.outgoing(connector, role='bus-connector-owner')[0].target, bus)
        self.assertEqual((connector['BusNumber'], copied.values), (0, (0,)))
        doc.validate()
