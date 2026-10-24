"""Detached export footprint choices for symbols sharing a multipart RefDes."""
from ...common.references import (ReferenceError, Segment)
from .traversal import (footprint_name)


def prepare_patterns(document):
    groups = {}
    for part in document.select('/Schematic/Components/Part'):
        if part.scalar('Enabled') in (True, 'Y') and part.scalar('AllowParts') in (True, 'Y'):
            groups.setdefault(part.values[1], []).append(part)
    changes = []
    for parts in groups.values():
        patterns = [part.one('Pattern') for part in parts]
        names = [footprint_name(pattern) for pattern in patterns]
        named = [index for index, name in enumerate(names) if name.replace(' ', '')]
        preferred = named[0] if named else None
        if preferred is None or len(patterns[preferred].select('Pads/Pad')) <= 2:
            populated = next((index for index, pattern in enumerate(patterns[1:], 1)
                              if len(pattern.select('Pads/Pad')) > 2), None)
            if populated is not None:
                preferred = populated
        if preferred is None:
            continue
        selected = patterns[preferred]
        for index, pattern in enumerate(patterns):
            if pattern.values[0] != selected.values[0]:
                changes.append((parts[index], pattern, selected))
    removed = {node for part, pattern, selected in changes for node in pattern.walk(include_self=True)}
    owners = {node: part for part, pattern, selected in changes for node in pattern.walk(include_self=True)}
    changed_parts = {part for part, pattern, selected in changes}
    discarded = []
    for reference in document.references:
        targets = ((reference.target.start, reference.target.end)
                   if isinstance(reference.target, Segment) else (reference.target,))
        if reference.source in removed:
            discarded.append(reference)
        elif any(target in removed for target in targets):
            if (reference.role != 'symbol-pin-pad' or reference.source not in changed_parts or
                    any(owners.get(target) is not reference.source for target in targets)):
                raise ReferenceError('multipart footprint replacement needs explicit reference remapping')
            # The format footprint-only copy leaves the symbol pin Number
            # fields unchanged. Rebind those literal assignments into the new
            # owned pad array after replacement; do not match by printed name.
            discarded.append(reference)
    discarded_issues = []
    for issue in document.references.issues if changes else ():
        if issue.source in removed or (issue.source in changed_parts and issue.message.startswith('symbol-pin-pad:')):
            discarded_issues.append(issue)
        elif issue.collections is None or any(parent in removed or parent in changed_parts for parent in issue.collections):
            raise ReferenceError('multipart footprint replacement needs explicit unresolved-reference remapping')
    for reference in discarded:
        document.references.discard(reference)
    for issue in discarded_issues:
        document.references.discard_issue(issue)
    for part, pattern, selected in changes:
        position = part.children().index(pattern)
        pattern.detach()
        replacement = selected.clone()
        replacement.annotations['derived_from'] = 'selected footprint of the same multipart component'
        part.insert(replacement, position)
    if changes:
        from .refs import (bind_schematic_references)
        bind_schematic_references(document)
    return tuple(part for part, pattern, selected in changes)

