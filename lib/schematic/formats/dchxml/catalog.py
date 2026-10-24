"""Own XML library catalogs and exact sharing of generated public records."""
from .syntax import (set_attribute)
from .settings import (field)
from ....common.model import (Element, Value)


def _text(node):
    if node is None or not node.arguments:
        return ''
    if len(node.arguments) != 1 or node.arguments[0].kind != 'string':
        raise ValueError('category labels require plain text')
    return node.values[0]


def _index(node):
    field = node.child('Index') if node is not None else None
    if field is None:
        return -1
    if len(field.arguments) == 1:
        value = field.arguments[0]
        if value.kind == 'number' and not value.unit:
            try:
                if int(value.value) == value.value:
                    return value.value
            except (ValueError, OverflowError):
                pass
    raise ValueError('category indices require integer values without units')


class _CatalogLevel:
    """A scoped set of resources; labels and declared keys both resolve entries."""
    def __init__(self, container, record, key, *, parent=None, nested=()):
        self.element = Element(container)
        self.record, self.key, self.parent, self.nested = record, key, parent, nested
        self.named, self.declared, self.used, self.reserved = {}, {}, set(), set()

    def entry(self, label, source_key, *, create=False):
        known = self.declared.get(source_key)
        if known is not None and (not label or known['label'] == label):
            return known
        if not label:
            return None
        if label not in self.named and create:
            node = Element(self.record)
            field(node, 'Name', label)
            self.named[label] = self._entry(label, node)
        return self.named.get(label)

    def _entry(self, label, element, index=None):
        children = (_CatalogLevel(*self.nested[0], self.key, parent=element,
                                  nested=self.nested[1:]) if self.nested else None)
        return dict(label=label, element=element, index=index, children=children)

    def reserve(self, label, source_key):
        entry = self.entry(label, source_key, create=True)
        if entry is None and source_key >= 0:
            if source_key in self.used:
                raise ValueError('reserve unresolved category keys before catalog allocation')
            self.reserved.add(source_key)
        return entry

    def include(self, label, source_key):
        entry = self.entry(label, source_key, create=True)
        if entry is not None and entry['index'] is None:
            index = 0
            while index in self.used or index in self.reserved:
                index += 1
            self._attach(entry, index)
        return entry

    def _attach(self, entry, index):
        set_attribute(entry['element'], self.key, index)
        self.element.append(entry['element'])
        if self.parent is not None and self.element.parent is None:
            self.parent.append(self.element)
        entry['index'] = index
        self.used.add(index)

    def seed(self, rows):
        for source in rows:
            if (len(source.arguments) != 2 or source.arguments[0].kind != 'string'
                    or source.arguments[0].unit or source.arguments[1].kind != 'number'
                    or source.arguments[1].unit):
                raise ValueError('catalog resources require a text label and integer key')
            label, index = source.values
            try:
                valid = int(index) == index
            except (ValueError, OverflowError):
                valid = False
            if not valid:
                raise ValueError('catalog resources require a text label and integer key')
            if index in self.used:
                raise ValueError('duplicate catalog resource key')
            node = Element(self.record)
            field(node, 'Name', label)
            entry = self._entry(label, node)
            self._attach(entry, index)
            self.declared[index] = entry
            if label:
                self.named.setdefault(label, entry)
            parameters = source.schema.parameters if source.schema is not None else ()
            children = [child for child in source.children() if child.kind not in parameters]
            if entry['children'] is not None:
                model_kind = 'Type' if self.record == 'Category' else 'Subtype'
                if any(child.kind != model_kind for child in children):
                    raise ValueError('unsupported catalog resource child')
                entry['children'].seed(children)
            elif children:
                raise ValueError('subtype resources cannot contain child records')


class CategoryCatalog:
    """Project owned resources and classification references in their local scopes.

    Declared catalog keys identify their resources, including unnamed entries.
    New named classifications receive free keys around declared/missing targets.
    All allocation and reference changes are confined to the XML export view.
    """
    def __init__(self, *, key='Index'):
        if key not in ('Index', 'Number'):
            raise ValueError('XML category catalog key must be Index or Number')
        self.key = key
        self._root = _CatalogLevel('Categories', 'Category', key,
                                  nested=(('Types', 'Type'), ('SubTypes', 'SubType')))
        self.element = self._root.element

    def _visit(self, category, *, include):
        operation = 'include' if include else 'reserve'
        entry = getattr(self._root, operation)(_text(category.child('Name')), _index(category))
        if entry is None:
            return
        if include:
            set_attribute(category, 'Index', entry['index'])
        for row in category.select('CategoryTypes/CategoryType'):
            kind = row.child('Type')
            child = getattr(entry['children'], operation)(_text(kind), _index(kind))
            if child is None:
                continue
            if include:
                set_attribute(kind, 'Index', child['index'])
            subtype = row.child('SubType')
            if subtype is not None:
                sub = getattr(child['children'], operation)(_text(subtype), _index(subtype))
                if include and sub is not None:
                    set_attribute(subtype, 'Index', sub['index'])

    def reserve(self, references):
        """Reserve unresolved keys before allocating new named classifications."""
        for category in references:
            if category is not None:
                self._visit(category, include=False)

    def include(self, category):
        self.reserve((category,))
        self._visit(category, include=True)

    def seed(self, categories):
        """Declare all current resources, including unnamed and unused entries."""
        if categories is not None:
            if categories.arguments or any(row.kind != 'Category' for row in categories.children()):
                raise ValueError('catalog resources require a Category collection')
            if self.element.children() or self._root.named:
                raise ValueError('declare catalog resources before reference allocation')
            self._root.seed(categories.children('Category'))


def unrepresented_pattern_categories(schematic):
    """Catalog labels which embedded DCH footprint records cannot carry."""
    cache = schematic.child('CacheLib')
    categories = cache.child('PatternCategories') if cache is not None else None
    if categories is None:
        return set()
    facts = set()
    for category in categories.children('Category'):
        name = category.values[0]
        facts.add((name, '', ''))
        for kind in category.children('Type'):
            label = kind.values[0]
            facts.add((name, label, ''))
            for subtype in kind.children('Subtype'):
                facts.add((name, label, subtype.values[0]))
    from ...model.traversal import (footprints)
    covered = set()
    for pattern in footprints(schematic):
        name = pattern.scalar('Pattern_CategoryName', '')
        if name:
            covered.add((name, '', ''))
        for row in pattern.select('Pattern_CategoryTypes/CategoryType'):
            kind, subtype = row.values[:2]
            if kind:
                covered.add((name, kind, ''))
            if subtype:
                covered.add((name, kind, subtype))
    return facts-covered


def record_key(node, *, omit_attribute=None):
    """Exact semantic key for generated library records, excluding a root key.

    These schema records have scalar text and ordinary child elements; arbitrary
    XML mixed content continues through the raw XML adapter instead.
    """
    def values(item):
        return tuple((value.kind, value.value, value.unit) for value in item.arguments)
    attributes = tuple(sorted((child.kind, values(child)) for child in node.children()
                             if child.annotations.get('xml_role') == 'attribute' and child.kind != omit_attribute))
    children = tuple(record_key(child) for child in node.children() if child.annotations.get('xml_role') != 'attribute')
    return node.kind, values(node), attributes, children


class StyleTable:
    """Share only records with equal public data; never infer weak equivalence."""
    def __init__(self, container, record, attribute, prefix):
        self.element = Element(container)
        self.record, self.attribute, self.prefix = record, attribute, prefix
        self._keys = {}

    def include(self, node, *, exclude=()):
        """Share equal data unless a key must remain a distinct relationship."""
        if node.kind != self.record or node.parent is not None:
            raise ValueError('style tables require a detached record of the declared kind')
        key = record_key(node, omit_attribute=self.attribute)
        candidates = self._keys.get(key, ())
        name = next((name for name in candidates if name not in exclude), None)
        if name is None:
            name = self.prefix + str(len(self.element.children()))
            set_attribute(node, self.attribute, name)
            self.element.append(node)
            self._keys.setdefault(key, []).append(name)
        return name
