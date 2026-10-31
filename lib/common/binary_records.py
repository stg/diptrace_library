"""Read and write named scalar fields and tuple records.

Readers attach byte provenance. Adapters supply scalar codecs, format names,
layouts and their own import/output policy, including version gates.
"""
from .model import Element, SourceSpan, Value
from .binary import BinaryWriter
from decimal import Context, Decimal, localcontext


def grid_step_value(numerator, divisor):
    """Decode a scaled grid independently of the caller's decimal precision."""
    with localcontext(Context(prec=34)):
        return Decimal(numerator)/max(1, divisor)


def write_grid_step(writer, size):
    """Keep fine grid spacing in a scaled number plus generated denominator."""
    size = float(size)
    divisor = max(1, min(100000, round(1000/size))) if size >= .000001 else 100000
    writer.number(size*divisor)
    writer.integer(divisor)


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


class RecordWriter(BinaryWriter):
    """Named scalar and tuple output; adapters supply layouts and value policy."""

    def value(self, codec, value):
        getattr(self, codec)(value)

    def field_value(self, parent, name, codec, value):
        if (codec == 'color' and isinstance(value, int) and not isinstance(value, bool)
                and not 0 <= value <= 0xFFFFFF and -(1 << 31) <= value < (1 << 32)):
            from .conversion import warn
            # The color wire holds RGB, while text formats can supply a signed
            # 32-bit color. Negative/sign-bit values project to black; positive
            # values retain their RGB bytes. Keep the authored value untouched.
            projected = 0 if value < 0 or value >= (1 << 31) else value & 0xFFFFFF
            warn(getattr(self, 'report', None), 'color-rgb-range', self.format_name.lower(),
                 'Binary RGB output projects the extended color '+name, (parent,),
                 recoverability='negative/sign-bit colors become black; positive colors keep their '
                 'low 24 bits; upper color flags are omitted')
            return projected
        return value

    def field(self, parent, name, codec):
        node = parent.child(name)
        if node is not None and len(node.arguments) != 1:
            raise ValueError(f'{node.path}: expected one scalar binary value')
        try:
            value = parent[name]
            self.value(codec, self.field_value(parent, name, codec, value))
        except KeyError:
            path = node.path if node is not None else parent.path.rstrip('/')+'/'+name
            raise ValueError(f'{path}: scalar binary value is missing') from None
        except (TypeError, ValueError) as error:
            path = node.path if node is not None else parent.path.rstrip('/')+'/'+name
            raise type(error)(f'{path}: {error}') from error

    def fields(self, parent, codec, names, **options):
        for name in names.split():
            self.field(parent, name, codec, **options)

    def values(self, node, codecs, *, start=0, trailing=0):
        codecs = codecs.split()
        width = start+len(codecs)+trailing
        if len(node.arguments) != width:
            raise ValueError(f'{node.path}: expected {width} binary tuple values, found {len(node.arguments)}')
        for codec, value in zip(codecs, node.values[start:]):
            self.value(codec, value)

    def rows(self, container, kind, codecs, *, start=0, trailing=0):
        records = container.children() if container is not None else []
        if container is not None and container.schema is not None:
            records = [record for record in records if record.kind not in container.schema.parameters]
        width = start+len(codecs.split())+trailing
        for record in records:
            if record.kind != kind:
                raise ValueError(f'{record.path}: expected {kind} binary row')
            if len(record.arguments) != width:
                raise ValueError(f'{record.path}: expected {width} row values, found {len(record.arguments)}')
        self.integer(len(records))
        for record in records:
            self.values(record, codecs, start=start, trailing=trailing)
