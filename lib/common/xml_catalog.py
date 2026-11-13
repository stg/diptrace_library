"""Own XML library catalogs and exact sharing of generated public records."""
from .xml import set_attribute, syntax_role
from .xml_output import field
from .model import Element, Value


def _text(node):
    if node is None or not node.arguments:
        return ''
    if len(node.arguments) != 1 or node.arguments[0].kind != 'string':
        raise ValueError('category labels require plain text')
    return node.values[0]


def _include_label(parent, name, label, *, before=None):
    """Complete resolved text in the field order used by named projections."""
    node = parent.child(name)
    if label and not _text(node):
        if node is None:
            node = field(parent, name, label)
        else:
            node.set_values(label)
    if node is not None and before is not None:
        children = parent.children()
        index = children.index(before)
        if children.index(node) > index:
            node.move_to(parent, index)


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
            _include_label(category, 'Name', entry['label'], before=category.child('CategoryTypes'))
        for row in category.select('CategoryTypes/CategoryType'):
            kind = row.child('Type')
            child = getattr(entry['children'], operation)(_text(kind), _index(kind))
            if child is None:
                continue
            if include:
                set_attribute(kind, 'Index', child['index'])
                _include_label(row, 'Type', child['label'])
            subtype = row.child('SubType')
            if subtype is not None:
                sub = getattr(child['children'], operation)(_text(subtype), _index(subtype))
                if include and sub is not None:
                    set_attribute(subtype, 'Index', sub['index'])
                    _include_label(row, 'SubType', sub['label'])

    def reserve(self, references):
        """Reserve unresolved keys before allocating new named classifications."""
        for category in references:
            if category is not None:
                self._visit(category, include=False)

    def include(self, category):
        self.reserve((category,))
        self._visit(category, include=True)

    def include_plan(self, category):
        """Allocate classification keys in a detached destination plan."""
        from .xml_plan import XmlPlan
        element = category.element()
        self.include(element)
        return XmlPlan.from_element(element)

    def seed(self, categories):
        """Declare all current resources, including unnamed and unused entries."""
        if categories is not None:
            if categories.arguments or any(row.kind != 'Category' for row in categories.children()):
                raise ValueError('catalog resources require a Category collection')
            if self.element.children() or self._root.named:
                raise ValueError('declare catalog resources before reference allocation')
            self._root.seed(categories.children('Category'))


def record_key(node, *, omit_attribute=None):
    """Exact semantic key for generated library records, excluding a root key.

    These schema records have scalar text and ordinary child elements; arbitrary
    XML mixed content continues through the raw XML adapter instead.
    """
    def values(item):
        return tuple((value.kind, value.value, value.unit) for value in item.arguments)
    attributes, children = [], []
    for child in node._child_sequence():
        if syntax_role(child) == 'attribute':
            if child.kind != omit_attribute:
                attributes.append((child.kind, values(child)))
        else:
            children.append(record_key(child))
    return node.kind, values(node), tuple(sorted(attributes)), tuple(children)


class StyleTable:
    """Share only records with equal public data; never infer weak equivalence."""
    def __init__(self, container, record, attribute, prefix):
        self.element = Element(container)
        self.record, self.attribute, self.prefix = record, attribute, prefix
        self._keys = {}
        self._names = set()

    def include(self, node, *, exclude=(), name=None):
        """Share equal data, or declare an independently named resource.

        An explicit name keeps that resource separate even when its content
        equals another style. Generated names avoid all declared names.
        """
        if node.kind != self.record or node.parent is not None:
            raise ValueError('style tables require a detached record of the declared kind')
        key = record_key(node, omit_attribute=self.attribute)
        return self._include(key, lambda: node, exclude=exclude, name=name)

    def include_plan(self, plan, *, exclude=(), name=None):
        """Materialize a complete style only when it introduces a resource."""
        if plan.kind != self.record:
            raise ValueError('style tables require a plan of the declared kind')
        return self._include(plan.key(omit_attribute=self.attribute), plan.element,
                             exclude=exclude, name=name)

    def _include(self, key, build, *, exclude, name):
        name = self._select_name(key, exclude=exclude, name=name)
        if name not in self._names:
            node = build()
            set_attribute(node, self.attribute, name)
            self.element.append(node)
            self._remember(key, name)
        return name

    def _select_name(self, key, *, exclude, name):
        candidates = self._keys.get(key, ())
        if name is not None:
            if not isinstance(name, str) or name in self._names:
                raise ValueError('declared style names must be distinct text values')
        else:
            name = next((name for name in candidates if name not in exclude), None)
        if name is None:
            ordinal = len(self._names)
            name = self.prefix + str(ordinal)
            while name in self._names:
                ordinal += 1
                name = self.prefix + str(ordinal)
        return name

    def _remember(self, key, name):
        self._keys.setdefault(key, []).append(name)
        self._names.add(name)


class StylePlans:
    """Allocate local style keys before any editable records are needed."""
    def __init__(self, container, record, attribute, prefix):
        self._table = StyleTable(container, record, attribute, prefix)
        self.entries = []
        self._element = None
        self._plan = None

    def include_plan(self, plan, *, exclude=(), name=None):
        if plan.kind != self._table.record:
            raise ValueError('style plans require the declared record kind')
        key = plan.key(omit_attribute=self._table.attribute)
        name = self._table._select_name(key, exclude=exclude, name=name)
        if name not in self._table._names:
            self.entries.append((name, plan))
            self._table._remember(key, name)
            self._element = None
            self._plan = None
        return name

    @property
    def _names(self):
        return self._table._names

    @property
    def plan(self):
        from .xml_plan import XmlPlan
        if self._plan is None:
            self._plan = XmlPlan(self._table.element.kind, children=tuple(
                plan.with_attribute(self._table.attribute, name)
                for name, plan in self.entries))
        return self._plan

    @property
    def element(self):
        if self._element is None:
            self._element = self.plan.element()
        return self._element
