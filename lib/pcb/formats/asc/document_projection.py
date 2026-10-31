"""Detached ASC sheet, panel and display sections, separate from routing rules.

The document writer merges these root fields and Settings children with other
sections. No source geometry or application preference is consulted or changed.
"""
from ....common.conversion import info, warn
from ....common.model import Element
from ...model import board_records as model, settings_records as settings
from ..errors import PcbError
from .document_settings import DISPLAY_ALIASES, SHEET_FIELDS
from .panel import GAPS, PANEL_FIELDS
from .projection import check, fields, flag, rows


def _sheet(board, output, display, report):
    sheet = board.child('SheetSettings')
    if sheet is None:
        return
    check(sheet, settings.SHEET)
    fields(sheet, output, exclude=('DisplayTitles', 'DisplaySheet'),
           names={current: saved for saved, current in SHEET_FIELDS.items()})
    for name in ('DisplayTitles', 'DisplaySheet'):
        if sheet.child(name) is not None:
            display.add(name, flag(sheet[name]))
    zones = sheet.child('BorderZones')
    if zones is not None:
        check(zones, settings.BORDER_ZONES)
        if zones.children():
            warn(report, 'sheet-border-zones', 'asc', 'ASC omits sheet border-zone settings', (zones,))
    titles = sheet.child('TitleBlocks')
    if titles is not None and titles.children():
        authored = any(block['Name'] or block['Width'] or block['Height'] or
                       any(block.one(name).children() for name in ('ColWidths', 'RowHeights', 'Cells', 'Contents'))
                       for block in titles.children())
        notice = warn if authored else info
        notice(report, 'sheet-title-blocks', 'asc', 'ASC omits sheet title-block definitions', (titles,),
               recoverability='title definitions remain in the source model; ASC carries only sheet dimensions and visibility')


def _panel(board, output, report):
    panel = board.child('Panel')
    if panel is None:
        return
    check(panel, model.PANEL)
    fields(panel, output, exclude=GAPS, names={current: saved for saved, current in PANEL_FIELDS.items()})
    for name in ('HorzTabsX', 'VertTabsY'):
        source = panel.child(name)
        if source is None:
            continue
        positions = output.add(next(saved for saved, current in PANEL_FIELDS.items() if current == name))
        for row in rows(source, model.TAB_POSITIONS, model.TAB_POSITION):
            positions.add('pt', row['Position'])
    gaps = [name for name in GAPS if panel.get(name) is not None]
    if gaps:
        notice = warn if any(panel[name] != 0 for name in gaps) else info
        notice(report, 'panel-gaps', 'asc', 'ASC omits separate panel edge gaps', (panel,),
               recoverability='panel tab positions and existing geometry remain; separate gap settings are omitted')


def _visibility(board, output):
    layers = board.select('NonSignals/NonSignal')
    supplied = [index for index, layer in enumerate(layers) if layer.get('Visible') is not None]
    if not supplied:
        return
    last = supplied[-1]
    if supplied != list(range(last+1)):
        raise PcbError('ASC custom-layer visibility requires choices for all preceding layers')
    target = output.add('LayerPanel_NonSignal')
    for layer in layers[:last+1]:
        target.add('pt', flag(layer['Visible']))


def project_document_settings(board, *, report=None):
    """Project display, sheet and tab data; routing and DRC use their own section."""
    output = Element('Board')
    display = output.add('Settings')
    source = board.child('Settings')
    if source is not None:
        check(source, settings.SETTINGS)
        fields(source, display, names={current: saved for saved, current in DISPLAY_ALIASES.items()})
        if (panel := source.child('LayerPanel')) is not None:
            check(panel, settings.LAYER_PANEL)
            fields(panel, output, names={name: 'LayerPanel_'+name for name in settings.LAYER_PANEL.fields})
    _visibility(board, output)
    _sheet(board, output, display, report)
    _panel(board, output, report)
    # The document's selected display unit owns these redundant switches.
    units = board._owner().root['Units']
    for name, unit in (('UnitsMM', 'mm'), ('UnitsMIL', 'mil'), ('UnitsINCH', 'inch')):
        display.add(name, flag(units == unit))
    return output
