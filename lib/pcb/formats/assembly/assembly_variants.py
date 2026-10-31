"""Resolve assembly choices once, without keeping duplicate saved positions."""
from ....common.conversion import import_notice
from ....common.references import Index
from ....common.structural_edits import assembly
from ...model import assembly_variants as model
from ...model.table_records import UPDATE
from ..errors import PcbError


def assemble_variants(core):
    document, board = core.document, core.document.one('/Board')
    settings = board.child('Settings')
    earlier = settings.child('AssemblyVariants') if settings is not None else None
    variants = board.child('AssemblyVariants')
    if earlier is not None and variants is not None:
        raise PcbError('duplicate assembly variant collections')
    plans, unresolved = [], []
    with assembly(document):
        if earlier is not None:
            earlier.move_to(board)
            variants = earlier
        if variants is None:
            variants = board.add('AssemblyVariants')
        if variants.arguments:
            raise PcbError('unexpected assembly-variant collection arguments')
        variants.bind_schema(model.VARIANTS)
        for variant in variants.children():
            if variant.kind != 'AssemblyVariant' or len(variant.values) != 1 or not isinstance(variant.values[0], str):
                raise PcbError('assembly variants require one name per row')
            variant.bind_schema(model.VARIANT)
        choices = dict(enumerate(variants.children('AssemblyVariant')))
        for component in core.components.records:
            exclusions = component.child('AssemblyExclude')
            if exclusions is None:
                continue
            if exclusions.arguments:
                raise PcbError('unexpected component exclusion collection arguments')
            exclusions.bind_schema(model.EXCLUSIONS)
            for member in exclusions.children():
                if member.kind != 'Item' or len(member.values) != 1 or type(member.values[0]) is not int:
                    raise PcbError('component assembly exclusions require integer positions')
                index = member.values[0]
                member.set_values()
                member.bind_schema(model.MEMBER)
                plans.append((member, model.EXCLUSION_ROLE, index, 'UnresolvedIndex'))
        for update in board.select('Tables/Table/AutoUpdate'):
            index = update.get('AssemblyVariant', 0)
            if type(index) is not int:
                raise PcbError('table assembly selection requires an integer position')
            if (slot := update.child('AssemblyVariant')) is not None:
                slot.detach()
            update.bind_schema(UPDATE)
            # A document without named variants has no variant identity behind
            # the unused default selector. Do not invent a named base variant.
            if index == 0 and not choices:
                index = -1
            plans.append((update, model.TABLE_ROLE, index, 'UnresolvedAssemblyVariant'))
        with document.references.binding_batch():
            for source, role, index, missing in plans:
                if index < 0:
                    continue
                target = choices.get(index)
                if target is not None:
                    document.references.bind(source, target, role=role, preserve=True)
                else:
                    slot = source.add(missing, index)
                    document.references.note(source, role+': assembly variant cannot be resolved', Index(slot), collections=(variants,))
                    unresolved.append(source)
    if unresolved:
        import_notice('warning', 'unresolved-assembly-variant', 'Assembly selections refer to unavailable named variants',
            unresolved, recoverability='unresolved selections can be repaired or cleared')
    return core
