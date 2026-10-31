"""Calculated marking geometry omits only on an XML export view."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.references import ReferenceError
from lib.common.units import XmlUnits
from lib.pcb.formats.dipxml.pattern_output import project_pattern
from lib.pcb.formats.dipxml.output_keys import OutputKeys
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read, source
from lib.pcb.tests.test_xml_component_output import context


COMPONENT = '/Board/Components/Component'
PATTERN = COMPONENT+'/Pattern'


def design(*, attachment=None):
    text = source()
    if attachment is not None:
        text = text.replace('</Shapes>', '''<Shape Id="99" Type="Line"><Points>
            <Item X="3" Y="4"/><Item X="5" Y="6"/></Points></Shape></Shapes>''', 1)
        text = text.replace('</Pattern>', f'''<Dimensions><Dimension Type="Horizontal"
            Connected1="Shape" SubObject1="{attachment}" Point1="0" Connected2="None"/>
            </Dimensions></Pattern>''', 1)
    return read(text, report=ConversionReport())


class XmlMarkingOutputTests(unittest.TestCase):
    def test_independent_placed_supplier_data_warns_and_remains_in_the_source(self):
        document = design()
        component = document.one(COMPONENT)
        suppliers = component.child('Suppliers')
        if suppliers is None:
            suppliers = component.add('Suppliers')
        for name, value in dict(PartNumber='Order-1', Supplier='Vendor', Currency='USD',
                                SourceLocator='catalog:item', MainSupplier=True).items():
            suppliers[name] = value
        prices = suppliers.child('Prices')
        if prices is None:
            prices = suppliers.add('Prices')
        prices.add('Quote', 10, Decimal('1.25'))
        before, report = model_text(document, preserve=False), ConversionReport()
        output, _ = context(document, report=report)
        rebuilt = read(dumps(output), report=ConversionReport())
        self.assertIsNone(rebuilt.one(COMPONENT).child('Suppliers'))
        self.assertEqual({notice.rule for notice in report.warnings}, {'placed-supplier-data', 'placed-supplier-prices'})
        self.assertEqual(model_text(document, preserve=False), before)

    def test_base_name_projection_distinguishes_empty_default_from_independent_text(self):
        for name, severity, rule in (('', 'info', 'component-base-name-default'),
                                     ('Independent base', 'warning', 'component-base-name')):
            with self.subTest(name=name):
                document = design()
                component = document.one(COMPONENT)
                component['BaseName'] = name
                before, report = model_text(document, preserve=False), ConversionReport()
                output, _ = context(document, report=report)
                actual = read(dumps(output), report=ConversionReport()).one(COMPONENT)
                self.assertEqual(actual['BaseName'], component.one('Pattern')['Name'])
                self.assertEqual([(notice.severity, notice.rule) for notice in report.notices], [(severity, rule)])
                self.assertEqual(model_text(document, preserve=False), before)

    def test_calculated_text_omits_but_component_marking_settings_and_source_remain(self):
        document = design()
        component, pattern = document.one(COMPONENT), document.one(PATTERN)
        generated = document.copy(pattern.one('Shapes/Shape'), parent=pattern.one('Shapes'))
        generated['Type'], generated['TextShow'], generated['MarkingGenerated'] = 7, 2, True
        component['RefDes_SilkAlign'] = 8
        component['RefDes_SilkX'], component['RefDes_SilkY'] = Decimal('3.5'), Decimal('-4.25')
        component['RefDes_SilkAngle'] = Decimal('.25')
        component['CustomMarkingFont'], component['MarkingFontSize'] = True, Decimal('5.5')
        before, report = model_text(document, preserve=False), ConversionReport()
        expected_cache = signature(document.one('/Board/CacheLib'))
        output, _ = context(document, report=report)
        rebuilt = read(dumps(output), report=ConversionReport())
        actual = rebuilt.one(COMPONENT)
        for name in component.schema.fields:
            if component.schema.fields[name].getter is None:
                self.assertEqual(actual.get(name), component.get(name), name)
        self.assertEqual(len(actual.select('Pattern/Shapes/Shape')), 1)
        self.assertEqual(signature(rebuilt.one('/Board/CacheLib')), expected_cache)
        self.assertIn('generated-marking-geometry', {notice.rule for notice in report.infos})
        self.assertEqual(report.warnings, [])
        self.assertEqual(model_text(document, preserve=False), before)

    def test_only_text_with_the_flag_is_omitted(self):
        for kind, generated, count, rule in ((1, True, 1, 'non-text-marking-flag'),
                                             (7, False, 1, None),
                                             (7, True, 0, 'generated-marking-geometry')):
            with self.subTest(kind=kind, generated=generated):
                document = design()
                pattern = document.one(PATTERN)
                shape = pattern.one('Shapes/Shape')
                shape['Type'], shape['MarkingGenerated'] = kind, generated
                report = ConversionReport()
                output = project_pattern(pattern, style='P', units=XmlUnits('mm'), report=report)
                self.assertEqual(len(output.element.select('Shapes/Shape')), count)
                self.assertEqual({notice.rule for notice in report.infos}, set() if rule is None else {rule})

    def test_remaining_shape_attachment_keys_follow_the_projected_collection(self):
        document = design(attachment=99)
        pattern = document.one(PATTERN)
        first = pattern.one('Shapes/Shape[1]')
        first['Type'], first['MarkingGenerated'] = 7, True
        report = ConversionReport()
        output = project_pattern(pattern, style='P', units=XmlUnits('mm'), report=report)
        self.assertEqual(output.element.one('Shapes/Shape')['Id'], 1)
        self.assertEqual(output.element.one('Dimensions/Dimension')['SubObject1'], 1)
        self.assertNotIn(first, output.shape_keys)
        self.assertEqual(output.shape_keys[pattern.one('Shapes/Shape[2]')], 1)
        _, library = context(document, report=ConversionReport())
        keys = OutputKeys(document.one('/Board'), library)
        self.assertEqual(keys.shape(pattern.one('Shapes/Shape[2]')), (0, 1))
        with self.assertRaisesRegex(PcbError, 'shape has no placed physical XML key'):
            keys.shape(first)

    def test_promoting_an_attached_shape_to_text_checks_dimension_constraints(self):
        document = design(attachment=9)
        pattern = document.one(PATTERN)
        first = pattern.one('Shapes/Shape[1]')
        before = model_text(document, preserve=False)
        with self.assertRaisesRegex(ReferenceError, 'dimension attachment requires a compatible target'):
            first['Type'] = 7
        self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
