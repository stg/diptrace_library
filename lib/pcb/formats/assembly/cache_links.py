"""Bind the active PCB library-cache prefix to owned slot identities."""
from ....common.cache_refs import specifications, issue_collections
from ....common.conversion import import_notice
from ....common.structural_edits import assembly
from ...model.cache_links import validate_prefix


def assemble_cache_links(core):
    document = core.document
    board = document.one('/Board')
    validate_prefix(board)
    with assembly(document), document.references.binding_batch():
        links = board.child('DesignCache_Links')
        if links is not None:
            inactive = links.children('Link')[board['DesignCache_Count']+1:]
            if inactive:
                import_notice('info', 'cache-selection-capacity',
                    'Removed unused library-selection capacity rows', inactive,
                    recoverability='all owned definitions and active selection order remain; capacity is generated on output')
                for link in inactive:
                    link.detach()
        for source, target, role, indices, guards in specifications(board):
            if target is None:
                document.references.note(source, role+': target index cannot be resolved', *indices,
                    collections=issue_collections(source, role), guards=guards)
            else:
                document.references.bind(source, target, *indices, role=role, guards=guards, preserve=True)
    return core
