"""Whole exports share fresh subtree checks; standalone projections remain strict."""
from collections import Counter
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport
from lib.common.model import Element
from lib.common.units import XmlUnits
from lib.pcb.formats import output_validation
from lib.pcb.formats.dipxml.component_output import project_components
from lib.pcb.formats.dipxml.library_output import project_library
from lib.pcb.formats.dipxml.pattern_output import project_pattern
from lib.pcb.formats.dipxml.symbol_output import project_symbol
from lib.pcb.formats.dipxml.write import project_document
from lib.pcb.formats.errors import PcbError
from lib.pcb.formats.export_view import prepare_export
from lib.pcb.tests.test_dip_output import configured_document
from lib.pcb.tests.test_dipxml_library import source


class XmlProjectionValidationTests(unittest.TestCase):
    def design(self):
        document = configured_document(source())
        return prepare_export(document, destination='dipxml', report=ConversionReport())[0]

    def library(self, document):
        board = document.one('/Board')
        return project_library(board, units=XmlUnits('mm'),
                               physical=board.select('Components/Component/Pattern'), report=ConversionReport())

    def test_each_cached_or_placed_geometry_record_is_checked_once_per_whole_export(self):
        document = self.design()
        watched = document.select('/Board/Components/Component/Pattern/Pads/Pad')
        watched += document.select('/Board/CacheLib/Slots/Slot/Definition/Pattern/Pads/Pad')
        watched += document.select('/Board/CacheLib/Slots/Slot/Definition/Part/Pins/Pin')
        self.assertTrue(watched)
        with patch.object(output_validation, 'check', wraps=output_validation.check) as check:
            project_document(document, report=ConversionReport())
        counts = Counter(call.args[0] for call in check.call_args_list)
        self.assertEqual([counts[node] for node in watched], [1]*len(watched))

    def test_whole_export_checks_actual_values_again_after_a_successful_export(self):
        paths = (
            '/Board/Components/Component/Pattern/Pads/Pad[1]/Name',
            '/Board/CacheLib/Slots/Slot/Definition/Pattern/Pads/Pad[1]/Name',
            '/Board/CacheLib/Slots/Slot/Definition/Part/Pins/Pin/Name',
            '/Board/Components/Component/RefDes',
        )
        for path in paths:
            with self.subTest(path=path):
                document = self.design()
                project_document(document, report=ConversionReport())
                document.one(path).set_values(23)
                with self.assertRaises((PcbError, TypeError, ValueError)):
                    project_document(document, report=ConversionReport())

    def test_standalone_components_do_not_trust_a_previous_library_projection(self):
        document = self.design()
        library = self.library(document)
        board = document.one('/Board')
        project_components(board, library=library, units=XmlUnits('mm'), report=ConversionReport())
        board.one('Components/Component/Pattern/Pads/Pad[1]/Name').set_values(23)
        with self.assertRaisesRegex(PcbError, 'Name requires text'):
            project_components(board, library=library, units=XmlUnits('mm'), report=ConversionReport())

    def test_standalone_symbol_and_pattern_checks_remain_fresh_and_complete(self):
        document = self.design()
        part = document.one('/Board/CacheLib/Slots/Slot/Definition/Part')
        pattern = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        options = dict(units=XmlUnits('mm'), report=ConversionReport())
        keys = self.library(document).physical_styles[pattern].pad_keys
        project_symbol(part, pad_keys=keys, **options)
        project_pattern(pattern, style='Pattern', **options)
        part.one('Pins/Pin/Name').set_values(23)
        with self.assertRaisesRegex(PcbError, 'Name requires text'):
            project_symbol(part, pad_keys=keys, **options)
        pattern.one('Pads/Pad[1]')._append_import(Element('Unknown', 1))
        with self.assertRaisesRegex(PcbError, 'no PCB DIPXML projection'):
            project_pattern(pattern, style='Pattern', **options)

    def test_additional_foreign_pattern_is_not_covered_by_the_local_cache_audit(self):
        document, foreign = self.design(), self.design()
        pattern = foreign.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        pattern.one('Pads/Pad[1]/Name').set_values(23)
        with self.assertRaisesRegex(PcbError, 'Name requires text'):
            project_library(document.one('/Board'), units=XmlUnits('mm'), physical=(pattern,),
                            report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
