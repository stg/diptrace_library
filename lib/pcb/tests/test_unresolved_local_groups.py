"""Missing local selectors stay explicit without becoming another identity."""
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.references import ReferenceError
from lib.pcb.formats import io
from lib.pcb.tests.test_dipxml_library import source


PART = '/Board/CacheLib/Slots/Slot/Definition/Part'


def design(*, key=99, grouped=False):
    root = ElementTree.fromstring(source())
    part = next(root.iter('Part'))
    groups = part.find('Groups')
    if groups is None:
        groups = ElementTree.SubElement(part, 'Groups')
    groups.clear()
    if grouped:
        ElementTree.SubElement(groups, 'Item', Id='7', X='0', Y='0')
    pins = part.find('Pins').findall('Pin')
    for pin in pins:
        pin.set('Group', '7' if grouped else '-1')
    pins[0].set('Group', str(key))
    return io.parse(ElementTree.tostring(root), report=ConversionReport())


class UnresolvedLocalGroupTests(unittest.TestCase):
    def test_unavailable_group_cannot_silently_change_owner_and_copy_keeps_scope(self):
        from lib.pcb.tests.test_core_assembly import fixture
        from lib.pcb.formats.assembly.assemble import assemble_core
        decoded = fixture()
        slot = decoded.board.add('CacheLib').add('Slots').add('Slot', 0, '')
        for index in range(2):
            part = slot.add('Definition', index).add('Part', 'Symbol', 'U')
            part.add('PartType', 1)
            part.add('Groups').add('pt', True, 0, 0, 0)
            part.add('Pins').add('Pin', 0, 0, 0).add('Group', 99)
        document = assemble_core(decoded).document
        first, second = document.select('/Board/CacheLib/Slots/Slot/Definition/Part')
        pin = first.one('Pins/Pin')
        copied = document.copy(pin)
        self.assertEqual(copied['UnresolvedGroupId'], 99)
        with self.assertRaisesRegex(ReferenceError, 'unavailable local group'):
            pin.move_to(second.one('Pins'))
        self.assertIs(pin.parent, first.one('Pins'))
        copied['Group'] = None
        pin['Group'] = first.one('Groups/pt')
        document.references.validate()

    def test_import_retains_missing_selector_and_clone_keeps_its_scope(self):
        document = design()
        for current in (document, document.clone()):
            pin = current.one(PART+'/Pins/Pin[1]')
            self.assertEqual(pin['UnresolvedGroupId'], 99)
            self.assertEqual(pin['GroupId'], 99)
            with self.assertRaisesRegex(ReferenceError, 'unresolved target'):
                pin['Group']
            current.references.validate()

    def test_all_formats_keep_an_unavailable_noncolliding_selector(self):
        document = design()
        before = dumps(document, preserve=False)
        for format in ('dip', 'asc', 'dipxml'):
            report = ConversionReport()
            rebuilt = io.parse(io.serialize(document, format=format, report=report), report=report)
            with self.subTest(format=format):
                pin = rebuilt.one(PART+'/Pins/Pin[1]')
                self.assertEqual(pin['UnresolvedGroupId'], 99)
                self.assertIn('unresolved-local-group', {n.rule for n in report.warnings})
                rebuilt.references.validate()
        self.assertEqual(dumps(document, preserve=False), before)

    def test_xml_reserves_missing_keys_and_positional_output_never_binds_them(self):
        document = design(key=0, grouped=True)
        before = dumps(document, preserve=False)
        current = io.parse(document.to_dipxml_bytes(report=ConversionReport()), report=ConversionReport())
        self.assertEqual(current.one(PART+'/Pins/Pin[1]')['UnresolvedGroupId'], 0)
        self.assertEqual(len(current.select(PART+'/Groups/pt')), 1)
        for format in ('dip', 'asc'):
            report = ConversionReport()
            current = io.parse(io.serialize(document, format=format, report=report), report=report)
            pin = current.one(PART+'/Pins/Pin[1]')
            self.assertIsNone(pin['Group'])
            self.assertIsNone(pin.child('UnresolvedGroupId'))
            self.assertIn('unresolved-local-group', {n.rule for n in report.warnings})
        self.assertEqual(dumps(document, preserve=False), before)

    def test_clear_and_repair_use_the_normal_reference_setter(self):
        document = design(grouped=True)
        pin = document.one(PART+'/Pins/Pin[1]')
        group = document.one(PART+'/Groups/pt')
        pin['Group'] = group
        self.assertIs(pin['Group'], group)
        self.assertEqual(pin['GroupId'], 0)
        self.assertIsNone(pin.child('UnresolvedGroupId'))
        pin['Group'] = None
        self.assertIsNone(pin['Group'])
        document.references.validate()
