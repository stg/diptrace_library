"""Prepare destination requirements from the current editable design."""


def prepare(document,*,context=None,report=None):
    """Apply output choices without changing the authoring document."""
    from ..export_context import resolve_export_context
    context = resolve_export_context(context, 'dch')
    override = context.marking_style
    project_dir = context.project_dir
    units_override = context.units
    color_override = context.use_part_font_color
    context = context.resolved(document)
    from ..export_view import (prepare_export)
    view=prepare_export(document,marking_style=override,text_layout=context.text_layout,
                        additional_user_fields=context.additional_user_fields,
                        refresh_user_fields=context.refresh_user_fields,
                        compact_inactive=context.compact_inactive,
                        destination='dch', report=report,
                        default_main_supplier=context.default_main_supplier)
    schematic=view.one('/Schematic')
    if project_dir is not None:
        schematic.set_field('ProjectDir',project_dir)
    settings = schematic.one('Settings')
    if units_override is not None:
        for name, unit in (('UnitsMM', 'mm'), ('UnitsMIL', 'mil'), ('UnitsINCH', 'in')):
            settings.set_field(name, context.units == unit)
    if color_override is not None:
        settings.set_field('UsePartFontColor', color_override)
    from ..pictures import (prepare_pictures)
    prepare_pictures(schematic,destination='dch',filenames=context.legacy_picture_files,report=report)
    return view
