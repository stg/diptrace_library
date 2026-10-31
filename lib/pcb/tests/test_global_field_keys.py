"""Global field names own their generated keys through edits and conversions."""
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats.asc.global_projection import project_globals
from lib.pcb.formats.capabilities import DIP
from lib.pcb.formats.dip.write import encode
from lib.pcb.formats.dipxml.syntax import dumps as xml_text
from lib.pcb.formats.dipxml.write import project_document
from lib.pcb.tests.test_dip_output import configured_document, reopen
from lib.pcb.tests.test_dipxml_library import read as read_xml
from lib.pcb.tests.test_global_projection import design, reopen as reopen_asc


PATH = '/Board/Userfields_Global/UserField'


def add_field(document, name):
    board = document.one('/Board')
    fields = board.child('Userfields_Global')
    if fields is None:
        fields = board.add('Userfields_Global')
    row = fields.add('UserField')
    row['Name'] = name
    for key, value in dict(SilkShow=1, SilkAlign=2, AssyShow=0, AssyAlign=0).items():
        row[key] = value
    return row


class GlobalFieldKeyTests(unittest.TestCase):
    def test_import_discards_stale_key_and_rename_updates_the_computed_view(self):
        document = design()  # Incoming ASC deliberately supplies a stale Value.
        row = document.one(PATH)
        self.assertEqual(row['Value'], 'order')
        self.assertIsNone(row.child('Value'))
        row['Name'] = 'Purchase Code'
        self.assertEqual(row['Value'], 'purchasecode')
        self.assertEqual(project_globals(document.one('/Board')).one('Userfields_Global/Userfield/Value').values,
                         ('purchasecode',))
        current = reopen_asc(document)
        self.assertEqual(current.one(PATH+'[1]')['Name'], 'Purchase Code')
        self.assertEqual(current.one(PATH+'[1]')['Value'], 'purchasecode')
        self.assertEqual(current.one(PATH+'[2]')['Name'], 'Order')
        with self.assertRaises(TypeError):
            row['Value'] = 'a second truth'
        self.assertEqual(row['Name'], 'Purchase Code')

    def test_copy_keeps_names_and_their_keys_independent(self):
        document = design()
        row = document.one(PATH)
        copied = document.copy(row)
        copied['Name'] = 'Other Code'
        self.assertEqual((row['Value'], copied['Value']), ('order', 'othercode'))
        self.assertTrue(all(item.child('Value') is None for item in (row, copied)))

    def test_binary_versions_regenerate_keys_without_stored_duplicates_or_drift(self):
        document = configured_document()
        row = add_field(document, 'Purchase Code')
        before = dumps(document, preserve=False)
        for version in DIP.write_versions:
            with self.subTest(version=version):
                data = encode(document, version=version, report=ConversionReport())
                current = reopen(data, report=ConversionReport())
                field = current.select(PATH)[-1]
                self.assertEqual((field['Name'], field['Value']), ('Purchase Code', 'purchasecode'))
                self.assertIsNone(field.child('Value'))
                self.assertEqual(encode(current, version=version, report=ConversionReport()), data)
        self.assertEqual(row['Name'], 'Purchase Code')
        self.assertEqual(dumps(document, preserve=False), before)

    def test_xml_reconstructs_key_from_name_without_a_loss_warning(self):
        document = configured_document()
        add_field(document, 'Purchase Code')
        report = ConversionReport()
        output = project_document(document, report=report)
        current = read_xml(xml_text(output), report=ConversionReport())
        row = current.select(PATH)[-1]
        self.assertEqual((row['Name'], row['Value']), ('Purchase Code', 'purchasecode'))
        self.assertIsNone(row.child('Value'))
        self.assertNotIn('global-userfield-value', {item.rule for item in report.notices})


if __name__ == '__main__':
    unittest.main()
