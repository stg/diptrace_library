"""Prepare destination requirements from the current editable design."""


def prepare(document,*,context=None,report=None):
    """Apply output choices without changing the authoring document."""
    from .asc_export import AscExportContext
    if context is not None and not isinstance(context,AscExportContext):
        raise TypeError('DCH conversion context must be an AscExportContext')
    override = getattr(context, 'marking_style', None)
    project_dir = getattr(context, 'project_dir', None)
    compact = getattr(context, 'compact_inactive', None)
    context = (context or AscExportContext()).resolved(document)
    from .asc_export import prepare_export
    view=prepare_export(document,marking_style=override,text_layout=context.text_layout,
                        additional_user_fields=context.additional_user_fields,
                        refresh_user_fields=context.refresh_user_fields,
                        compact_inactive=False if compact is None else compact,
                        destination='dch', report=report,
                        default_main_supplier=context.default_main_supplier)
    schematic=view.one('/Schematic')
    if project_dir is not None:
        schematic.set_field('ProjectDir',project_dir)
    from .pictures import prepare_pictures
    prepare_pictures(schematic,destination='dch',filenames=context.legacy_picture_files,report=report)
    return view
