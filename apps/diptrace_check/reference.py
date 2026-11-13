"""User-supplied export references, without normalizing away their syntax."""
import gc
from dataclasses import dataclass, replace
from importlib import import_module
from pathlib import Path

from lib import Element, format_capabilities, input_identity, parse
from lib.common import asc, xml
from apps.common.cli import PROCESSING_ERRORS
from .comparison import compare, compare_ordered, snapshot


def source_document(data, *, format, family, retain_source=False):
    """Retain unknown fields and ordered values, without unused spelling spans."""
    if format == 'asc':
        return asc.loads_bytes(data, retain_source=retain_source)
    dialect = import_module(f'lib.{family}.formats.{format}.syntax').DIALECT
    return xml.loads(data, dialect=replace(dialect, representation='xml'), retain_source=retain_source)


def _node_facts(node, path):
    if xml.syntax_role(node) in ('comment', 'instruction'):
        return
    yield path, ('record', '', node.kind)
    content = []
    argument = 0
    for item in node.items:
        if isinstance(item, Element):
            if xml.syntax_role(item) not in ('attribute', 'comment', 'instruction'):
                content.append(('element', item.kind))
        else:
            content.append(('value', argument))
            argument += 1
    yield path+'/@content', ('order', '', tuple(content))
    for index, value in enumerate(node.arguments):
        kind = 'serialized-number' if value.kind == 'number' else value.kind
        unit = value.unit or ('serialized units' if value.kind == 'number' else '')
        yield path+f'/@{index}', (kind, unit, value.value)


def source_snapshot(document):
    """Ignore spelling/indentation and attribute order; retain ordered content."""
    return dict(fact for node in document.root.walk(include_self=True)
                for fact in _node_facts(node, node.path))


def source_rows(document):
    """Yield the same lexical facts in path order, retaining only local rows.

    Count every sibling when deriving paths, including XML metadata nodes.
    Sorting each node's immediate entries also orders two-digit ordinals and
    argument indices correctly, without building a complete fact dictionary.
    """
    def visit(node, path):
        entries = [(key, False, fact) for key, fact in _node_facts(node, path)]
        counts = {}
        for child in node.items:
            if isinstance(child, Element):
                counts[child.kind] = ordinal = counts.get(child.kind, 0)+1
                child_path = path.rstrip('/')+'/'+child.kind+f'[{ordinal}]'
                entries.append((child_path, True, child))
        entries.sort(key=lambda entry: entry[0])
        for key, subtree, value in entries:
            if subtree:
                yield from visit(value, key)
            else:
                yield key, value

    yield from visit(document.root, '/')


@dataclass
class Reference:
    path: Path
    format: str
    version: int | str
    declaration: int | str
    candidates: tuple
    units: str | None
    data: bytes

    @classmethod
    def load(cls, path, *, family, version=None):
        path = Path(path)
        data = path.read_bytes()
        identity = input_identity(data)
        if identity.family != family:
            raise ValueError(f'{path}: reference family {identity.family!r} differs from {family!r}')
        if identity.format != 'asc' and not (identity.format or '').endswith('xml'):
            raise ValueError(f'{path}: references must be ASC or XML exports')
        capabilities = format_capabilities(identity.format, family=family)
        candidates = capabilities.output_versions_for(identity.version)
        selected = max(candidates) if version is None else capabilities.output_version(version)
        if selected not in candidates:
            raise ValueError(f'{path}: output schema {selected} does not match '
                             f'reference version {identity.version!r}')
        raw = source_document(data, format=identity.format, family=family)
        units = raw.root.one('Units').values if identity.format == 'asc' else (raw.metadata.get('units'),)
        if len(units) != 1 or not isinstance(units[0], str):
            raise ValueError(f'{path}: reference must declare its display units')
        result = cls(path, identity.format, selected, identity.version, candidates, units[0], data)
        # Only bytes and header choices survive loading. Release the temporary
        # lexical tree before the caller prepares another complete design.
        del raw, units
        gc.collect()
        return result

    def context(self, family):
        # Match the reference's declared display units, without borrowing its
        # design data or substituting it for the supplied source model.
        package = import_module('lib.'+family)
        return package.ExportContext(units=self.units)

    def check(self, generated, *, actual, family, tolerance, source_tolerance, report):
        expected = source_document(self.data, format=self.format, family=family)
        output = source_document(generated, format=self.format, family=family)
        structure = compare_ordered(source_rows(expected), source_rows(output), tolerance=source_tolerance)
        del expected, output
        gc.collect()
        model, error = None, None
        try:
            reference = parse(self.data, report=report, label=str(self.path))
            reference.references.validate()
            model = compare(snapshot(reference), actual, tolerance=tolerance)
        except PROCESSING_ERRORS as failure:
            # Unsupported reference content is itself useful evidence. Keep
            # its direct syntax comparison even when model import cannot finish.
            error = str(failure)
        review = error is not None or model['needs_review'] or structure['needs_review']
        rounding = bool((model and model['counts']) or structure['counts'])
        return dict(path=str(self.path), format=self.format, version=self.version,
                    reference_version=self.declaration, matching_versions=self.candidates,
                    model=model, model_error=error, serialized=structure,
                    status='review' if review else 'rounding' if rounding else 'clean')
