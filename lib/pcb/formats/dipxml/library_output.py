"""Generate PCB XML component libraries from the current owned definitions."""
from dataclasses import dataclass, field as dataclass_field, replace

from ....common.conversion import info
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_catalog import CategoryCatalog, StylePlans
from ....common.xml_plan import XmlBuilder, XmlPlan
from ....common.xml_library_output import project_category, project_subfolders, report_slot_omissions
from ....common.xml_output import field
from ....common.xml_pad_output import plan_pad_style
from ...model import library_records, static_via
from ...model.definitions import PATTERN
from ...model.cache_links import validate_prefix
from ..errors import PcbError
from ..output_validation import check_tree
from .pattern_output import project_pattern, _project_validated_pattern
from .symbol_output import _project_validated_symbol
from .versions import XmlVersion
from .output_revision import adapt_library


@dataclass(frozen=True)
class PhysicalStyle:
    name: str | None
    pad_keys: dict
    connections: tuple
    shape_keys: dict = dataclass_field(default_factory=dict)
    hole_keys: dict = dataclass_field(default_factory=dict)


@dataclass(frozen=True)
class LibraryProjection:
    plan: XmlPlan
    component_styles: dict
    physical_styles: dict
    _element: Element | None = dataclass_field(default=None, init=False, compare=False, repr=False)

    @property
    def element(self):
        if self._element is None:
            object.__setattr__(self, '_element', self.plan.element())
        return self._element


class _Builder:
    def __init__(self, board, *, units, physical, profile, report):
        self.board, self.units, self.report = board, units, report
        self.profile = profile
        self.cache = board.child('CacheLib')
        cached = library_records.patterns(board)
        self._cached_patterns = frozenset(cached)
        self.physical = tuple(dict.fromkeys((*cached, *physical)))
        self.parts = tuple(board.select('CacheLib/Slots/Slot/Definition/Part'))
        self.component_categories = CategoryCatalog()
        self.pattern_categories = CategoryCatalog(key='Number')
        self.pads = StylePlans('PadStyles', 'PadStyle', 'Name', 'Pad')
        self.patterns = StylePlans('Patterns', 'Pattern', 'PatternStyle', 'Pattern')
        self.components = XmlBuilder('Components')
        self.component_styles, self.physical_styles = {}, {}
        self.independent_pads, self.independent_patterns = set(), set()
        self.placement_patterns = {}

    def header(self, family):
        result = XmlBuilder('Library')
        for name, value in (('Type', 'DipTrace-'+family+'Library'),
                            ('Version', self.profile.application_text), ('Units', self.units.units)):
            set_attribute(result, name, value)
        return result

    def pattern(self, source, *, independent=False):
        project = _project_validated_pattern if source in self._cached_patterns else project_pattern
        placed = source.parent is not None and source.parent.kind == 'Component'
        if placed and source['Type'] == 16 and source.parent['Via'] is not None:
            check_tree(source, PATTERN, destination='DIPXML')
            project = _project_validated_pattern
            if static_via.matches(source, source.parent['Via']):
                pads = source.select('Pads/Pad')
                self.physical_styles[source] = PhysicalStyle(None, {pads[0]: 1}, ())
                return
        projected = project(source, style='', units=self.units,
                                    explicit_pad_style=self.profile.current_fields,
                                    physical_font_width=self.profile.physical_font_width, report=self.report)
        plan = projected.plan
        default_pad = plan.child('DefPad')
        default = default_pad.attribute('Style')
        remapped = {}
        for local, style_plan in projected.pad_styles.entries:
            # Older XML uses style identity for inheritance. Avoid merging a
            # separate local style with this pattern's default style.
            excluded = self.independent_pads
            if not self.profile.current_fields and local != default:
                excluded = excluded | {remapped[default]}
            remapped[local] = self.pads.include_plan(style_plan, exclude=excluded)
        plan = plan.with_child(default_pad, default_pad.with_attribute('Style', remapped[default]))
        pads = plan.child('Pads')
        plan = plan.with_child(pads, replace(pads, children=tuple(
            pad.with_attribute('Style', remapped[pad.attribute('Style')]) for pad in pads.children)))
        if (category := plan.child('Category')) is not None:
            plan = plan.with_child(category, self.pattern_categories.include_plan(category))
        excluded = (self.patterns._names
                    if independent else self.independent_patterns)
        key = _placement_key(plan)
        name = self.placement_patterns.get(key) if placed else None
        if name is None:
            name = self.patterns.include_plan(plan, exclude=excluded)
        self.placement_patterns.setdefault(key, name)
        if independent:
            self.independent_patterns.add(name)
            if projected.connections:
                raise PcbError(f'{source.path}: independent internal pad pairs need a PCB XML mapping')
        self.physical_styles[source] = PhysicalStyle(name, projected.pad_keys, projected.connections,
                                                      projected.shape_keys, projected.hole_keys)

    def component(self, slot):
        name = 'Component'+str(len(self.components.children))
        result = self.components.add('Component')
        set_attribute(result, 'ComponentStyle', name)
        self.component_styles[slot] = name
        definitions = slot.children('Definition')
        primary = definitions[0].child('Pattern') if definitions else None
        keys = self.physical_styles[primary].pad_keys if primary is not None else {}
        for definition in definitions:
            part = definition.child('Part')
            if part is None:
                raise PcbError(f'{definition.path}: cached physical definition needs an owning XML symbol')
            physical = definition.child('Pattern')
            projected = self.physical_styles[physical] if physical is not None else None
            # build() has freshly audited this slot's entire cache subtree.
            symbol = _project_validated_symbol(part, units=self.units, pad_keys=keys,
                                    pattern_style=projected.name if projected else None,
                                    connections=projected.connections if projected else (),
                                    physical_font_width=self.profile.physical_font_width, report=self.report,
                                    _factory=XmlBuilder)
            path = symbol.add('LibPath')
            field(path, 'Path', slot['LibPath'])
            field(path, 'Var', slot.get('VariablePath', ''))
            plan = symbol.freeze()
            if (category := plan.child('Category')) is not None:
                plan = plan.with_child(category, self.component_categories.include_plan(category))
            result.append(plan)
        report_slot_omissions((slot,), destination='dipxml', report=self.report)

    def build(self):
        if self.cache is not None:
            check_tree(self.cache, library_records.CACHE, destination='DIPXML')
            self.component_categories.seed(self.cache.child('Categories'))
            self.pattern_categories.seed(self.cache.child('PatternCategories'))
            for style in self.cache.select('PadStyles/PadStyle'):
                name = self.pads.include_plan(plan_pad_style(style, name=style['Name'], units=self.units), name=style['Name'])
                self.independent_pads.add(name)
        self.component_categories.reserve(project_category(part) for part in self.parts)
        self.pattern_categories.reserve(project_category(pattern) for pattern in self.physical)
        independent = set(self.board.select('CacheLib/Patterns/Pattern'))
        # Declare independent resources first, then prevent users from absorbing
        # them. Equal content does not erase independent library definitions.
        for source in self.physical:
            if source in independent:
                self.pattern(source, independent=True)
        for source in self.physical:
            if source not in independent:
                self.pattern(source)
        slots = tuple(self.board.select('CacheLib/Slots/Slot'))
        for slot in slots:
            self.component(slot)
        links = self.board.select('DesignCache_Links/Link')
        count = self.board.get('DesignCache_Count', -1)+1
        if count != len(slots) or tuple(link['SlotIndex'] for link in links) != tuple(range(len(slots))):
            info(self.report, 'library-cache-selection', 'dipxml',
                 'XML rebuilds the active library selection from its component definitions', (self.board,),
                 recoverability='all owned definitions remain; selection order and spare capacity are regenerated')
        result = self.header('Component')
        if self.component_categories.element.children():
            result.append(XmlPlan.from_element(self.component_categories.element))
        if (folders := project_subfolders(self.cache)) is not None:
            result.append(XmlPlan.from_element(folders))
        inner = self.header('Pattern')
        if self.pattern_categories.element.children():
            inner.append(XmlPlan.from_element(self.pattern_categories.element))
        inner.append(self.pads.plan)
        inner.append(self.patterns.plan)
        result.append(inner)
        result.append(self.components)
        plan = adapt_library(result.freeze(), version=self.profile, report=self.report)
        return LibraryProjection(plan, self.component_styles, self.physical_styles)


def _placement_key(pattern):
    """Placement metadata, type and fields override these template defaults.

    Physical geometry, public keys and pattern classification still match
    exactly. Template defaults remain in the independently owned definition;
    the component writer supplies all its current metadata and custom fields.
    """
    comparable = pattern.without_fields(('RefDes', 'Value', 'Manufacturer', 'Datasheet', 'AddFields', 'Type'))
    return comparable.key(omit_attribute='PatternStyle')


def project_library(board, *, units, physical=(), profile=None, report=None):
    """Plan cached definitions and optional placed physical styles together.

    The result is a detached XML library, not a whole PCB export. Electrical pin
    keys use each component's primary footprint; physical styles retain their
    own pad pairs and may also supply later placed-component output.
    """
    validate_prefix(board)
    return _Builder(board, units=units, physical=physical,
                    profile=XmlVersion.output() if profile is None else profile, report=report).build()
