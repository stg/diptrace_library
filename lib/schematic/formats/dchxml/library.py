"""Assemble public XML libraries with our own exact data-sharing policy."""
from dataclasses import dataclass, field, replace

from ...model.cache import (symbol_definition)
from .syntax import (set_attribute)
from ....common.xml_catalog import CategoryCatalog, StylePlans
from ....common.xml_plan import XmlBuilder, XmlPlan
from ....common.xml_pad_output import plan_pad_style
from ....common.xml_library_output import project_subfolders, report_slot_omissions
from .patterns import plan_pattern
from .symbols import plan_symbol
from ....common.model import (Element)
from ...model.refs import (_integer)
from ...model.pad_keys import (public_pad_keys)
from ...model.traversal import (footprint_name)


@dataclass(frozen=True)
class XmlLibrary:
    plan: XmlPlan
    component_styles: dict
    cache_count: int
    _element: Element | None = field(default=None, init=False, compare=False, repr=False)

    @property
    def element(self):
        if self._element is None:
            object.__setattr__(self, '_element', self.plan.element())
        return self._element


class _Builder:
    def __init__(self, *, units, version):
        from ..dch.versions import (xml_application_version)
        self.units, self.version = units, version
        self.header_version = xml_application_version(version)
        self.components = XmlBuilder('Components')
        self.component_categories = CategoryCatalog()
        self.pattern_categories = CategoryCatalog(key='Number')
        self.pad_styles = StylePlans('PadStyles', 'PadStyle', 'Name', 'PadT')
        self.patterns = StylePlans('Patterns', 'Pattern', 'PatternStyle', 'PatType')
        self.symbols = {}
        self.associations = {}
        self.standard_changes = set()

    def header(self, kind):
        result = XmlBuilder('Library')
        for name, value in (('Type', 'DipTrace-'+kind+'Library'), ('Version', self.header_version), ('Units', self.units.units)):
            set_attribute(result, name, value)
        return result

    def footprint(self, pattern, *, pad_keys=None):
        if pattern is None:
            return None
        footprint_name(pattern)
        default_record = plan_pad_style(pattern, name='', units=self.units)
        default_key = default_record.key(omit_attribute='Name')
        default = self.pad_styles.include_plan(default_record)
        pads = {}
        for index, pad in enumerate(pattern.select('Pads/Pad')[1:-1], 1):
            record = plan_pad_style(pad, name='', units=self.units)
            standard = bool(pad.scalar('Standard'))
            comparable = record
            if standard:
                # The placed pad has its own Side attribute. Selecting the
                # default style need not replace that independent placement.
                comparable = record.with_attribute('Side', default_record.attribute('Side'))
            if standard and comparable.key(omit_attribute='Name') == default_key:
                pads[index] = default
            else:
                # Equal attributes do not make these relationships equivalent:
                # selecting the default style reconstructs Standard=True.
                pads[index] = self.pad_styles.include_plan(record, exclude=() if self.version >= 52 else (default,))
            if self.version < 52 and (pads[index] == default) != standard:
                self.standard_changes.add(pad)
        result = plan_pattern(pattern, style='', default_pad_style=default, pad_styles=pads,
                                 units=self.units, pad_ids=self.version >= 48,
                                 pad_keys=public_pad_keys(pattern) if pad_keys is None else pad_keys, version=self.version)
        category = result.child('Category')
        if category is not None:
            result = result.with_child(category, self.pattern_categories.include_plan(category))
        return self.patterns.include_plan(result)

    def symbol(self, part, pattern):
        keys = public_pad_keys(pattern, part) if pattern is not None and part.scalar('PartType') == 0 else None
        style = self.footprint(pattern, pad_keys=keys)
        result = plan_symbol(part, units=self.units, pattern=pattern, pattern_style=style, pad_keys=keys, version=self.version)
        category = result.child('Category')
        if category is not None:
            result = result.with_child(category, self.component_categories.include_plan(category))
        return result

    def component(self, definitions):
        name = 'CompType'+str(len(self.components.children))
        result = self.components.add('Component')
        set_attribute(result, 'ComponentStyle', name)
        for index, definition in enumerate(definitions):
            result.append(definition)
            self.symbols.setdefault(definition.key(), (name, index))
        return name

    def cached(self, schematic):
        count = _integer(schematic.scalar('DesignCache_Count'))
        links = schematic.select('DesignCache_Links/Link')
        slots = schematic.select('CacheLib/Slots/Slot')
        if count is None or count < -1 or count+1 > len(links):
            raise ValueError('design-cache count must identify its active link prefix')
        included = set()
        for link in links[:count+1]:
            position = _integer(link.values[0]) if link.arguments else None
            if position is None or not 0 <= position < len(slots):
                raise ValueError('active design-cache link does not identify an available slot')
            definitions = [self.symbol(item.one('Part'), item.one('Pattern')) for item in slots[position].children('Definition')]
            # Cached slots remain distinct even when equal. Their first-use
            # ordering and variant arrays carry cache identity, not just shape.
            self.component(definitions)
            included.add(position)
        # The active cache prefix is an application selection, not ownership of
        # every definition. Keep additional stored definitions in public output
        # as independent styles; their default values must not disappear merely
        # because only an overridden instance is currently placed.
        for position, slot in enumerate(slots):
            if position not in included:
                self.component([self.symbol(item.one('Part'), item.one('Pattern'))
                                for item in slot.children('Definition')])
        return count+1

    def build(self, schematic):
        cache = schematic.one('CacheLib')
        from ...model.traversal import (footprints, symbols)
        from ....common.xml_library_output import project_category
        self.component_categories.seed(cache.child('Categories'))
        self.pattern_categories.seed(cache.child('PatternCategories'))
        self.component_categories.reserve(project_category(part) for part in symbols(schematic))
        self.pattern_categories.reserve(project_category(pattern) for pattern in footprints(schematic) if pattern is not None)
        for style in cache.select('PadStyles/PadStyle'):
            self.pad_styles.include_plan(plan_pad_style(style, name='', units=self.units))
        for pattern in cache.select('Patterns/Pattern'):
            self.footprint(pattern)
        cache_count = self.cached(schematic)
        for part in schematic.select('Components/Part'):
            if not part.scalar('Enabled'):
                continue
            definition = self.symbol(symbol_definition(part), part.one('Pattern'))
            key = definition.key()
            if key not in self.symbols:
                self.component([definition])
            self.associations[part] = self.symbols[key]
        result = self.header('Component')
        if self.component_categories.element.children():
            result.append(XmlPlan.from_element(self.component_categories.element))
        if (folders := project_subfolders(cache)) is not None:
            result.append(XmlPlan.from_element(folders))
        patterns = self.header('Pattern')
        if self.pattern_categories.element.children():
            patterns.append(XmlPlan.from_element(self.pattern_categories.element))
        patterns.append(self.pad_styles.plan)
        patterns.append(self.patterns.plan)
        result.append(patterns)
        # Definitions precede their users, including in single-pass readers.
        result.append(self.components)
        plan = result.freeze()
        if self.version >= 47:
            plan = _current_geometry_names(plan)
        return XmlLibrary(plan, self.associations, cache_count)


def _current_geometry_names(plan, parent=''):
    """Use the selected library dialect without changing shared definitions."""
    kind = ('Point' if plan.kind == 'Item' and parent == 'Points' else
            'TextLine' if plan.kind == 'Item' and parent == 'TextLines' else
            'TextLines' if plan.kind == 'Lines' and parent == 'Shape' else plan.kind)
    children = tuple(_current_geometry_names(child, kind) for child in plan.children)
    if kind == plan.kind and all(new is old for new, old in zip(children, plan.children)):
        return plan
    return replace(plan, kind=kind, children=children)


def project_library(schematic, *, units, version=46, report=None):
    """Build cached and placed public definitions without modifying the source.

    Sharing uses complete projected records, not names or format cache heuristics.
    """
    from ...model.traversal import (footprints, cached_definitions)
    from ....common.conversion import (warn)
    from ..compatibility import (report_omitted_records)
    report_slot_omissions(schematic.select('CacheLib/Slots/Slot'), destination='dchxml', report=report)
    inactive, states = [], []
    for definition in cached_definitions(schematic):
        part = definition.one('Part')
        if part.scalar('Enabled') in (False, 'N'):
            states.append(part.one('Enabled'))
        inactive.extend(node for path in ('Pins/Pin', 'Shapes/Shape') for node in part.select(path)
                        if node.scalar('Enabled') in (False, 'N'))
    for pattern in footprints(schematic):
        inactive.extend(node for node in pattern.select('Dimensions/Dimension')
                        if node.scalar('Enabled') in (False, 'N'))
    if inactive:
        report_omitted_records(inactive, destination='dchxml', report=report, rule='inactive-library-records')
    if states:
        warn(report, 'inactive-library-state', 'dchxml', 'cached symbol Enabled state is not represented by XML', states,
             recoverability='definition content is exported; its activation state remains in the authoring model')
    if version < 48:
        shapes = [shape for pattern in footprints(schematic) for shape in pattern.select('Shapes/Shape')
                  if shape.scalar('PadId', -1) >= 0]
        if shapes:
            warn(report, 'shape-pad-id', 'dchxml', 'footprint Shape.PadId is omitted by output schema below 48', shapes)
    builder = _Builder(units=units, version=version)
    result = builder.build(schematic)
    if builder.standard_changes:
        warn(report, 'pad-standard-style', 'dchxml',
             'XML reconstructs Standard from shared default and individual pad styles',
             sorted(builder.standard_changes, key=lambda pad: pad.path),
             recoverability='explicit pad geometry is retained; the original choice remains in the authoring model')
    return result
