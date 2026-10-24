"""Prepare a detached ASC view without changing the editable source document.

Export overrides are optional. Modern label choices and current drawings are
authoritative; destination bookkeeping is generated from them.
"""
from dataclasses import dataclass, field, replace
from typing import Callable

from .model import Document, Element, Value, IncompleteDocumentError
from .references import ReferenceError, Segment
from .markings import MarkingStyle, update_markings, resolve_marking_style, apply_marking_style
from .text_layout import TextLayout, default_layout
from .path_variables import PathVariables
from .export_defaults import default_line_width, display_units
from .conversion import export_diagnostics


def _inactive_pattern_records(part):
    pattern = part.child('Pattern')
    if pattern is None:
        return
    # Pads, drawings and holes have boundary slots outside their real records.
    for index, pad in enumerate(pattern.select('Pads/Pad')[1:-1], 1):
        number = pad.scalar('Number_New')
        if number is not None and number != index:
            yield pad
    for shape in pattern.select('Shapes/Shape')[1:-1]:
        if shape.scalar('Type') <= 0:
            yield shape
    for hole in pattern.select('Holes/Hole')[1:-1]:
        if hole.values and hole.values[0] in (False, 'N'):
            yield hole
    for dimension in pattern.select('Dimensions/Dimension'):
        if dimension.scalar('Enabled') in (False, 'N'):
            yield dimension


def prepare_export(document, *, marking_style=None, text_layout=None, additional_user_fields=(),
                   retain_inactive=(), materialize_markings=True,
                   refresh_user_fields=False, compact_inactive=True, destination='asc', report=None,
                   default_main_supplier=False):
    """Clone the current design and prepare destination record arrays.

    References are rebuilt by identity after compaction. A live connection to an
    inactive record is an error, rather than an invitation to discard topology.
    This is preparation only; it does not mark a partial document as complete.
    """
    override = marking_style
    marking_style = resolve_marking_style(document, marking_style)
    view = document.clone()
    view.rebuild(force=False)
    apply_marking_style(view, override)
    schematic = view.one('/Schematic')
    from .symbol_text import modernize_named_marking_choices
    modernize_named_marking_choices(schematic)
    if destination in ('asc','dch'):
        from .supplier_data import prepare_preferences
        prepare_preferences(schematic,default=default_main_supplier,destination=destination,report=report)
    from .component_links import prepare_component_links
    prepare_component_links(view)
    from .multipart_patterns import prepare_patterns
    prepare_patterns(view)
    from .dch_records import footprints
    from .footprint_frame import prepare_pattern
    if destination in ('asc', 'dchxml'):
        # Public drawing views need selection frames. Binary output encodes
        # current physical coordinates and must not recenter an authored edit.
        for pattern in footprints(schematic):
            if pattern is not None and (pattern.parent.kind != 'Part' or pattern.parent.scalar('Enabled') not in (False, 'N')):
                prepare_pattern(pattern)
    from .wire_visibility import update_wire_visibility
    update_wire_visibility(schematic)
    if refresh_user_fields:
        from .user_fields import refresh_global_user_fields
        refresh_global_user_fields(schematic, destination=destination, report=report)
    choices=schematic.one('ShowUserfield_Global')
    known_keys={row.values[1] for row in choices.children('pt')}
    for row in additional_user_fields:
        if len(row)!=4:
            raise ValueError('global user-field choices require display name, key, state and position')
        if row[1] not in known_keys:
            choices.add('pt',*row)
            known_keys.add(row[1])
    from .angles import prepare_angles
    prepare_angles(view, destination=destination, report=report)
    protected = {target for reference in view.references
                 for target in ((reference.target.start, reference.target.end)
                                if isinstance(reference.target, Segment) else (reference.target,))}
    removed, omitted = set(), []
    for name in ('Components','PageConnectors','Shapes','Nets','Buses','Groups','Tables'):
        if not compact_inactive or name in retain_inactive:
            continue
        collection=schematic.child(name)
        for node in collection.children() if collection else ():
            if node.scalar('Enabled') in (False,'N'):
                removed.update(node.walk(include_self=True))
                omitted.append(node)
    for part in schematic.select('Components/Part'):
        if part in removed:
            continue
        if not compact_inactive and part.scalar('Enabled') in (False,'N'):
            continue
        if compact_inactive:
            for node in _inactive_pattern_records(part):
                removed.update(node.walk(include_self=True))
                omitted.append(node)
        shapes = part.one('Shapes')
        if materialize_markings:
            update_markings(part, schematic, style=marking_style, text_layout=text_layout,
                            protected=protected)
        if compact_inactive:
            for drawing in shapes.children('Shape'):
                if drawing.scalar('Enabled') in (False, 'N'):
                    removed.update(drawing.walk(include_self=True))
                    omitted.append(drawing)
        for pin in part.select('Pins/Pin') if compact_inactive else ():
            if pin.scalar('Enabled') in (False, 'N'):
                removed.update(pin.walk(include_self=True))
                omitted.append(pin)

    from .symbol_text import refresh_symbol_text
    refresh_symbol_text(view)
    # Validate the whole removal plan before modifying either collections or
    # bindings. Self-index bindings on discarded slots disappear with the slot.
    discarded = []
    for reference in view.references:
        if reference.source in removed:
            discarded.append(reference)
            continue
        targets = ((reference.target.start, reference.target.end)
                   if isinstance(reference.target, Segment) else (reference.target,))
        if any(target in removed for target in targets):
            raise ReferenceError(f'{reference.role}: {destination.upper()} compaction would remove a referenced record')
    discarded_issues = [issue for issue in view.references.issues if issue.source in removed]
    if omitted:
        from .conversion import report_omitted_records
        report_omitted_records(omitted, destination=destination, report=report)
    for reference in discarded:
        view.references.discard(reference)
    for issue in discarded_issues:
        view.references.discard_issue(issue)
    for node in list(removed):
        if node.parent is not None and node.parent not in removed:
            node.parent.remove(node)
    if materialize_markings:
        from .schematic_refs import bind_schematic_references
        bind_schematic_references(view)
    view.rebuild(force=True)
    return view


@dataclass(frozen=True)
class AscExportContext:
    """Optional display/export overrides over stored document settings.

    Vector layout is self-contained; system fonts use a supplied measurement
    provider or the lazy Windows backend. Absent settings use mm, vector text and size 2.
    No registry, format application or GUI is consulted.
    """
    units: str | None = None
    project_dir: str | None = None
    marking_style: MarkingStyle | None = None
    grid_snap: bool | None = None
    line_width: Callable[[int],float] | None = None
    text_layout: TextLayout = field(default_factory=default_layout)
    use_part_font_color: bool | None = None
    additional_user_fields: tuple = ()
    legacy_text_slots: tuple | None = None
    legacy_picture_files: tuple | None = None
    path_variables: PathVariables | None = None
    refresh_user_fields: bool = False
    compact_inactive: bool | None = None
    encoding: str | None = None
    default_main_supplier: bool = False

    def __post_init__(self):
        if self.encoding is not None:
            import codecs
            try:
                codecs.lookup(self.encoding)
                ''.encode(self.encoding)
            except LookupError as error:
                raise ValueError(f'unsupported ASC text encoding: {self.encoding}') from error
        if self.units is not None and self.units not in ('mm','mil','in','inch'):
            raise ValueError('ASC display units must be mm, mil or in')
        if self.grid_snap is not None and not isinstance(self.grid_snap,bool):
            raise TypeError('grid_snap must be a boolean')
        if self.marking_style is not None and not isinstance(self.marking_style, MarkingStyle):
            raise TypeError('marking_style must be a MarkingStyle')
        if not isinstance(self.refresh_user_fields, bool):
            raise TypeError('refresh_user_fields must be a boolean')
        if self.compact_inactive is not None and not isinstance(self.compact_inactive, bool):
            raise TypeError('compact_inactive must be a boolean')
        if not isinstance(self.default_main_supplier, bool):
            raise TypeError('default_main_supplier must be a boolean')
        if self.path_variables is not None and not isinstance(self.path_variables, PathVariables):
            raise TypeError('path_variables must be a PathVariables configuration')
        if self.legacy_text_slots is not None and len(self.legacy_text_slots)!=6:
            raise ValueError('legacy text slots require two modes, two alignments and two field names')

    def resolved(self, document):
        schematic = document.one('/Schematic')
        settings = schematic.one('Settings')
        units = self.units or display_units(document)
        return replace(self, units='in' if units == 'inch' else units,
            encoding=self.encoding or 'cp1252',
            compact_inactive=self.compact_inactive if self.compact_inactive is not None else True,
            project_dir=self.project_dir if self.project_dir is not None else schematic.scalar('ProjectDir', ''),
            marking_style=resolve_marking_style(document, self.marking_style),
            grid_snap=self.grid_snap if self.grid_snap is not None else settings.scalar('GridSnap', True),
            use_part_font_color=self.use_part_font_color if self.use_part_font_color is not None else settings.scalar('UsePartFontColor', False),
            line_width=self.line_width if self.line_width is not None else default_line_width)


SCHEMATIC_FIELDS = '''Pages PictureCount ShowText TextAlign ShowText2 TextAlign2
HidePower OriginX OriginY FieldName1 FieldName2 PartFontVector ProjectDir
PartFontWidth PartFontScale NetClasses DifferentialPairs ShowRefDes_Global
ShowName_Global ShowValue_Global ShowManufacturer_Global ShowDatasheet_Global
ShowUserfield_Global Components PageConnectors Shapes Nets Buses Groups Tables
Settings ssimulator ProjectLibs_Name ProjectLibs_Type ProjectLibs_Content
ProjectLibs_Folders ProjectLibs_Libs ProjectLibs_Sorted DesignCache_Count
DesignCache_Links CacheLib'''.split()


@export_diagnostics('asc')
def project_document(document, *, context=None, report=None):
    """Build a complete ASC document from current DCH data and explicit context."""
    from .asc_projection import (ProjectionError,_value,_plain,_visible,project_page,
        project_component,project_net,project_settings,project_schematic_drawing)
    from .asc_cache_projection import project_cache
    from .asc_document_projection import (legacy_global_fields,project_page_connector,
        project_bus,project_group,project_table,project_library_paths)
    from .asc_policy import calculation_number
    if not document.complete:
        raise IncompleteDocumentError('complete shared schematic data is required for ASC conversion')
    if context is None:
        context = AscExportContext()
    if not isinstance(context, AscExportContext):
        raise TypeError('ASC conversion context must be an AscExportContext')
    override = context.marking_style
    context = context.resolved(document)
    if document.representation != 'schematic':
        raise ProjectionError('shared schematic data is required; normalize source views with as_schematic()')
    from .schematic_schema import validate_public_content
    validate_public_content(document, allow_xml_fields=True)
    view=prepare_export(document,marking_style=override,text_layout=context.text_layout,
                        additional_user_fields=context.additional_user_fields,
                        refresh_user_fields=context.refresh_user_fields,
                        compact_inactive=context.compact_inactive, report=report,
                        default_main_supplier=context.default_main_supplier)
    from .conversion import apply_capacity
    apply_capacity(view, destination='asc', report=report)
    view.rebuild(force=False)
    source=view.one('/Schematic')
    from .revision_adaptation import prepare_revisions
    prepare_revisions(source, destination='asc', report=report)
    from .pictures import prepare_pictures
    prepare_pictures(source,destination='asc',filenames=context.legacy_picture_files,report=report)
    if context.path_variables is not None:
        from .path_variables import prepare_variable_paths
        prepare_variable_paths(source, context.path_variables,
            project_dir=context.project_dir if context.project_dir is not None else source.scalar('ProjectDir', ''))
    unknown=[n.kind for n in _visible(view.root) if n.kind not in ('Source','Scale','Xpos','Ypos','Schematic')]
    if unknown:
        raise ProjectionError(f'no document projection for {unknown}')
    unknown=[n.kind for n in _visible(source) if n.kind not in SCHEMATIC_FIELDS]
    if unknown:
        raise ProjectionError(f'no schematic projection for {unknown}')
    output=Document(representation='asc')
    output.root.add('Source','DipTrace-Schematic',46)
    output.root.add('Units',context.units)
    value=_value(view.one('/Scale').arguments[0])
    output.root.add('Scale',Value(value.value,value.kind,'%',source=value.source))
    for name in ('Xpos','Ypos'):
        output.root.add(name,round(calculation_number(view.one('/'+name))))
    schematic=output.root.add('Schematic')
    legacy = legacy_global_fields(
        source, initial=context.legacy_text_slots or (0, 0, 0, 0, '', ''))
    def collection(node,kind,project):
        result=Element(node.kind,*map(_value,node.arguments))
        for item in _visible(node):
            if item.kind!=kind:
                raise ProjectionError(f'{node.path}: expected {kind}, found {item.kind}')
            result.append(project(item))
        return result
    layout=context.text_layout
    projectors={
        'Pages':lambda n:collection(n,'Page',project_page),
        'Components':lambda n:collection(n,'Part',lambda p:project_component(p,
            line_width=context.line_width,symbol_text_bounds=layout.symbol_bounds,
            generated_font_name=context.marking_style.font_name if override is not None else context.marking_style.font_name or None)),
        'PageConnectors':lambda n:collection(n,'PageConnector',project_page_connector),
        'Shapes':lambda n:collection(n,'Shape',lambda p:project_schematic_drawing(p,text_bounds=layout.symbol_bounds)),
        'Nets':lambda n:collection(n,'Net',project_net),
        'Buses':lambda n:collection(n,'Bus',project_bus),
        'Groups':lambda n:collection(n,'Group',project_group),
        'Tables':lambda n:collection(n,'Table',project_table),
        'CacheLib':lambda n:project_cache(n,line_width=context.line_width,symbol_text_bounds=layout.symbol_bounds),
        'ProjectLibs_Folders':lambda n:project_library_paths(n,'Folder'),
        'ProjectLibs_Libs':lambda n:project_library_paths(n,'Lib'),
    }
    for name in SCHEMATIC_FIELDS:
        if name=='PictureCount':
            # ASC writes a literal zero; modern pictures are file-backed.
            schematic.add(name,0)
            continue
        if name in legacy:
            schematic.add(name,_value(Value.of(legacy[name])))
            continue
        if name=='ProjectDir' and context.project_dir is not None:
            schematic.add(name,_value(Value.of(context.project_dir)))
            continue
        fields=source.children(name)
        if len(fields)!=1:
            raise ProjectionError(f'{source.path}: expected one {name}, found {len(fields)}')
        node=fields[0]
        if name=='Settings':
            use_color=context.use_part_font_color
            if use_color is None:
                use_color=node.scalar('UsePartFontColor')
            if use_color is None:
                raise ProjectionError('old files require an explicit use_part_font_color choice')
            projected=project_settings(node,grid_snap=context.grid_snap,
                part_font_size=context.marking_style.font_size,part_font_color=context.marking_style.font_color,
                use_part_font_color=use_color)
        else:
            projected=projectors.get(name,_plain)(node)
        if name=='DesignCache_Links':
            projected.set_values(len(projected.children()))
        if name=='ssimulator':
            for item in projected.children():
                if item.kind in ('signals','sim_ac','sim_dc','sim_tran','sim_noise'):
                    item.set_values(len(item.children()))
        schematic.append(projected)
    # Text-file restrictions follow geometry. This also reports irreversible
    # substitutions using only fields actually present in the destination.
    from .asc_policy import project_text
    project_text(output, encoding=context.encoding, report=report)
    output.metadata.update(source_format='asc',projected_from='schematic',
        source_version=46,asc_layout='schematic-46',
        export_equivalence_verified=False)
    output._source_encoding=context.encoding
    from .schematic_refs import bind_schematic_references
    bind_schematic_references(output)
    return output
