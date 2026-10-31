"""XML guides retain supplied geometry while pad/component positions change."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.pcb.formats.dipxml.output_keys import OutputKeys
from lib.pcb.formats.dipxml.ratline_output import project_ratlines
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read
from lib.pcb.tests.test_ratline_inputs import xml_source
from lib.pcb.tests.test_xml_routing_output import context, with_component_library


def design():
    return read(with_component_library(xml_source()), report=ConversionReport())


def reopen(document, *, units='mm', report=None):
    output, library = context(document, units=units, report=report)
    board = document.one('/Board')
    output.one('/Source/Board').append(project_ratlines(
        board, keys=OutputKeys(board, library), units=XmlUnits(units), report=report))
    return read(dumps(output), report=ConversionReport())


class XmlRatlineOutputTests(unittest.TestCase):
    def test_geometry_hidden_choice_and_endpoints_survive_repeated_unit_conversion(self):
        document = design()
        before, expected = model_text(document, preserve=False), signature(document.one('/Board/Ratlines'))
        for units in ('mm', 'mil', 'inch'):
            current = document
            for _ in range(3):
                current = reopen(current, units=units)
                actual = signature(current.one('/Board/Ratlines'))
                self.assertEqual(actual.keys(), expected.keys())
                for name, value in expected.items():
                    if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                        self.assertLessEqual(abs(actual[name]-value), Decimal('1e-23'), name)
                    else:
                        self.assertEqual(actual[name], value, name)
                current.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_reparented_pad_reordered_component_and_absent_endpoint_are_current(self):
        document = design()
        guide = document.one('/Board/Ratlines/Ratline')
        component = document.one('/Board/Components/Component')
        other = document.copy(component, parent=component.parent, index=0, fields={'RefDes': 'U2'})
        guide['Pad1']['Id'] = 100  # Distinct from the copied footprint's declared keys.
        guide['Pad1'].move_to(other.one('Pattern/Pads'))
        guide['Pad2'] = None
        current = reopen(document)
        result = current.one('/Board/Ratlines/Ratline')
        self.assertIs(result['Pad1'], current.one('/Board/Components/Component[1]/Pattern/Pads/Pad[3]'))
        self.assertIsNone(result['Pad2'])
        self.assertEqual((result['X1'], result['Y1'], result['X2'], result['Y2']),
                         (guide['X1'], guide['Y1'], guide['X2'], guide['Y2']))
        current.references.validate()

    def test_inactive_guides_omit_with_info_without_modifying_the_source(self):
        document = design()
        document.one('/Board/Ratlines/Ratline')['Enabled'] = False
        before, report = model_text(document, preserve=False), ConversionReport()
        current = reopen(document, report=report)
        self.assertFalse(current.one('/Board/Ratlines').children())
        self.assertIn('inactive-ratline', {notice.rule for notice in report.infos})
        self.assertEqual(model_text(document, preserve=False), before)

    def test_unknown_guide_properties_are_an_atomic_error(self):
        document = design()
        document.one('/Board/Ratlines/Ratline').add('UnmappedGuideChoice', 3)
        before = model_text(document, preserve=False)
        with self.assertRaises(PcbError):
            reopen(document)
        self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
