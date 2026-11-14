"""Construct the owned pattern model from decoded standalone records.

This adapter is under development and is not registered as public support.
"""
from ....common import footprint_objects
from ....common.conversion import import_notice, import_diagnostics
from ....common.pad_defaults import matches_defaults
from ....common.structural_edits import assembly
from ...model import new_library
from ..import_patterns import normalize, finish, fill_defaults, active_pad_indices
from .decode import decode


def refresh_standard_pads(pattern):
    """Binary loading refreshes style membership without replacing geometry."""
    changed = []
    pads = pattern.one('Pads').children('Pad')
    for index in active_pad_indices(pattern):
        pad = pads[index]
        if pad['PadShape_New'] == 20:
            continue
        standard = matches_defaults(pattern, pad, mirrored=pad['Sided'])
        if pad['Standard'] != standard:
            pad.set_field('Standard', standard)
            changed.append(pad)
    if changed:
        import_notice('info', 'pad-default-status',
                      'Refreshed pad default-style membership from current physical settings.', changed)


@import_diagnostics('lib')
def parse(data, *, source=None, ansi_encoding='cp1252'):
    decoded = decode(data,source=source,ansi_encoding=ansi_encoding)
    return construct(decoded)


def construct(decoded):
    """Own decoded semantic records; serialized counts/tokens stay outside."""
    document = new_library(decoded.header.name,hint=decoded.header.hint)
    library = document.one('/Library')
    with assembly(document):
        library.one('Categories').detach()
        library.append(decoded.root.one('Categories').detach())
    inputs = []
    pattern_defaults, pad_defaults = footprint_objects.new_pattern(), footprint_objects.new_pad()
    for pattern in tuple(decoded.root.one('Patterns').children('Pattern')):
        pattern.detach()
        fill_defaults(pattern,pattern_defaults=pattern_defaults,pad_defaults=pad_defaults)
        refresh_standard_pads(pattern)
        imported = normalize(pattern,
            pad_indices=active_pad_indices(pattern),
            shape_indices=[index for index,shape in enumerate(pattern.select('Shapes/Shape')) if shape['Type'] > 0],
            hole_indices=[index for index,hole in enumerate(pattern.select('Holes/Hole')) if hole.values[0]])
        # Normalization has established this entry; finish audits the full model.
        with assembly(document):
            library.one('Patterns').append(pattern)
        inputs.append(imported)
    return finish(document,inputs)
