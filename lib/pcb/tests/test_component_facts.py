"""Editable supplier and timing facts use ordinary shared/model fields."""
from decimal import Decimal
import unittest

from lib.common.supplier_records import SUPPLIERS, PRICES, QUOTE
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.assembly.graphic_inputs import GraphicInputs
from lib.pcb.formats.assembly.routing import assemble_routing
from lib.pcb.tests.test_core_assembly import fixture
from lib.pcb.tests.test_dipxml_electrical import prepared, NETS
from lib.pcb.tests.test_dipxml_components import SOURCE
from lib.schematic.model import definitions as schematic
from lib.schematic.model.collections import COLLECTIONS as SCHEMATIC_COLLECTIONS


def design(source):
    source.upgrades = GraphicInputs()
    return assemble_graphics(source).document


class ComponentFactTests(unittest.TestCase):
    def test_supplier_prices_share_the_schematic_schema_and_support_named_editing(self):
        source = fixture()
        supplier = source.board.one('Components/Component').add('Suppliers')
        supplier.add('Currency', 'EUR')
        prices = supplier.add('Prices')
        prices.add('Quote', 10, Decimal('2.50'))
        prices.add('Quote', 100, Decimal('1.75'))
        document = design(source)
        self.assertIs(supplier.schema, SUPPLIERS)
        self.assertIs(prices.schema, PRICES)
        self.assertIs(SCHEMATIC_COLLECTIONS['Prices'], PRICES)
        self.assertIs(schematic.QUOTE, QUOTE)
        quote = prices.one('Quote[2]')
        self.assertIs(quote.schema, QUOTE)
        self.assertEqual((quote['Quantity'], quote['Price']), (100, Decimal('1.75')))
        quote['Price'] = Decimal('1.5')
        extra = prices.add('Quote', 1000, Decimal('1.25'))
        self.assertIs(extra.schema, QUOTE)
        extra['Quantity'] = 2000
        self.assertEqual(extra.values, (2000, Decimal('1.25')))
        with self.assertRaises((TypeError, ValueError)):
            extra['Quantity'] = 'many'
        self.assertEqual(extra['Quantity'], 2000)
        clone = document.clone()
        cloned = clone.one('/Board/Components/Component/Suppliers/Prices/Quote[2]')
        self.assertEqual(cloned['Price'], Decimal('1.5'))
        self.assertIsNot(cloned, quote)
        document.references.validate()

    def test_optional_prices_can_remain_absent_and_be_added_and_removed_normally(self):
        source = fixture()
        supplier = source.board.one('Components/Component').add('Suppliers')
        supplier.add('PartNumber', 'Device')
        document = design(source)
        self.assertIsNone(supplier.child('Prices'))
        prices = supplier.add('Prices')
        self.assertIs(prices.schema, PRICES)
        quote = prices.add('Quote', 1, 2)
        self.assertEqual(quote['Price'], 2)
        document.remove(prices)
        self.assertIsNone(supplier.child('Prices'))

    def test_xml_and_binary_stage_pad_delays_are_scalars_independent_of_display_length_units(self):
        text = SOURCE.replace('</Components></Board>', '</Components>'+NETS+'</Board>')
        text = text.replace('Pad Id="17" NetId="7"', 'Pad Id="17" NetId="7" SignalDelay="0.125"')
        result = assemble_routing(prepared(text))
        pad = result.core.pads[8, 1]
        self.assertEqual(pad['SignalDelay'], Decimal('.125'))
        self.assertEqual(result.core.pads[8, 2]['SignalDelay'], 0)
        pad['SignalDelay'] = Decimal('.25')
        self.assertEqual(pad['SignalDelay'], Decimal('.25'))
        source = fixture()
        source.board.one('Components/Component/Pattern/Pads').children('Pad')[1].add('SignalDelay', Decimal('.125'))
        binary = assemble_core(source)
        self.assertEqual(binary.pads[41, 5]['SignalDelay'], Decimal('.125'))
        self.assertEqual(binary.pads[41, 12]['SignalDelay'], 0)
        binary.document.references.validate()


if __name__ == '__main__':
    unittest.main()
