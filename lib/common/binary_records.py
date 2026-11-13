"""Read and write named scalar fields and tuple records.

Readers attach byte provenance. Adapters supply scalar codecs, format names,
layouts and their own import/output policy, including version gates.
"""
from .model import Element, SourceSpan, Value, _valid_element_name
from .binary import BinaryWriter
from .element_storage import RecordItems
from .drawing_records import POINT
from .record_storage import RecordLayout
from .schema import MISSING


_POINT_LAYOUT = RecordLayout.for_schema(POINT)
_POINT_SLOTS = tuple(_POINT_LAYOUT.slots[name] for name in ('X', 'Y'))
_POINT_POSITIONS = tuple(_POINT_LAYOUT.positions[slot] for slot in _POINT_SLOTS)
_POINT_MASK = sum(1 << slot for slot in _POINT_SLOTS)


def grid_step_value(numerator, divisor):
    """Decode a scaled floating grid independently of decimal contexts."""
    return float(numerator)/max(1, divisor)


def write_grid_step(writer, size):
    """Keep fine grid spacing in a scaled number plus generated denominator."""
    size = float(size)
    divisor = max(1, min(100000, round(1000/size))) if size >= .000001 else 100000
    writer.number(size*divisor)
    writer.integer(divisor)


class RecordReader:
    source_format = 'binary'
    compact_fields = True
    retain_source = True

    def _annotate(self, node):
        pass

    def argument(self, kind):
        start = self.pos
        value = getattr(self, kind)()
        value_kind = {'text': 'string', 'boolean': 'boolean'}.get(kind, 'number')
        return Value(value, value_kind, source=(
            SourceSpan(self.source_format, start, self.pos, self.source) if self.retain_source else None))

    def record_definition(self, parent):
        return parent.schema

    def _add(self, parent, name, values, *, handle):
        """Construct decoder-owned content before the model audit/binding step."""
        if not name or not _valid_element_name(name):
            raise ValueError('invalid decoder record name: '+repr(name))
        values = tuple(Value.of(value) for value in values)
        storage = self._field_storage(parent)
        if storage is not None and storage.import_field(name, values):
            return storage.field(storage.storage.layout.slots[name]) if handle else None
        node = parent._append_import(Element(name, *values))
        return node if handle else None

    def add(self, parent, name, *values):
        """Construct a named record/field and return its normal editable view."""
        return self._add(parent, name, values, handle=True)

    def add_into(self, parent, name, *values):
        """Construct content whose field view the decoder does not need."""
        self._add(parent, name, values, handle=False)

    def _field_storage(self, parent):
        if not self.compact_fields:
            return None
        if type(parent._content) is not RecordItems:
            untyped = getattr(self, '_untyped_records', None)
            if untyped is None:
                untyped = self._untyped_records = {}
            state = (parent.parent, parent.kind)
            if parent.schema is None and untyped.get(parent) == state:
                return None
            schema = self.record_definition(parent)
            if schema is None:
                untyped[parent] = state
                return None
            parent._content = RecordItems(parent, schema, parent._content, retain_debug=self.retain_source)
            parent._children_cache = parent._positions_cache = None
        return parent._content

    def record(self, parent, name, *kinds):
        start = self.pos
        node = parent._append_import(Element(name, *(self.argument(kind) for kind in kinds),
            source=SourceSpan(self.source_format, start, self.pos, self.source)))
        self._field_storage(node)
        self._annotate(node)
        return node

    def points(self, parent, count):
        """Construct neutral X/Y rows directly in their current value slots.

        Adapters select this for coordinate pairs whose meaning is already
        current. Other tuple layouts retain record(); provenance requests use
        that path too. No relationship or authoring policy runs during decoding.
        """
        if type(count) is not int or count < 0:
            raise ValueError('point count must be a nonnegative integer')
        if self.retain_source or not self.compact_fields:
            for _ in range(count):
                self.record(parent, 'pt', 'number', 'number')
            return parent
        x_slot, y_slot = _POINT_SLOTS
        for _ in range(count):
            x, y = self.number(), self.number()
            node = Element('pt')
            content = RecordItems(node, POINT)
            node._schema, node._content = POINT, content
            content.storage._values[x_slot], content.storage._values[y_slot] = x, y
            content.storage._order.extend(_POINT_SLOTS)
            content.order.extend(_POINT_POSITIONS)
            content.dirty_fields = content.reordered_fields = _POINT_MASK
            parent._append_import(node)
            self._annotate(node)
        return parent

    def field(self, parent, name, kind, *, replace=False):
        storage = self._field_storage(parent)
        if (storage is not None and not self.retain_source
                and storage.can_import(name, replace=replace)):
            storage.import_value(name, getattr(self, kind)(), replace=replace)
            return storage.field(storage.storage.layout.slots[name])
        value = self.argument(kind)
        if storage is not None and storage.import_field(name, (value,), replace=replace, source=value.source):
            return storage.field(storage.storage.layout.slots[name])
        node = parent.child(name) if replace else None
        if node is None:
            node = parent._append_import(Element(name, value, source=value.source))
        else:
            # Import replacement is authoritative even when an earlier codec
            # produced an equal number with a different numeric representation.
            node._items = [value]
            node.source = value.source
        self._annotate(node)
        return node

    def fields(self, parent, layout, *, replace=False):
        storage = self._field_storage(parent)
        for name, kind in layout:
            if storage is None:
                self.field(parent, name, kind, replace=replace)
            else:
                if not self.retain_source:
                    raw = getattr(self, kind)()
                    if storage.import_value(name, raw, replace=replace):
                        continue
                    value = Value(raw, {'text': 'string', 'boolean': 'boolean'}.get(kind, 'number'))
                else:
                    value = self.argument(kind)
                if not storage.import_field(name, (value,), replace=replace, source=value.source):
                    node = parent.child(name) if replace else None
                    if node is None:
                        parent._append_import(Element(name, value, source=value.source))
                    else:
                        node._items = [value]
                        node.source = value.source
        return parent

    def field_into(self, parent, name, kind, *, replace=False):
        """Decode a scalar without requesting an editable leaf view."""
        return self.fields(parent, ((name, kind),), replace=replace)


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
        content = parent._content
        slot = content.storage.layout.slots.get(name) if type(content) is RecordItems else None
        direct = (slot is not None and content.storage.layout.definitions[slot].kind != 'tuple'
                  and content.value(name) is not MISSING and name not in content._owned_records())
        node = None if direct else parent.child(name)
        if node is not None and len(node.arguments) != 1:
            raise ValueError(f'{node.path}: expected one scalar binary value')
        try:
            value = parent[name]
            self.value(codec, self.field_value(parent, name, codec, value))
        except KeyError:
            node = parent.child(name)
            path = node.path if node is not None else parent.path.rstrip('/')+'/'+name
            raise ValueError(f'{path}: scalar binary value is missing') from None
        except (TypeError, ValueError) as error:
            node = parent.child(name)
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
