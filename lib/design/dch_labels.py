"""Upgrade old label choices into the public ASC/DCHXML vocabulary.

Settings are data; producing text shapes and measuring fonts are separate
operations. Font-dependent instance migration accepts an explicit layout
environment; it never starts DipTrace or reads application settings itself.
"""


GLOBAL_COMPATIBILITY_FIELDS = ('ShowText', 'ShowText2', 'TextAlign', 'TextAlign2',
                               'FieldName1', 'FieldName2')
COMPONENT_COMPATIBILITY_FIELDS = ('ShowText', 'TextAlign', 'ShowText2', 'TextAlign2',
                                  'TextPosX', 'TextPosY', 'TextPosX2', 'TextPosY2',
                                  'FieldIndex1', 'FieldIndex2', 'Orientation')


def discard_legacy_label_slots(schematic):
    """Remove obsolete slots after modern label choices have been established."""
    from .dch_records import placed_components
    for name in GLOBAL_COMPATIBILITY_FIELDS:
        field = schematic.child(name)
        if field is not None:
            field.detach()
    for part in placed_components(schematic):
        if part.child('ShowRefDes') is None:
            raise ValueError('modern label choices are required before discarding old slots')
        for name in COMPONENT_COMPATIBILITY_FIELDS:
            field = part.child(name)
            if field is not None:
                field.detach()


def upgrade_global_labels(version, schematic):
    if version >= 40:
        return
    labels = {
        'ShowRefDes_Global': [2, 1, 7],
        'ShowName_Global': [2, 1, 7],
        'ShowValue_Global': [2, 7],
        'ShowManufacturer_Global': [2, 7],
        'ShowDatasheet_Global': [2, 7],
    }
    user_fields = schematic.add('ShowUserfield_Global')
    targets = {1: 'ShowName_Global', 2: 'ShowRefDes_Global', 3: 'ShowValue_Global',
               4: 'ShowName_Global', 6: 'ShowManufacturer_Global', 7: 'ShowDatasheet_Global'}
    for suffix, field_name in (('', 'FieldName1'), ('2', 'FieldName2')):
        mode = schematic.scalar('ShowText'+suffix)
        alignment = schematic.scalar('TextAlign'+suffix)
        target = targets.get(mode)
        if target:
            values = labels[target]
            values[0], values[-1] = 1, alignment
            if mode == 4:
                values[1] = 2
        elif mode == 5:
            from .user_fields import user_field_key
            name = schematic.scalar(field_name)
            user_fields.add('pt', name, user_field_key(name), 1, alignment)
    for name, values in labels.items():
        schematic.add(name, *values).annotations['derived_from'] = 'legacy global label choices'


def upgrade_instance_labels(version, schematic, *, font_size, font_name='', text_layout=None):
    """Populate modern public label tuples using a chosen font environment.

    This explicit operation supports old files whose automatic label placement
    depended on application font settings rather than serialized DCH fields.
    Run before selection dimensions and local origins are modernized. The
    resulting tuples are the current editable facts, without source backups.
    """
    if version >= 40:
        return
    from .asc_policy import calculation_number
    from .dch_records import placed_components
    from .legacy_labels import LegacyLabelSlot, resolve_legacy_labels, LABEL_NAMES
    from .markings import MarkingStyle, marking_width
    from .text_layout import TextLayout
    layout = text_layout or TextLayout()
    style = MarkingStyle(font_size=font_size, font_name=font_name,
        vector=schematic.scalar('PartFontVector') in (True, 'Y'),
        font_width=calculation_number(schematic.one('PartFontWidth')),
        font_scale=calculation_number(schematic.one('PartFontScale')))
    globals_ = [tuple(schematic.scalar(name) for name in names) for names in
                (('ShowText', 'TextAlign'), ('ShowText2', 'TextAlign2'))]
    for part in placed_components(schematic):
        present = [part.child(name) is not None for name in LABEL_NAMES]
        if all(present):
            continue
        if any(present):
            raise ValueError(f'{part.path}: partially upgraded label settings')
        dimensions = [calculation_number(part.one(name)) for name in ('Width', 'Height')]
        outside = False
        for shape in part.select('Shapes/Shape'):
            if shape.scalar('Enabled') not in (True, 'Y') or shape.scalar('Type') != 10:
                continue
            lo, hi = layout.symbol_bounds(shape)
            outside |= any(lo[i] < -dimensions[i]/2 or hi[i] > dimensions[i]/2 for i in (0, 1))
        users = part.one('UserFields').children('UserField')
        def measure(name):
            texts = dict(ShowName=part.values[0], ShowRefDes=part.values[1], ShowValue=part.scalar('Value'),
                         ShowManufacturer=part.scalar('Manufacturer'), ShowDatasheet=part.scalar('Datasheet'))
            text = users[int(name.removeprefix('UserField'))].values[1] if name.startswith('UserField') else texts[name]
            return marking_width(text, style, text_layout=layout)
        slots = []
        for suffix, field_number in (('', 1), ('2', 2)):
            slots.append(LegacyLabelSlot(part.scalar('ShowText'+suffix), part.scalar('TextAlign'+suffix),
                part.scalar('FieldIndex'+str(field_number)), calculation_number(part.one('TextPosX'+suffix)),
                calculation_number(part.one('TextPosY'+suffix))))
        values = resolve_legacy_labels(version=version, first=slots[0], second=slots[1],
            global_first=globals_[0], global_second=globals_[1], dimensions=dimensions,
            user_field_count=len(users), measure_width=measure, outside_text=outside,
            pin_orientations=[pin.scalar('Orientation') for pin in part.select('Pins/Pin')
                              if pin.scalar('Enabled') in (True, 'Y')])
        for name in LABEL_NAMES:
            part.add(name, *values[name])
        for index, user in enumerate(users):
            user.set_values(*user.arguments, *values[f'UserField{index}'])
