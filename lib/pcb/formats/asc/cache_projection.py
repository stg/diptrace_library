"""PCB ASC embedded slots, catalogues and explicit project/library references."""
from ....common.asc_library import project_catalogs, project_library_paths
from ....common.conversion import info, warn
from ....common.model import Element
from ....common import library_metadata
from ...model import library_records as model
from ...model.cache_links import validate_prefix
from ..cache_domains import physical_domain
from ..errors import PcbError
from .cache_symbols import project_symbol
from .cache_footprints import project_pattern
from .global_projection import CACHE_FIELDS
from .projection import check, collection, fields


def _physical(slot, definitions, report):
    patterns = tuple(definition.one('Pattern') for definition in definitions
                     if definition.child('Pattern') is not None)
    selected = physical_domain(slot, definitions)
    others = tuple(pattern for pattern in patterns if pattern is not selected)
    if others:
        warn(report,'cached-secondary-patterns','asc',
             'ASC carries one physical footprint per cached component slot',others,
             recoverability='the pin-assignment footprint remains; independent secondary physical definitions are omitted')
    if selected.parent is not definitions[0]:
        info(report,'cached-footprint-position','asc',
             'Placed the shared cached footprint alongside the first symbol variant',(selected,),
             recoverability='symbol order, shared physical data and pin assignments retain their meaning')
    return selected


def _cache(source, report):
    check(source,model.CACHE)
    try:
        output = project_catalogs(source)
    except ValueError as error:
        raise PcbError(str(error)) from error
    for name in ('Categories','Subfolders'):
        if (section := source.child(name)) is not None:
            for node in section.walk(include_self=True):
                if node.schema is not None:
                    check(node,node.schema)
    components = output.add('cl_Components')
    paths = output.add('Design_Cache_Specific')
    for slot in collection(source,'Slots',model.SLOTS,model.SLOT):
        paths.add('cl_pt',slot['LibPath'],slot.get('VariablePath',''))
        target = components.add('cl_Component')
        definitions = tuple(slot.children('Definition'))
        for definition in definitions:
            check(definition,model.DEFINITION)
            if definition.child('Part') is None:
                raise PcbError(f'{definition.path}: ASC requires a cached symbol for this definition')
        if definitions:
            pattern = _physical(slot,definitions,report)
            first = definitions[0].one('Part')
            datasheet = first.get('Datasheet','')
            for definition in definitions:
                part = definition.one('Part')
                target.append(project_symbol(part,report=report))
                if part is not first and part.child('Datasheet') is not None:
                    notice = info if not part['Datasheet'] or part['Datasheet'] == datasheet else warn
                    notice(report,'cached-secondary-datasheet','asc',
                           'ASC carries one datasheet value per cached component slot',(part,),
                           recoverability='the first symbol datasheet remains; independent secondary datasheet values are omitted')
            target.append(project_pattern(pattern,datasheet=datasheet,report=report))
        if slot.get('Model3DFile_Variable',''):
            warn(report,'empty-slot-model-path','asc',
                 'ASC has no independent slot model path outside a physical definition',(slot,))
    for name in ('Patterns','PadStyles','PatternCategories'):
        branch = source.child(name)
        if branch is not None and branch.children():
            warn(report,'independent-library-definitions','asc',
                 'ASC cannot carry independent library '+name,(branch,),
                 recoverability='cached/placed physical geometry remains; unused independent definitions are omitted')
    return output


def project_cache(board, *, report=None):
    """Emit current cache selections without discovering external resources."""
    validate_prefix(board)
    output = Element('Board')
    fields(board,output,exclude=board.schema.fields.keys()-CACHE_FIELDS)
    for name,kind,schema in (('ProjectLibs_Folders','Folder',library_metadata.PROJECT_FOLDERS),
                              ('ProjectLibs_Libs','Lib',library_metadata.PROJECT_LIBRARIES)):
        source = board.child(name)
        if source is not None:
            collection(board,name,schema,library_metadata.LIBRARY_PATH)
            try:
                output.append(project_library_paths(source,kind))
            except ValueError as error:
                raise PcbError(str(error)) from error
    links = board.child('DesignCache_Links')
    if links is not None:
        members = collection(board,'DesignCache_Links',model.DESIGN_LINKS,library_metadata.DESIGN_LINK)
        target = output.add('DesignCache_Links',len(members))
        for member in members:
            target.add('Link',member['SlotIndex'])
            if board._owner().references.unresolved_slot(member):
                warn(report,'unresolved-design-cache-slot','asc',
                     'Active design-cache selection is unavailable',(member,),
                     recoverability='the explicit unresolved slot index remains')
    if (source := board.child('CacheLib')) is not None:
        output.append(_cache(source,report))
    return output
