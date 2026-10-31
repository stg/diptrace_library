"""Strict preparation of one supplied PCB XML document for model import.

Parsing does not discover or read companion files."""
from dataclasses import dataclass

from ....common.model import Element
from ....common.units import XmlUnits
from ....common.xml_records import XmlRecord
from ..assembly.graphic_inputs import GraphicInputs
from ..errors import PcbError
from ..import_context import resolve_import_context
from ..placement_frames import resolve_fiducials
from .syntax import loads
from .library import read_library
from .document_settings import read_document_settings
from .electrical import read_electrical
from .versions import XmlVersion


@dataclass(frozen=True)
class PcbXmlInput:
    root: Element
    version: XmlVersion
    upgrades: GraphicInputs

    @property
    def board(self):
        return self.root.one('Board')

    def prepare(self, context):
        from ..assembly.object_kinds import normalize_objects
        from ..assembly.graphic_colors import normalize_graphic_colors
        normalize_objects(self.board)
        normalize_graphic_colors(self, context)


def prepare(data, *, source=None, context=None):
    context = resolve_import_context(context)
    syntax = loads(data, source=source)
    record = XmlRecord(syntax.one('/Source'))
    if record.text('Type') != 'DipTrace-PCB':
        raise PcbError('PCB XML requires a DipTrace-PCB source')
    version_text = record.text('Version', '')
    version = XmlVersion.parse(version_text)
    units = XmlUnits(record.text('Units', 'mm'))
    board_source = record.take('Board', required=True)
    root = Element('')
    root.add('Units', units.units)
    board = root.add('Board')
    placed_patterns = {item.scalar('PatternStyle') for item in board_source.node.select('Components/Component')
                       if item.child('PatternStyle') is not None}
    library = read_library(record.take('Library'), board, units=units, placed_patterns=placed_patterns)
    read_document_settings(board_source, root, board, units=units, application_version=version_text)
    common_fiducials = resolve_fiducials(board, context.show_component_fiducials)
    upgrades = read_electrical(board_source, board, patterns=library.patterns, units=units,
                              version=version, common_fiducials=common_fiducials)
    board_source.finish()
    record.finish()
    return PcbXmlInput(root, version, upgrades)
