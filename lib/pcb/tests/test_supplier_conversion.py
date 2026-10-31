"""PCB cached supplier data converts with explicit, family-consistent reports."""
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_dipxml_library import source


SUPPLIER = '/Board/CacheLib/Slots/Slot/Definition/Part/Suppliers'


class PcbSupplierConversionTests(unittest.TestCase):
    def test_cached_details_convert_with_specific_losses_and_no_source_changes(self):
        document = io.parse(source(), report=ConversionReport())
        supplier = document.one(SUPPLIER)
        expected = dict(PartNumber='ABC', Manufacturer='Example', Pattern='Package', Supplier='Vendor', Currency='EUR')
        for name, value in expected.items():
            supplier[name] = value
        supplier['SourceLocator'], supplier['MainSupplier'] = 'catalog:item', True
        supplier.add('Prices').add('Quote', 10, 1.25)
        before = model_text(document, preserve=False)
        cases = [(format, version) for format in ('dip', 'asc', 'dipxml')
                 for version in FORMATS[format].write_versions]
        for format, version in cases:
            with self.subTest(format=format, version=version):
                report = ConversionReport()
                data = io.serialize(document, format=format, version=version, report=report)
                current = io.parse(data, report=ConversionReport()).one(SUPPLIER)
                self.assertEqual({name: current[name] for name in expected}, expected)
                self.assertEqual(current.get('SourceLocator', ''), 'catalog:item' if format == 'dip' else '')
                self.assertFalse(current.select('Prices/Quote'))
                self.assertIsNone(current.child('MainSupplier'))
                warnings = {notice.rule for notice in report.warnings}
                self.assertIn('supplier-quotes', warnings)
                self.assertEqual('supplier-source-locator' in warnings, format != 'dip')
                self.assertNotIn('supplier-preference', warnings)
                self.assertIn('supplier-preference', {notice.rule for notice in report.infos})
                self.assertFalse(report.errors)
                self.assertEqual(model_text(document, preserve=False), before)

    def test_false_cached_match_no_longer_blocks_xml_or_emits_asc_metadata(self):
        document = io.parse(source(), report=ConversionReport())
        supplier = document.one(SUPPLIER)
        supplier['Supplier'], supplier['MainSupplier'] = 'Vendor', False
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                report = ConversionReport()
                current = io.parse(io.serialize(document, format=format, report=report),
                                   report=ConversionReport()).one(SUPPLIER)
                self.assertEqual(current['Supplier'], 'Vendor')
                self.assertIsNone(current.child('MainSupplier'))
                self.assertFalse(any(notice.rule.startswith('supplier-') for notice in report.notices))
        self.assertIs(supplier['MainSupplier'], False)

    def test_unknown_supplier_data_remains_an_error(self):
        document = io.parse(source(), report=ConversionReport())
        document.one(SUPPLIER).add('Unmapped', 1)
        before = model_text(document, preserve=False)
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format), self.assertRaises(PcbError):
                io.serialize(document, format=format, report=ConversionReport())
            self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
