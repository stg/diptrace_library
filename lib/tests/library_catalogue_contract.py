"""The same editable catalogue contract for standalone library families."""
from lib.common.conversion import ConversionReport
from lib.common.references import ReferenceError
import xml.etree.ElementTree as ET


class LibraryCatalogueContract:
    def example(self):
        document = self.library()
        categories = document.one('/Library/Categories')
        alpha = categories.add('Category', 'Alpha', 7)
        beta = categories.add('Category', 'Beta', 12)
        kind = alpha.add('Type', 'First', 11)
        sub = kind.add('Subtype', 'One', 21)
        owner = document.one('/Library/'+self.collection).append(self.entry('Example'))
        return document, owner, alpha, beta, kind, sub

    def rows(self, owner):
        return owner.one(self.prefix+'_CategoryTypes')

    def test_selections_coordinate_names_keys_reordering_and_clone(self):
        document, owner, alpha, beta, kind, sub = self.example()
        owner['Category'] = alpha
        row = self.rows(owner).add('CategoryType', '', '', -1, -1)
        row['TypeDefinition'], row['SubTypeDefinition'] = kind, sub
        alpha['Name'], alpha['Index'] = 'Renamed', 8
        kind['Name'], kind['Index'] = 'Other', 15
        sub['Name'], sub['Index'] = 'New', 25
        beta.move_to(beta.parent, index=0)
        self.assertEqual(('Renamed', 8), (owner[self.prefix+'_CategoryName'], owner[self.prefix+'_CategoryIndex']))
        self.assertEqual(('Other', 'New', 15, 25), row.values)
        clone = document.clone()
        copied = clone.one('/Library/'+self.collection+'/'+owner.kind)
        self.assertIs(clone.one('/Library/Categories/Category[2]'), copied['Category'])
        document.validate()
        clone.validate()

    def test_parent_changes_and_foreign_targets_fail_without_partial_edits(self):
        document, owner, alpha, beta, kind, sub = self.example()
        owner['Category'] = alpha
        row = self.rows(owner).add('CategoryType', 'First', 'One', 11, 21)
        for target in (beta, None):
            with self.assertRaises(ReferenceError):
                owner['Category'] = target
        foreign, _, other, _, _, _ = self.example()
        with self.assertRaises(ReferenceError):
            owner['Category'] = other
        with self.assertRaises(ReferenceError):
            row['TypeDefinition'] = None
        self.assertIs(alpha, owner['Category'])
        self.assertIs(sub, row['SubTypeDefinition'])
        row['SubTypeDefinition'] = None
        row['TypeDefinition'] = None
        owner['Category'] = beta
        self.assertEqual(('', '', -1, -1), row.values)
        self.assertIs(beta, owner['Category'])
        document.validate()

    def test_named_scalar_assignment_is_a_coherent_explicit_selection(self):
        document, owner, alpha, _, kind, sub = self.example()
        owner[self.prefix+'_CategoryName'] = 'Alpha'
        self.assertIs(alpha, owner['Category'])
        row = self.rows(owner).add('CategoryType', '', '', -1, -1)
        row['TypeIndex'] = 11
        row['SubType'] = 'One'
        self.assertIs(kind, row['TypeDefinition'])
        self.assertIs(sub, row['SubTypeDefinition'])
        row['SubType'] = ''
        row['TypeIndex'] = -1
        owner[self.prefix+'_CategoryIndex'] = -1
        self.assertIsNone(owner['Category'])
        document.validate()

    def test_detached_import_pairs_bind_only_when_key_and_label_agree(self):
        document, _, alpha, _, _, _ = self.example()
        proposal = self.entry('Missing')
        proposal[self.prefix+'_CategoryName'] = 'Beta'
        proposal[self.prefix+'_CategoryIndex'] = 7
        owner = document.one('/Library/'+self.collection).append(proposal)
        self.assertEqual(('Beta', 7), (owner[self.prefix+'_CategoryName'], owner[self.prefix+'_CategoryIndex']))
        with self.assertRaises(ReferenceError):
            _ = owner['Category']
        with self.assertRaises(ReferenceError):
            alpha['Name'] = 'Changed'
        owner['Category'] = alpha
        self.assertEqual([], document.references.issues)
        self.assertEqual(('Alpha', 7), (owner[self.prefix+'_CategoryName'], owner[self.prefix+'_CategoryIndex']))
        document.validate()

    def test_copy_and_remove_keep_owned_relationships_scoped(self):
        document, owner, alpha, _, kind, sub = self.example()
        owner['Category'] = alpha
        row = self.rows(owner).add('CategoryType', 'First', 'One', 11, 21)
        copied = document.copy(owner)
        self.assertIs(alpha, copied['Category'])
        self.assertIs(kind, self.rows(copied).one('CategoryType')['TypeDefinition'])
        with self.assertRaises(ReferenceError):
            document.remove(alpha)
        document.remove(copied)
        document.remove(owner)
        document.remove(alpha)
        document.validate()

    def test_all_formats_retain_coherent_classifications(self):
        document, owner, alpha, _, kind, sub = self.example()
        owner['Category'] = alpha
        self.rows(owner).add('CategoryType', 'First', 'One', 11, 21)
        for format in self.formats:
            with self.subTest(format=format):
                restored = self.io.parse(self.io.serialize(document, format=format, report=ConversionReport()),
                                         report=ConversionReport())
                copied = restored.one('/Library/'+self.collection+'/'+owner.kind)
                self.assertEqual('Alpha', copied['Category']['Name'])
                row = self.rows(copied).one('CategoryType')
                self.assertEqual('First', row['TypeDefinition']['Name'])
                self.assertEqual('One', row['SubTypeDefinition']['Name'])
                restored.validate()

    def test_whole_entry_attachment_binds_parent_and_child_choices_together(self):
        document, _, alpha, _, kind, sub = self.example()
        proposal = self.entry('Detached')
        proposal[self.prefix+'_CategoryName'] = 'Alpha'
        proposal[self.prefix+'_CategoryIndex'] = 7
        self.rows(proposal).add('CategoryType', 'First', 'One', 11, 21)
        document.one('/Library/'+self.collection).append(proposal)
        self.assertIs(alpha, proposal['Category'])
        row = self.rows(proposal).one('CategoryType')
        self.assertIs(kind, row['TypeDefinition'])
        self.assertIs(sub, row['SubTypeDefinition'])
        document.validate()

    def test_missing_child_choices_block_scope_changes_until_explicitly_cleared(self):
        document, owner, alpha, beta, kind, sub = self.example()
        owner['Category'] = alpha
        row = self.rows(owner).add('CategoryType', 'Missing', 'Absent', 42, 43)
        with self.assertRaises(ReferenceError):
            row['TypeDefinition'] = kind
        with self.assertRaises(ReferenceError):
            owner['Category'] = beta
        self.assertIs(alpha, owner['Category'])
        self.assertEqual(('Missing', 'Absent', 42, 43), row.values)
        row['SubTypeDefinition'] = None
        row['TypeDefinition'] = kind
        self.assertEqual(('First', '', 11, -1), row.values)
        document.validate()

    def test_binary_and_asc_keep_conflicting_and_empty_labels_explicit(self):
        for label in ('Beta', ''):
            document, _, _, _, _, _ = self.example()
            proposal = self.entry('Unresolved')
            proposal[self.prefix+'_CategoryName'] = label
            proposal[self.prefix+'_CategoryIndex'] = 7
            document.one('/Library/'+self.collection).append(proposal)
            for format in self.formats[:2]:
                with self.subTest(label=label, format=format):
                    restored = self.io.parse(self.io.serialize(document, format=format, report=ConversionReport()),
                                             report=ConversionReport())
                    owner = restored.one('/Library/'+self.collection).children()[-1]
                    self.assertEqual((label, 7), (owner[self.prefix+'_CategoryName'], owner[self.prefix+'_CategoryIndex']))
                    with self.assertRaises(ReferenceError):
                        _ = owner['Category']
                    owner['Category'] = None
                    self.assertEqual(('', -1), (owner[self.prefix+'_CategoryName'], owner[self.prefix+'_CategoryIndex']))
                    restored.validate()

    def test_xml_resolves_names_before_keys_and_introduces_unknown_names(self):
        document, owner, alpha, beta, kind, sub = self.example()
        owner['Category'] = alpha
        self.rows(owner).add('CategoryType', 'First', 'One', 11, 21)
        template = self.io.serialize(document, format=self.formats[2], report=ConversionReport())
        for unknown in (False, True):
            with self.subTest(unknown=unknown):
                root = ET.fromstring(template)
                selected = root.find('Patterns/Pattern/Category' if self.prefix == 'Pattern'
                                     else 'Components/Component/Part/Category')
                selected.find('Name').text = 'New category' if unknown else 'Beta'
                row = selected.find('CategoryTypes/CategoryType')
                row.find('Type').text = 'New type' if unknown else 'First'
                row.find('SubType').text = 'New sub' if unknown else 'One'
                report = ConversionReport()
                restored = self.io.parse(ET.tostring(root, encoding='utf8'), report=report)
                copied = restored.one('/Library/'+self.collection+'/'+owner.kind)
                self.assertEqual('New category' if unknown else 'Beta', copied['Category']['Name'])
                row = self.rows(copied).one('CategoryType')
                self.assertEqual('New type' if unknown else 'First', row['TypeDefinition']['Name'])
                self.assertEqual('New sub' if unknown else 'One', row['SubTypeDefinition']['Name'])
                notices = [notice for notice in report.notices if notice.rule == 'library-catalogue-normalization']
                self.assertTrue(notices)
                self.assertTrue(all(notice.severity == 'info' for notice in notices))
                self.assertTrue(all(path != '/' for notice in notices for path in notice.paths))
                restored.validate()

    def test_ambiguous_xml_export_warns_and_leaves_the_source_unchanged(self):
        document, _, _, _, _, _ = self.example()
        proposal = self.entry('Ambiguous')
        proposal[self.prefix+'_CategoryName'] = 'Beta'
        proposal[self.prefix+'_CategoryIndex'] = 7
        document.one('/Library/'+self.collection).append(proposal)
        report = ConversionReport()
        data = self.io.serialize(document, format=self.formats[2], report=report)
        self.assertEqual(('Beta', 7), (proposal[self.prefix+'_CategoryName'], proposal[self.prefix+'_CategoryIndex']))
        self.assertTrue(any(notice.rule == 'library-catalogue-selection' and notice.severity == 'warning'
                            for notice in report.notices))
        restored = self.io.parse(data, report=ConversionReport())
        self.assertEqual('Beta', restored.one('/Library/'+self.collection).children()[-1]['Category']['Name'])
        with self.assertRaises(ReferenceError):
            _ = proposal['Category']
        document.validate()

    def test_unnamed_primary_selection_warns_before_xml_import_unassigns_it(self):
        document, owner, alpha, _, _, _ = self.example()
        alpha['Name'] = ''
        owner['Category'] = alpha
        report = ConversionReport()
        data = self.io.serialize(document, format=self.formats[2], report=report)
        restored = self.io.parse(data, report=ConversionReport())
        self.assertIsNone(restored.one('/Library/'+self.collection+'/'+owner.kind)['Category'])
        self.assertIs(alpha, owner['Category'])
        self.assertTrue(any(notice.rule == 'library-catalogue-selection' and notice.severity == 'warning'
                            for notice in report.notices))
        document.validate()
