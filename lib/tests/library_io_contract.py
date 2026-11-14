"""Reusable I/O contract exercised by each standalone library family."""
from dataclasses import replace
from pathlib import Path
import tempfile
from unittest.mock import patch

from lib.common.conversion import ConversionReport
from lib.common.document_families import input_identity, model_identity
from lib.common.errors import UnsupportedFileError
from lib.common.library_context import ImportContext, ExportContext


class LibraryIOContract:
    """The concrete test supplies api, family, native, xml, and make_document."""

    def test_each_input_can_be_edited_and_written_to_every_output(self):
        for input_format in (self.native,'asc',self.xml):
            data = self.api.serialize(self.make_document(),format=input_format,report=ConversionReport())
            document = self.api.parse(data,report=ConversionReport())
            pad = document.one(self.pad_path)
            pad['StringNumber'] = 'A17'
            for output_format in (self.native,'asc',self.xml):
                with self.subTest(input=input_format,output=output_format):
                    output = self.api.serialize(document,format=output_format,report=ConversionReport())
                    rebuilt = self.api.parse(output,report=ConversionReport())
                    self.assertEqual(self.family,rebuilt.representation)
                    self.assertEqual('A17',rebuilt.one(self.pad_path)['StringNumber'])
                    rebuilt.validate()
            self.assertEqual('A17',pad['StringNumber'])
            document.validate()

    def test_generic_dispatch_uses_the_adapter_and_restores_registration(self):
        import lib
        before = dict(lib._FAMILY_ADAPTERS)
        with patch.dict(lib._FAMILY_ADAPTERS,{self.family:self.api}):
            document = self.make_document()
            for key in (self.native,'asc',self.xml):
                data = lib.serialize(document,format=key,report=ConversionReport())
                result = lib.parse(data,report=ConversionReport())
                self.assertEqual(self.family,result.representation)
                self.assertEqual('1',result.one(self.pad_path)['StringNumber'])
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary)/('example.'+self.native)
                lib.write(document,path,report=ConversionReport())
                self.assertEqual(self.family,lib.read(path,report=ConversionReport()).representation)
            self.assertEqual(self.family,lib.format_capabilities('asc',family=self.family).family)
        self.assertEqual(before, lib._FAMILY_ADAPTERS)

    def test_read_uses_content_and_write_uses_an_explicit_or_suffix_format(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            document = self.make_document()
            for key in (self.native,'asc',self.xml):
                path = folder/('design.'+key)
                self.assertIsNone(self.api.write(document,path,report=ConversionReport()))
                misleading = folder/('copy-'+key+'.unknown')
                misleading.write_bytes(path.read_bytes())
                self.assertEqual(self.family,self.api.read(misleading,report=ConversionReport()).representation)
                self.assertEqual(key,input_identity(path.read_bytes()).format)
            generic = folder/'design.xml'
            self.api.write(document,generic,format=self.xml,report=ConversionReport())
            self.assertEqual(self.family,self.api.read(generic,report=ConversionReport()).representation)

    def test_contexts_are_optional_shared_settings_and_source_is_not_changed(self):
        document = self.make_document()
        original = document.one(self.pad_path)['X']
        context = ExportContext()
        self.assertEqual('mm',context.units)
        self.assertEqual('cp1252',ImportContext().ansi_encoding)
        for units in ('mm','mil','inch'):
            data = self.api.serialize(document,format=self.xml,context=replace(context,units=units),report=ConversionReport())
            rebuilt = self.api.parse(data,context=ImportContext(),report=ConversionReport())
            self.assertAlmostEqual(original,rebuilt.one(self.pad_path)['X'],delta=.0001)
        self.assertEqual(original,document.one(self.pad_path)['X'])
        for context in (object(),{'units':'mm'}):
            with self.assertRaises(TypeError):
                self.api.serialize(document,format=self.native,context=context,report=ConversionReport())
            with self.assertRaises(TypeError):
                self.api.parse(self.api.serialize(document,format=self.native),context=context,report=ConversionReport())

    def test_source_inspection_and_detached_projection_remain_separate_from_editing(self):
        document = self.make_document()
        for key in ('asc',self.xml):
            projected = self.api.project(document,format=key,report=ConversionReport())
            self.assertEqual(self.family,model_identity(projected).family)
            with self.assertRaises(TypeError):
                self.api.serialize(projected,format=self.native,report=ConversionReport())
            data = self.api.serialize(document,format=key,report=ConversionReport())
            source = self.api.parse_source(data,report=ConversionReport())
            self.assertEqual(self.family,model_identity(source).family)
            self.assertIn(source.representation,('asc','xml'))
        binary = self.api.serialize(document,format=self.native,report=ConversionReport())
        self.assertEqual(self.family,self.api.parse_source(binary,report=ConversionReport()).representation)
        with self.assertRaises(ValueError):
            self.api.project(document,format=self.native,report=ConversionReport())

    def test_reports_reuse_labels_and_attribute_file_failures_once(self):
        document = self.make_document()
        report = ConversionReport()
        with self.assertRaises(ValueError):
            self.api.parse(b'invalid',report=report,label='read control')
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/('invalid.'+self.native)
            with self.assertRaises(UnsupportedFileError):
                self.api.write(document,path,version=999,report=report,label='write control')
            self.assertFalse(path.exists())
            self.assertEqual(['import','export'],[notice.operation for notice in report.errors])
            self.assertEqual(['read control','write control'],[notice.label for notice in report.errors])
            self.assertEqual(str(path),report.errors[-1].file)
            self.assertEqual(self.native,report.errors[-1].format)
        report.clear()
        self.assertFalse(report.notices)

    def test_explicit_encoding_is_an_asc_option_and_preserves_unicode(self):
        document = self.make_document()
        document.one('/Library')['Name'] = 'Control \u03a9'
        for encoding in ('utf-8','utf-8-sig'):
            data = self.api.serialize(document,format='asc',encoding=encoding,report=ConversionReport())
            result = self.api.parse(data,encoding=encoding,report=ConversionReport())
            self.assertEqual('Control \u03a9',result.one('/Library')['Name'])
        for key in (self.native,self.xml):
            with self.assertRaises(TypeError):
                self.api.serialize(document,format=key,encoding='utf-8',report=ConversionReport())
        self.assertEqual('Control \u03a9',document.one('/Library')['Name'])
