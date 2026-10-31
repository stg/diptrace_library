"""Component markings and shared supplier/3D properties use named data access."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.footprint_records import MODEL3D, VECTORS, SUPPLIERS
from lib.common.references import Property
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.tests.test_graphics import design
from lib.pcb.model.objects import new_component, new_user_field, new_document


class ComponentDataTests(unittest.TestCase):
    def test_user_fields_have_named_text_link_and_independent_side_placements(self):
        decoded, _, _ = design()
        component = decoded.board.one('Components/Component')
        fields = component.add('UserFields')
        field = fields.add('UserField', 'Order', 'Part-123', 1)
        field.add('SilkX', 4)
        field.add('AssyAngle', Decimal('7.854'))
        document = assemble_graphics(decoded).document
        self.assertEqual((field['Name'], field['Value'], field['Type']), ('Order', 'Part-123', 1))
        self.assertEqual(field['SilkX'], 4)
        self.assertEqual(field['AssyAngle'], Decimal('7.854'))
        field['Value'] = 'Part-456'
        field['SilkShow'] = 1
        self.assertEqual(field.values, ('Order', 'Part-456', 1))
        with self.assertRaises(TypeError):
            field['Type'] = 'link'
        copied = document.clone().one('/Board/Components/Component[1]/UserFields/UserField')
        self.assertEqual(copied['Value'], 'Part-456')
        self.assertEqual(copied['AssyAngle'], Decimal('7.854'))

    def test_user_field_construction_supplies_named_defaults_without_import_state(self):
        document = new_document()
        component = document.one('/Board/Components').append(new_component('Device', 'U1'))
        field = component.one('UserFields').append(new_user_field('URL', 'https://example.test', kind=1))
        self.assertEqual(field['Type'], 1)
        self.assertEqual((field['SilkShow'], field['AssyShow']), (0, 0))
        field['AssyX'] = Decimal('1.25')
        self.assertEqual(field['SilkX'], 0)
        document.validate()

    def test_marking_data_is_named_editable_and_propagates_without_global_scans(self):
        decoded, _, _ = design()
        component = decoded.board.one('Components/Component')
        component.add('RefDes_SilkX', 4)
        component.add('RefDes_SilkAngle', Decimal('7.854'))
        component.add('Name_AssyAlign', 8)
        document = assemble_graphics(decoded).document
        self.assertEqual(component['RefDes_SilkX'], 4)
        self.assertEqual(component['RefDes_SilkAngle'], Decimal('7.854'))
        self.assertEqual(component['Name_AssyAlign'], 8)
        probe = document.root.add('Probe', 0)
        document.references.bind(probe, component, Property(probe, 'RefDes_SilkX'))
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            component['RefDes_SilkX'] = 6
        self.assertEqual(probe.values, (6,))
        with self.assertRaises(TypeError):
            component['RefDes_SilkAngle'] = 'quarter turn'
        self.assertEqual(component['RefDes_SilkAngle'], Decimal('7.854'))
        copy = document.clone()
        self.assertEqual(copy.one('/Board/Components/Component[1]')['RefDes_SilkX'], 6)

    def test_decoded_model_vectors_and_supplier_settings_have_shared_schemas(self):
        decoded, _, _ = design()
        component = decoded.board.one('Components/Component')
        model = component.one('Pattern/Model3D')
        suppliers = component.add('Suppliers')
        suppliers.add('Supplier', 'Vendor')
        suppliers.add('Currency', 'EUR')
        # The decoded records arrive without constructor-provided schemas.
        for node in model.walk(include_self=True):
            node._schema = None
        document = assemble_graphics(decoded).document
        self.assertIs(model.schema, MODEL3D)
        self.assertIs(model.one('Rotate').schema, VECTORS['Rotate'])
        self.assertIs(suppliers.schema, SUPPLIERS)
        model.one('Rotate')['Z'] = Decimal('23.456')
        model.one('Offset')['Y'] = Decimal('-1.25')
        suppliers['Supplier'] = 'Other vendor'
        self.assertEqual(model.one('Rotate')['Z'], Decimal('23.456'))
        self.assertEqual(suppliers['Currency'], 'EUR')
        self.assertEqual(suppliers['Supplier'], 'Other vendor')
        copied = document.clone().one('/Board/Components/Component[1]')
        self.assertEqual(copied.one('Pattern/Model3D/Offset')['Y'], Decimal('-1.25'))
        self.assertIs(copied.one('Suppliers').schema, SUPPLIERS)


if __name__ == '__main__':
    unittest.main()
