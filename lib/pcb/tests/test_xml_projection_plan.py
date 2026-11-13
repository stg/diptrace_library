"""PCB XML byte output and editable inspection share one destination mapping."""
import unittest
from unittest.mock import patch

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.xml_plan import XmlPlan
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import DIPXML
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.export_context import ExportContext
from lib.pcb.tests.test_dip_output import configured_document
from lib.pcb.tests.test_xml_via_masks import via_document, configure, PAD


class XmlProjectionPlanTests(unittest.TestCase):
    def test_direct_and_inspection_outputs_match_all_profiles_and_units(self):
        via = via_document()
        configure(via.one(PAD))
        for document in (configured_document(), via):
            before = model_text(document, preserve=False)
            for version in DIPXML.write_versions:
                for units in ('mm', 'mil', 'inch'):
                    with self.subTest(version=version, units=units):
                        context = ExportContext(units=units)
                        emitted, inspected = ConversionReport(), ConversionReport()
                        data = io.serialize(document, format='dipxml', version=version, context=context, report=emitted)
                        view = io.project(document, format='dipxml', version=version, context=context, report=inspected)
                        self.assertEqual(data, dumps(view, canonical_numbers=True).encode('utf-8'))
                        self.assertEqual(emitted.notices, inspected.notices)
                        view.validate()
            self.assertEqual(model_text(document, preserve=False), before)

    def test_byte_export_never_materializes_the_whole_library_or_document(self):
        document = configured_document()
        original = XmlPlan.element
        def materialize(plan):
            if plan.kind in ('Source', 'Library'):
                raise AssertionError('complete editable XML projection was materialized')
            return original(plan)
        for version in DIPXML.write_versions:
            with self.subTest(version=version), patch.object(XmlPlan, 'element', materialize):
                data = document.to_dipxml_bytes(version=version, report=ConversionReport())
            self.assertIn(b'Type="DipTrace-PCB"', data)

    def test_explicit_inspection_stays_independently_editable(self):
        document = configured_document()
        expected = document.one('/Board/Components/Component')['RefDes']
        view = document.as_dipxml(report=ConversionReport())
        view.one('/Source/Board/Components/Component/RefDes').set_values('OTHER')
        self.assertEqual(document.one('/Board/Components/Component')['RefDes'], expected)
        self.assertIn(b'<RefDes>OTHER</RefDes>', dumps(view).encode('utf-8'))
        document.validate()


if __name__ == '__main__':
    unittest.main()
