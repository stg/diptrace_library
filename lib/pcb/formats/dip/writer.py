"""Named binary output primitives for supported PCB wire dialects."""
from ....common.binary_records import RecordWriter
from ....common.binary import quantized_number
from ....common.font_codec import compatibility_size
from ....common.schema import MISSING
from ..capabilities import DIP
from ...model.graphic_records import DIMENSION
from ...model.library_records import PIN
from ..symbol_pin_projection import number as pin_number
from ..output_indices import dimension_subobject
from ..local_group_projection import selection as group_selection
from .binary import UnsupportedVersionError
import math


class Writer(RecordWriter):
    format_name = 'DIP'

    def __init__(self, version=None, *, report=None):
        if version is None:
            version = DIP.default_write_version
        if not DIP.supports_write(version):
            raise UnsupportedVersionError(f'DIP output supports schemas {min(DIP.write_versions)} through {max(DIP.write_versions)}')
        super().__init__()
        self.version = version
        self.report = report
        self.compatibility_changes = []

    @staticmethod
    def quarter_turns(angle):
        """A neutral coarse slot; later full angles remain authoritative."""
        return round(float(quantized_number(angle, format_name='DIP'))/(math.pi/2)) % 4

    def header(self):
        signature = b'DTBOARD'
        self.buffer.append(len(signature))
        self.buffer.extend(signature)
        self.integer(self.version)

    def field_value(self, parent, name, codec, value):
        if parent.schema is PIN and name == 'Number':
            return pin_number(parent, destination='dip', report=self.report)
        if parent.schema is DIMENSION and name in ('SubObject1', 'SubObject2'):
            return dimension_subobject(parent, name[-1])
        if name == 'Group' and codec == 'integer' and 'GroupId' in parent.schema.fields:
            return parent['GroupId']
        if codec == 'integer' and name.endswith('FontSize'):
            return compatibility_size(value)
        return super().field_value(parent, name, codec, value)

    def field(self, parent, name, codec):
        if name == 'Group' and codec == 'integer' and parent.schema is not None and 'GroupId' in parent.schema.fields:
            return self.scalar(parent, name, codec)
        if parent.child(name) is None and parent.schema is not None:
            definition = parent.schema.fields.get(name)
            if definition is not None and definition.default is not MISSING:
                return self.scalar(parent, name, codec)
        return super().field(parent, name, codec)

    def scalar(self, parent, name, codec, *, default=MISSING):
        """Read a current fact or its declared default, then an explicit fallback."""
        if name == 'Group' and codec == 'integer' and parent.schema is not None and 'GroupId' in parent.schema.fields:
            return self.integer(group_selection(parent, destination='dip', report=self.report))
        try:
            value = parent[name]
        except KeyError:
            definition = parent.schema.fields.get(name) if parent.schema is not None else None
            value = definition.default if definition is not None else MISSING
            if value is MISSING:
                value = default
            if value is MISSING:
                raise ValueError(f'{parent.path}: {name} is needed for DIP output') from None
        self.value(codec, self.field_value(parent, name, codec, value))

    def scalars(self, parent, codec, names, *, defaults=None):
        defaults = defaults or {}
        for name in names.split():
            self.scalar(parent, name, codec, default=defaults.get(name, MISSING))
