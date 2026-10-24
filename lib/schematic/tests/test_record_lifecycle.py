"""Schematic copy/removal retains data ownership and electrical constraints."""
import unittest

from examples.schematic.create import build
from lib import ConversionReport, Guard, Index, Property, ReferenceError, new_wire, parse, serialize
from lib.schematic.tests import test_membership
from lib.schematic.model.new import fields
from lib.schematic.model.refs import bind_schematic_references


class RecordLifecycleTests(unittest.TestCase):
    def design(self):
        return parse(serialize(build(), format='dch', version=52), format='dch')

    def test_copy_component_maps_owned_links_and_refreshes_new_labels(self):
        doc = self.design()
        part = doc.one('/Schematic/Components/Part')
        copied = doc.copy(part, fields={'RefDes': 'J2', 'Value': 'Copied input'})
        pin = copied.one('Pins/Pin')
        self.assertIsNone(pin['Net'])  # Incoming memberships belong to the original net.
        self.assertIsNotNone(part.one('Pins/Pin')['Net'])
        label = next(shape for shape in copied.select('Shapes/Shape') if shape['FontType'] == 2)
        self.assertEqual(label.one('TextLine/pt')['Text'], 'J2')
        self.assertIs(doc.references.outgoing(copied, role='component-page')[0].target,
                      doc.one('/Schematic/Pages/Page'))
        for kind in ('dch', 'asc', 'dchxml'):
            with self.subTest(kind=kind):
                restored = parse(serialize(doc, format=kind, report=ConversionReport()),
                                 format=kind, report=ConversionReport())
                self.assertEqual(restored.one('/Schematic/Components/Part[RefDes="J2"]')['Value'], 'Copied input')
                restored.validate()
        doc.remove(copied)
        self.assertEqual(doc.select('/Schematic/Components/Part'), [part])
        doc.validate()

    def test_copy_net_cannot_duplicate_a_pin_membership(self):
        doc = self.design()
        net = doc.one('/Schematic/Nets/Net')
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'already has a net membership'):
            doc.copy(net, fields={'Name': 'Other'})
        self.assertEqual(tuple(doc.references), before)
        self.assertEqual(net.parent.children('Net'), [net])
        doc.validate()

    def test_removal_updates_membership_reverse_views_and_copies_atomically(self):
        doc = self.design()
        pin = doc.one('/Schematic/Components/Part/Pins/Pin')
        member = doc.one('/Schematic/Nets/Net/Parts/pt')
        copied = doc.root.add('NetIndex', 0)
        doc.references.bind(copied, pin, Property(copied, 'NetNumber'))
        doc.remove(member)
        self.assertIsNone(pin['Net'])
        self.assertEqual(copied.values, (-1,))
        self.assertIsNone(member.parent)
        doc.validate()

    def test_removal_rejects_external_membership_before_discarding_owned_links(self):
        doc = self.design()
        part = doc.one('/Schematic/Components/Part')
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'referenced content'):
            doc.remove(part)
        self.assertEqual(tuple(doc.references), before)
        self.assertIsNotNone(part.parent)
        doc.validate()

    def test_removal_cannot_disconnect_an_external_wire(self):
        doc, pins, nets = test_membership.design()
        line = nets[0].one('Lines').append(new_wire())
        for name, value in dict(Number=0, NetNumber=0, ConnectMode1=0, Connect1=0, ConnectL1=0).items():
            line.set_field(name, value)
        bind_schematic_references(doc)
        member = doc.references.incoming(pins[0], role='net-member')[0].source
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'attached wire'):
            doc.remove(member)
        self.assertEqual(tuple(doc.references), before)
        self.assertIs(pins[0]['Net'], nets[0])
        doc.validate()

    def test_dependent_guard_failure_keeps_owned_links_and_record(self):
        doc = self.design()
        pin = doc.one('/Schematic/Components/Part/Pins/Pin')
        member = doc.one('/Schematic/Nets/Net/Parts/pt')
        copied = doc.root.add('NetIndex', 0)
        doc.references.bind(copied, pin, Property(copied, 'NetNumber'))
        selector = copied.add('Target', 0)
        doc.references.bind(copied, pin['Net'], Index(selector), guards=(Guard(copied, (0,)),))
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            doc.remove(member)
        self.assertEqual(tuple(doc.references), before)
        self.assertIsNotNone(member.parent)
        self.assertEqual(copied.values, (0,))
        doc.validate()
