"""Per-pad and per-net XML overrides whose meaning is shared by PCB inputs."""
from ....common.model import Element
from ...model.pad_records import TEARDROP
from ....common.xml_records import enum_value, length
from ....common.xml_pads import read_mask_paste
from .keys import position


def read_teardrop_params(record, owner):
    if record is None:
        return
    result = owner.add('TeardropParams')
    for name, field in TEARDROP.fields.items():
        value = record.integer(name, field.default) if field.kind == 'integer' else record.number(name, field.default)
        result.add(name, value)
    record.finish()


def read_pad_options(record, pad, *, units, layers=None):
    pad.add('SignalDelay', record.number('SignalDelay', 0))
    pad.set_field('ShieldGroup', record.integer('ShieldGroup', -1))
    if record.has('DefStyle'):
        pad.set_field('Standard', record.boolean('DefStyle'))
    for public, own in (('HideRingLay', 'HideLayer'), ('BlindLay', 'BlindLayer')):
        source = record.take(public)
        if source is None:
            continue
        target = pad.add(own)
        for item in source.children('Item'):
            value = item.content()
            if value.kind != 'number' or value.unit or value.value != int(value.value):
                raise ValueError(f'{item.node.path}: expected an integer pad layer')
            key = int(value.value)
            if layers is not None:
                key = position(key, layers, label='pad layer', path=item.node.path)
            target.add('Item', key)
            item.finish(allow_text=True)
        source.finish()
    read_mask_paste(record.take('MaskPaste'), pad, units=units, partial=True)
    read_teardrop_params(record.take('TeardropParams'), pad)
    rows = record.rows('CustomSpokes', 'CustomSpoke')
    if rows:
        target = pad.add('CustomSpokes')
        for source in rows:
            key = source.integer('Lay', -1)
            if layers is not None:
                key = position(key, layers, label='pad thermal layer', path=source.node.path)
            target.add('CustomSpoke', key,
                enum_value(source.value('Type', 0), ()), enum_value(source.value('Spoke', 0), ()),
                length(source.number('Width', 0), units))
            source.finish()
