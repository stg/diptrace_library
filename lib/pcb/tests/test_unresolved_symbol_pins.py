"""Unavailable cached pin assignments never become unrelated output pad links."""
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.references import Guard, Index
from lib.common.structural_edits import assembly
from lib.pcb.formats import io
from lib.pcb.model.library_relations import PIN_PAD_ROLE
from lib.pcb.tests.test_dipxml_library import read, source


PART = '/Board/CacheLib/Slots/Slot/Definition/Part'


def unavailable_pin(number):
    document = read(source(), report=ConversionReport())
    part = document.one(PART)
    pin = part.one('Pins/Pin')
    graph = document.references
    graph.discard(graph.outgoing(part, role=PIN_PAD_ROLE)[0])
    with assembly(document):
        pin.one('Number').set_values(number)
    graph.note(part, PIN_PAD_ROLE+': target pad cannot be resolved',
               Index(pin.one('Number'), offset=1),
               collections=(part.parent.one('Pattern/Pads'),),
               guards=(Guard(part.one('PartType'), (0,)),))
    document.references.validate()
    return document, pin


class UnresolvedSymbolPinTests(unittest.TestCase):
    def test_output_never_binds_a_missing_key_to_a_current_positional_pad(self):
        for number in (1, 99):
            for format in ('dip', 'asc', 'dipxml'):
                with self.subTest(number=number, format=format):
                    document, pin = unavailable_pin(number)
                    before = dumps(document, preserve=False)
                    issues = tuple(document.references.issues)
                    report = ConversionReport()
                    data = io.serialize(document, format=format, report=report)
                    rebuilt = io.parse(data, report=ConversionReport())
                    current = rebuilt.one(PART+'/Pins/Pin')
                    expected = -1 if number == 1 or format == 'dipxml' else number
                    self.assertEqual(current['Number'], expected)
                    self.assertFalse(rebuilt.references.outgoing(current.parent.parent, role=PIN_PAD_ROLE))
                    self.assertEqual(current['StringNumber'], pin['StringNumber'])
                    notices = [n for n in report.notices if n.rule == 'unresolved-cached-pin']
                    self.assertEqual(len(notices), 1)
                    self.assertEqual(notices[0].severity, 'warning')
                    self.assertEqual(dumps(document, preserve=False), before)
                    self.assertTrue(document.references.unresolved_slot(pin.one('Number')))
                    self.assertEqual(tuple(document.references.issues), issues)
                    rebuilt.references.validate()


if __name__ == '__main__':
    unittest.main()
