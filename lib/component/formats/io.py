"""Component file/buffer API, awaiting public family activation."""
from ...common.library_io import LibraryIO
from .capabilities import FORMATS
from .elixml.syntax import DIALECT


class _ComponentIO(LibraryIO):
    family, native_format, xml_format = 'component', 'eli', 'elixml'
    formats, xml_dialect = FORMATS, DIALECT

    def _load(self,key,data,*,source,encoding,context):
        if key=='eli':
            from .eli.read import parse
            return parse(data,source=source,ansi_encoding=encoding or context.ansi_encoding)
        if key=='asc':
            from .asc.read import parse
            return parse(data,source=source,encoding=encoding)
        from .elixml.read import parse
        return parse(data,source=source)

    def _binary(self,document,*,version,context,report):
        from .eli.write import encode
        return encode(document,version=version,report=report,text_layout=context.text_layout)

    def _project(self,key,document,*,version,context,encoding,report):
        if key=='asc':
            from .asc.write import project_document
            return project_document(document,version=version,encoding=encoding,report=report,
                line_width=context.pen,text_layout=context.text_layout,target_application=context.target_application)
        from .elixml.write import project_document
        return project_document(document,version=version,units=context.units,report=report,text_layout=context.text_layout)

    def _asc_text(self,document):
        from .asc.write import COLLECTIONS
        from ...common.asc_library_output import dumps
        return dumps(document,collections=COLLECTIONS)

    def _xml_source(self,data,*,source):
        from .elixml.syntax import loads
        return loads(data,source=source,retain_source=True)


_api = _ComponentIO()
format_capabilities = _api.format_capabilities
parse, read = _api.parse, _api.read
parse_source, read_source = _api.parse_source, _api.read_source
project, serialize, write = _api.project, _api.serialize, _api.write

__all__ = ['format_capabilities','parse','read','parse_source','read_source','project','serialize','write']
