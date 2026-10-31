"""Length-check snapshots follow current rows through rule normalization and edits."""
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.model import Element
from lib.common.references import Property, ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.tests.test_dipxml_electrical import prepared
from lib.pcb.tests.test_length_rule_inputs import xml_source


USER = '''<LengthRule Type="By User"><Name>Manual</Name><Rules>
  <Rule NetId="7" Comp1="8" Pad1="17" Comp2="8" Pad2="41" Length="2"/>
</Rules></LengthRule>'''


def error(policy, connection=0):
    return f'''<DesignError Type="TraceLength" X="1" Y="2" Value="3" Rule="4"
      ObjectType1="LengthMatch" Object1="{policy}" SubObject1="{connection}" ObjectType2="-1"/>'''


def source(*errors):
    text = xml_source().replace('<LengthRules>', '<LengthRules>'+USER)
    return text.replace('</Board>', '<DesignErrors>'+''.join(errors)+'</DesignErrors></Board>')


@import_diagnostics('dipxml')
def read(text):
    return assemble_graphics(prepared(text)).document


class DrcLengthTargetTests(unittest.TestCase):
    def test_source_list_positions_become_identities_in_canonical_class_and_user_order(self):
        document = read(source(error(0), error(1)), report=ConversionReport())
        user, generated = document.select('/Board/DesignErrors/DesignError')
        manual = document.one('/Board/LengthRules/LengthRule/Rules/Rule')
        class_row = document.one('/Board/NetClasses/NetClass[2]/LengthResults/Rules/Rule')
        self.assertIs(user['Target1'], manual)
        self.assertIs(generated['Target1'], class_row)
        self.assertEqual((user['Object1'], generated['Object1']), (1, 0))
        self.assertEqual((user['SubObject1'], generated['SubObject1']), (0, 0))
        self.assertEqual((user['Point1'], user['ExtObject1']), (-1, -1))
        self.assertEqual((user['X'], user['Y'], user['Value'], user['Rule']), (3, -6, 9, 12))
        for row in (user, generated):
            for name in ('Object1', 'SubObject1', 'Point1', 'ExtObject1'):
                self.assertIsNone(row.child(name))
        document.references.validate()

    def test_registered_selectors_follow_class_activation_and_policy_and_row_reordering(self):
        document = read(source(error(0), error(1)), report=ConversionReport())
        user, generated = document.select('/Board/DesignErrors/DesignError')
        first_class, active_class = document.select('/Board/NetClasses/NetClass')
        observer = document.root.add('Observed', -1, -1, -1)
        document.references.bind(observer, user, Property(observer, 'Object1', 0))
        document.references.bind(observer, generated, Property(observer, 'Object1', 1))
        document.references.bind(observer, user, Property(observer, 'SubObject1', 2))
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            first_class['CheckLength'] = True
            self.assertEqual(observer.values, (2, 1, 0))
            # Even a class without supplied result rows owns a generated policy.
            self.assertIsNone(first_class.child('LengthResults'))
            manual = user['Target1'].parent.parent
            document.copy(manual, index=0)
            self.assertEqual(observer.values, (3, 1, 0))
            document.copy(user['Target1'], index=0)
            self.assertEqual(observer.values, (3, 1, 1))
            active_class.move_to(active_class.parent, 0)
            self.assertEqual(observer.values, (3, 0, 1))
            with self.assertRaises(ReferenceError):
                active_class['CheckLength'] = False
            self.assertTrue(active_class['CheckLength'])
            generated['Target1'] = None
            active_class['CheckLength'] = False
            self.assertEqual(observer.values, (2, -1, 1))
        document.references.validate()

    def test_retarget_copy_clone_and_scope_guards_preserve_snapshot_values(self):
        document = read(source(error(0)), report=ConversionReport())
        result = document.one('/Board/DesignErrors/DesignError')
        connection = result['Target1']
        duplicate = document.copy(connection)
        result['Target1'] = duplicate
        self.assertEqual(result['SubObject1'], 1)
        duplicate['Length'] = 100
        self.assertEqual(result['Value'], 9)
        observer = document.root.add('PolicyIndex', -1)
        document.references.bind(observer, result, Property(observer, 'Object1'))
        manual_rows = duplicate.parent
        duplicate.move_to(document.one('/Board/NetClasses/NetClass[2]/LengthResults/Rules'))
        self.assertEqual((observer.values, result['SubObject1']), ((0,), 1))
        duplicate.move_to(manual_rows)
        self.assertEqual(observer.values, (1,))
        with self.assertRaises(ReferenceError):
            duplicate.move_to(document.one('/Board/MainLengthRule/Rules'))
        with self.assertRaises(ReferenceError):
            result['ObjectType1'] = 17
        self.assertEqual(result['ObjectType1'], 18)
        clone = document.clone()
        cloned = clone.one('/Board/DesignErrors/DesignError')
        self.assertIsNot(cloned['Target1'], duplicate)
        with self.assertRaises(ReferenceError):
            cloned['Target1'] = duplicate
        cloned['Target1'] = None
        self.assertEqual((cloned['Object1'], cloned['SubObject1']), (-1, -1))
        document.references.validate()
        clone.references.validate()

    def test_source_row_positions_survive_deleted_pad_compaction(self):
        text = source(error(0, 1))
        text = text.replace(USER, USER.replace('<Rules>', '''<Rules>
          <Rule NetId="7" Comp1="8" Pad1="999" Comp2="8" Pad2="41" Length="1"/>'''))
        report = ConversionReport()
        document = read(text, report=report)
        result = document.one('/Board/DesignErrors/DesignError')
        self.assertIs(result['Target1'], document.one('/Board/LengthRules/LengthRule/Rules/Rule'))
        self.assertEqual(result['SubObject1'], 0)
        self.assertIn('stale-length-connections', [notice.rule for notice in report.infos])
        self.assertNotIn('unresolved-design-error-targets', [notice.rule for notice in report.warnings])
        document.references.validate()

    def test_unavailable_policy_stays_explicit_and_can_be_repaired_without_inventing_a_row(self):
        report = ConversionReport()
        document = read(source(error(88)), report=report)
        result = document.one('/Board/DesignErrors/DesignError')
        self.assertEqual(result.one('UnresolvedTarget1').values, (88, 0, -1, -1))
        self.assertIn('unresolved-design-error-targets', [notice.rule for notice in report.warnings])
        with self.assertRaises(ReferenceError):
            result['Target1']
        result['Target1'] = document.one('/Board/LengthRules/LengthRule/Rules/Rule')
        self.assertFalse(document.references.issues)
        self.assertEqual(result['Object1'], 1)
        document.references.validate()

    def test_a_discarded_duplicate_policy_does_not_silently_select_its_replacement(self):
        text = source(error(1), error(2))
        policy = text[text.index('<LengthRule Type="By NetClass"'):text.index('</LengthRules>')]
        text = text.replace('</LengthRules>', policy+'</LengthRules>')
        report = ConversionReport()
        document = read(text, report=report)
        obsolete, current = document.select('/Board/DesignErrors/DesignError')
        with self.assertRaises(ReferenceError):
            obsolete['Target1']
        self.assertEqual(obsolete.one('UnresolvedTarget1').values, (1, 0, -1, -1))
        self.assertIs(current['Target1'], document.one('/Board/NetClasses/NetClass[2]/LengthResults/Rules/Rule'))
        self.assertEqual(current['Object1'], 0)
        self.assertIn('obsolete-class-length-results', [notice.rule for notice in report.infos])
        self.assertIn('unresolved-design-error-targets', [notice.rule for notice in report.warnings])
        obsolete['Target1'] = None
        document.references.validate()

    def test_new_class_with_omitted_optional_activation_keeps_registered_positions_current(self):
        document = read(source(error(0)), report=ConversionReport())
        result = document.one('/Board/DesignErrors/DesignError')
        observer = document.root.add('PolicyIndex', -1)
        document.references.bind(observer, result, Property(observer, 'Object1'))
        classes = document.one('/Board/NetClasses')
        added = classes.append(Element('NetClass', 'Additional').bind_schema(classes.one('NetClass[1]').schema))
        self.assertEqual(observer.values, (1,))
        added['CheckLength'] = True
        self.assertEqual(observer.values, (2,))
        document.remove(added)
        self.assertEqual(observer.values, (1,))
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
