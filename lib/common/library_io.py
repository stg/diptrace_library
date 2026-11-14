"""Shared file/buffer workflow; standalone families supply their adapters.

    No document-domain or adapter imports belong here. This layer chooses a
    declared format, owns diagnostics and byte encoding, and delegates meaning
    to the family. Content selects inputs; suffixes select outputs by default.
"""
import codecs
from pathlib import Path

from .asc_library import loads_library, loads_library_bytes
from .conversion import import_diagnostics, export_diagnostics, _set_import_format
from .document_families import input_identity, model_identity
from .errors import UnsupportedFileError
from .library_context import import_context, export_context
from .model import Document
from .text.windows_1252 import encode as ansi_bytes
from .unit_views import canonical
from .xml import dumps_plan


class LibraryIO:
    """A family supplies format capabilities and a few narrow codec operations."""
    family = native_format = xml_format = None
    formats = {}

    def format_capabilities(self,format):
        key = format.lower().lstrip('.')
        try:
            return self.formats[key]
        except KeyError:
            raise UnsupportedFileError(format=key,family=self.family) from None

    def _input(self,data,format):
        identity = input_identity(data)
        key = format.lower().lstrip('.') if format is not None else identity.format
        _set_import_format(key)
        if identity.family not in (None,self.family):
            raise UnsupportedFileError(format=key,family=identity.family,
                                       version=identity.version,reason='family')
        if key is None:
            raise UnsupportedFileError(family=self.family,version=identity.version)
        self.format_capabilities(key)
        # The decoder validates its version after parsing the declaration.
        # Do not reject equivalent numeric spellings based on a lexical sniff.
        return key

    def _output(self,document,format,version):
        identity = model_identity(document)
        key = format.lower().lstrip('.')
        if identity.family != self.family:
            raise UnsupportedFileError(format=key,family=identity.family,version=version,reason='family')
        if document.representation != self.family:
            raise TypeError('output requires the editable library model; import source syntax with parse() first')
        return key,self.format_capabilities(key).output_version(version)

    @import_diagnostics()
    def parse(self,data,*,format=None,context=None,source=None,report=None,label=None,encoding=None):
        key = self._input(data,format)
        selected = import_context(context)
        if key==self.xml_format and encoding is not None:
            raise TypeError('XML input uses the encoding in its declaration')
        if key=='asc' and isinstance(data,str) and encoding is not None:
            raise TypeError('ASC encoding selects how a byte buffer is decoded')
        return self._load(key,data,source=source,encoding=encoding,context=selected)

    @import_diagnostics()
    def read(self,path,*,format=None,context=None,report=None,label=None,encoding=None):
        path = Path(path)
        return self.parse(path.read_bytes(),format=format,context=context,source=str(path),encoding=encoding)

    @import_diagnostics()
    def parse_source(self,data,*,format=None,context=None,source=None,report=None,label=None,encoding=None):
        key = self._input(data,format)
        if key==self.native_format:
            return self._load(key,data,source=source,encoding=encoding,context=import_context(context))
        if context is not None:
            raise TypeError('text source inspection does not use an import context')
        if key=='asc':
            if isinstance(data,str):
                if encoding is not None:
                    raise TypeError('ASC encoding selects how a byte buffer is decoded')
                return loads_library(data,source=source,retain_source=True)
            return loads_library_bytes(data,source=source,encoding=encoding,retain_source=True)
        if encoding is not None:
            raise TypeError('XML input uses the encoding in its declaration')
        return self._xml_source(data,source=source)

    @import_diagnostics()
    def read_source(self,path,*,format=None,context=None,report=None,label=None,encoding=None):
        path = Path(path)
        return self.parse_source(path.read_bytes(),format=format,context=context,source=str(path),encoding=encoding)

    @export_diagnostics()
    def project(self,document,*,format,version=None,context=None,report=None,label=None,encoding=None):
        document = canonical(document)
        key,version = self._output(document,format,version)
        if key==self.native_format:
            raise ValueError('binary output has no text tree; use serialize()')
        if key==self.xml_format and encoding is not None:
            raise TypeError('XML output is UTF-8; encoding is an ASC option')
        output = self._project(key,document,version=version,context=export_context(context),
                               encoding=encoding or 'cp1252',report=report)
        if key=='asc':
            return output
        result = Document(representation='xml')
        result.root.append(output.element())
        return result

    @export_diagnostics()
    def serialize(self,document,*,format,version=None,context=None,report=None,label=None,encoding=None):
        document = canonical(document)
        key,version = self._output(document,format,version)
        selected = export_context(context)
        if key==self.native_format:
            if encoding is not None:
                raise TypeError('encoding is an ASC output option')
            return self._binary(document,version=version,context=selected,report=report)
        if key==self.xml_format and encoding is not None:
            raise TypeError('XML output is UTF-8; encoding is an ASC option')
        output = self._project(key,document,version=version,context=selected,
                               encoding=encoding or 'cp1252',report=report)
        if key==self.xml_format:
            return dumps_plan(output,dialect=self.xml_dialect).encode('utf-8')
        text = self._asc_text(output)
        encoding = encoding or 'cp1252'
        return ansi_bytes(text) if codecs.lookup(encoding).name=='cp1252' else text.encode(encoding)

    @export_diagnostics()
    def write(self,document,path,*,format=None,version=None,context=None,report=None,label=None,encoding=None):
        path = Path(path)
        key = format if format is not None else path.suffix.lstrip('.')
        data = self.serialize(document,format=key,version=version,context=context,report=report,encoding=encoding)
        path.write_bytes(data)
