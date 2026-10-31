"""Supplier omissions keep authored details separate from environment matches."""
import unittest

from lib.common.model import Document
from lib.common.conversion import ConversionReport
from lib.common.supplier_conversion import report_supplier_omissions


class SupplierConversionTests(unittest.TestCase):
    def test_losses_aggregate_paths_and_match_is_information(self):
        document = Document()
        owners = []
        for index in range(2):
            owner = document.root.add('Part')
            supplier = owner.add('Suppliers')
            supplier.add('SourceLocator', 'catalog:item'+str(index))
            supplier.add('MainSupplier', True)
            supplier.add('Prices').add('Quote', 10, 1.25)
            owners.append(owner)
        report = ConversionReport()
        report_supplier_omissions(owners, destination='dipxml', report=report, omit_preference=True)
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'supplier-source-locator', 'supplier-quotes'})
        self.assertTrue(all(len(notice.paths) == 2 for notice in report.warnings))
        self.assertEqual([notice.rule for notice in report.infos], ['supplier-preference'])
        self.assertEqual(len(report.infos[0].paths), 2)
        self.assertEqual([owner.one('Suppliers/Prices/Quote').values for owner in owners], [(10, 1.25)]*2)

    def test_destination_choices_only_report_actual_omissions(self):
        document = Document()
        owner = document.root.add('Part')
        supplier = owner.add('Suppliers')
        supplier.add('SourceLocator', 'catalog:item')
        supplier.add('MainSupplier', True)
        supplier.add('Prices').add('Quote', 10, 1.25)
        report = ConversionReport()
        report_supplier_omissions((owner,), destination='dip', report=report,
                                  omit_source_locator=False, omit_preference=True)
        self.assertEqual([notice.rule for notice in report.warnings], ['supplier-quotes'])
        self.assertEqual([notice.rule for notice in report.infos], ['supplier-preference'])

    def test_absent_or_false_matches_and_empty_details_are_quiet(self):
        document = Document()
        owner = document.root.add('Part')
        supplier = owner.add('Suppliers')
        supplier.add('SourceLocator', '')
        supplier.add('Prices')
        for flag in (None, False):
            if flag is not None:
                supplier.add('MainSupplier', flag)
            report = ConversionReport()
            report_supplier_omissions((owner,), destination='dipxml', report=report, omit_preference=True)
            self.assertEqual(report.notices, [])


if __name__ == '__main__':
    unittest.main()
