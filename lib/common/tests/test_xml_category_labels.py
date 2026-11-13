"""Category canonicalization preserves independent names and unresolved keys."""
import unittest
from lib.common.model import Element
from lib.common.xml import set_attribute
from lib.common.xml_catalog import CategoryCatalog
from lib.common.xml_plan import XmlPlan


class CategoryLabelProjectionTests(unittest.TestCase):
    def catalog(self):
        rows=Element('Categories');category=rows.add('Category','Parts',7)
        category.add('Type','Discrete',3).add('Subtype','Resistor',9)
        catalog=CategoryCatalog();catalog.seed(rows);return catalog

    def project(self,category,catalog=None):
        return (catalog or self.catalog()).include_plan(XmlPlan.from_element(category))

    def test_index_only_and_named_category_have_the_same_projected_key(self):
        first=Element('Category');set_attribute(first,'Index',7)
        second=first.clone();second.add('Name','Parts')
        self.assertEqual(self.project(first).key(),self.project(second).key())
        self.assertIsNone(first.child('Name'))

    def test_nested_index_only_labels_resolve_without_changing_keys(self):
        category=Element('Category');set_attribute(category,'Index',7)
        row=category.add('CategoryTypes').add('CategoryType')
        kind=row.add('Type');set_attribute(kind,'Index',3)
        subtype=row.add('SubType');set_attribute(subtype,'Index',9)
        result=self.project(category)
        self.assertEqual(result.child('Name').arguments[0].value,'Parts')
        row=result.child('CategoryTypes').child('CategoryType')
        self.assertEqual(row.child('Type').arguments[0].value,'Discrete')
        self.assertEqual(row.child('SubType').arguments[0].value,'Resistor')
        self.assertEqual(row.child('SubType').attribute('Index'),9)

    def test_nested_named_and_key_only_categories_have_the_same_key(self):
        def category(name=None, *, name_last=False):
            result = Element('Category')
            set_attribute(result, 'Index', 7)
            if name is not None and not name_last:
                result.add('Name', name)
            row = result.add('CategoryTypes').add('CategoryType')
            kind = row.add('Type')
            set_attribute(kind, 'Index', 3)
            subtype = row.add('SubType')
            set_attribute(subtype, 'Index', 9)
            if name is not None and name_last:
                result.add('Name', name)
            return result

        expected = self.project(category('Parts')).key()
        for value in (category(), category('', name_last=True), category('Parts', name_last=True)):
            with self.subTest(name=value.child('Name')):
                self.assertEqual(self.project(value).key(), expected)

    def test_unknown_index_remains_unresolved(self):
        category=Element('Category');set_attribute(category,'Index',20)
        result=self.project(category)
        self.assertEqual(result.attribute('Index'),20)
        self.assertIsNone(result.child('Name'))

    def test_explicit_different_name_keeps_its_existing_allocation_behavior(self):
        category=Element('Category');set_attribute(category,'Index',7);category.add('Name','Other')
        result=self.project(category)
        self.assertEqual(result.child('Name').arguments[0].value,'Other')
        self.assertNotEqual(result.attribute('Index'),7)

    def test_empty_declared_label_is_not_replaced_with_a_guess(self):
        rows=Element('Categories');rows.add('Category','',7);catalog=CategoryCatalog();catalog.seed(rows)
        category=Element('Category');set_attribute(category,'Index',7)
        self.assertIsNone(self.project(category,catalog).child('Name'))


if __name__=='__main__':unittest.main()
