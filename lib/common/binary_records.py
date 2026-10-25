"""Read named scalar fields and tuple records with byte provenance.

The adapter supplies scalar codecs, a source-format name and any import-time
annotations it needs. This layer does not choose schemas or version gates.
"""
from .model import Element, SourceSpan, Value


class RecordReader:
    source_format = 'binary'

    def _annotate(self, node):
        pass

    def argument(self, kind):
        start = self.pos
        value = getattr(self, kind)()
        value_kind = {'text': 'string', 'boolean': 'boolean'}.get(kind, 'number')
        return Value(value, value_kind,
                     source=SourceSpan(self.source_format, start, self.pos, self.source))

    def record(self, parent, name, *kinds):
        start = self.pos
        node = parent.append(Element(name, *(self.argument(kind) for kind in kinds),
            source=SourceSpan(self.source_format, start, self.pos, self.source)))
        self._annotate(node)
        return node

    def field(self, parent, name, kind, *, replace=False):
        value = self.argument(kind)
        node = parent.child(name) if replace else None
        if node is None:
            node = parent.append(Element(name, value, source=value.source))
        else:
            node.set_values(value)
            node.source = value.source
        self._annotate(node)
        return node

    def fields(self, parent, layout, *, replace=False):
        for name, kind in layout:
            self.field(parent, name, kind, replace=replace)
        return parent
