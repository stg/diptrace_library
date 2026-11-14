"""Library contexts expose useful defaults without installation assumptions."""
from dataclasses import replace
import unittest

from lib.common.library_context import ImportContext, ExportContext, import_context, export_context


class LibraryContextTests(unittest.TestCase):
    def test_codec_defaults_aliases_and_invalid_configuration(self):
        self.assertEqual('cp1252',import_context(None).ansi_encoding)
        self.assertEqual('cp1252',ImportContext('windows-1252').ansi_encoding)
        with self.assertRaises(LookupError):
            ImportContext('not-a-codec')
        with self.assertRaises(TypeError):
            ImportContext(42)
        with self.assertRaises(TypeError):
            import_context(object())

    def test_export_defaults_and_independent_overrides(self):
        context = export_context(None)
        self.assertEqual(('mm',.3,None,None),
                         (context.units,context.line_width,context.text_layout,context.target_application))
        changed = replace(context,units='inch',line_width=.9)
        self.assertEqual(('inch',.9),(changed.units,changed.pen(4)))
        self.assertEqual(('mm',.3),(context.units,context.pen(4)))
        callback = ExportContext(line_width=lambda layer:layer/10)
        self.assertEqual((.4,.6),(callback.pen(4),callback.pen(6)))

    def test_invalid_export_settings_fail_before_conversion(self):
        for value in (-1,float('nan'),float('inf')):
            with self.subTest(value=value),self.assertRaises(ValueError):
                ExportContext(line_width=value)
        for value in (True,'wide',None):
            with self.subTest(value=value),self.assertRaises(TypeError):
                ExportContext(line_width=value)
        with self.assertRaises(TypeError):
            ExportContext(text_layout=object())
        with self.assertRaises(TypeError):
            ExportContext(target_application=5351)
        with self.assertRaises(TypeError):
            export_context(object())


if __name__=='__main__':
    unittest.main()
