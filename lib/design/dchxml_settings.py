"""Public XML sheet/settings views over the shared schematic model.

These are semantic projectors, not XML spelling emulation. Numbers retain
their available precision. Application choices absent from DCH are explicit.
"""
from .dchxml import set_attribute
from .dchxml_units import DchXmlUnits
from .model import Element, Value
from .markings import MarkingStyle


SHOW = ('Common', 'Show', 'Hide')
ALIGN = ('Common', 'Center', 'Top', 'Bottom', 'Left', 'Right', 'Corner', 'Auto', 'Position')


def enum_text(value, labels, *, negative=None):
    number = Value.of(value)
    if number.kind != 'number' or number.unit or number.value != int(number.value):
        raise ValueError('XML enum projection requires an integer')
    value = int(number.value)
    if value < 0 and negative is not None:
        return negative
    return labels[value] if 0 <= value < len(labels) else str(value)


def numeric(value):
    if isinstance(value, Value):
        if value.kind != 'number' or value.unit:
            raise ValueError('XML numeric projection requires an unqualified number')
        value = value.value
    result = Value.of(value)
    if result.kind != 'number' or result.unit:
        raise ValueError('XML numeric projection requires a number')
    return result


def field(parent, name, value):
    if (value.value if isinstance(value, Value) else value) == '':
        return parent.add(name)
    return parent.add(name, value)


def number(parent, name, value):
    return field(parent, name, numeric(value))


def length(parent, name, value, units):
    return number(parent, name, units.length(value))


def stroke_width(value, units):
    number_value = numeric(value)
    return number_value if number_value.value < 0 else numeric(units.length(number_value))


def _boolean(value):
    if value in (True, 'Y'):
        return True
    if value in (False, 'N'):
        return False
    raise ValueError(f'XML boolean projection requires a boolean: {value!r}')


def project_sheet_settings(schematic, *, units: DchXmlUnits, active_sheet):
    result = Element('SheetSettings')
    settings = schematic.one('Settings')
    field(result, 'DisplayTitles', _boolean(settings.scalar('DisplayTitles')))
    field(result, 'DisplaySheet', _boolean(settings.scalar('DisplaySheet')))
    pages = schematic.select('Pages/Page')
    if isinstance(active_sheet, bool) or not isinstance(active_sheet, int) or not 0 <= active_sheet < len(pages):
        raise ValueError('active_sheet must identify an existing page')
    field(result, 'ActiveSheet', active_sheet)
    sheets = result.add('Sheets')
    for index, page in enumerate(pages):
        sheet = sheets.add('Sheet')
        field(sheet, 'Id', index)
        field(sheet, 'Name', page.values[0])
        page_type = page.scalar('PageType')
        field(sheet, 'Type', enum_text(page_type, ('Normal', 'Hierarchy Block')))
        if page_type:
            field(sheet, 'BlockId', page.scalar('PageHiddenId'))
        x, y = units.point(page.one('PageXPos').arguments[0], page.one('PageyPos').arguments[0])
        number(sheet, 'XPos', x)
        number(sheet, 'YPos', y)
        number(sheet, 'Scale', page.one('PageScale').arguments[0])
        for public, own in (('SheetWidth', 'PageWidth'), ('SheetHeight', 'PageHeight'),
                            ('LeftMargin', 'FLeft'), ('TopMargin', 'FTop'),
                            ('RightMargin', 'FRight'), ('BottomMargin', 'FBottom')):
            length(sheet, public, page.one(own).arguments[0], units)
        zones = sheet.add('BorderZones')
        for public, own in (('Visible', 'Zones'), ('HorzZones', 'HorzZones'), ('VertZones', 'VertZones'),
                            ('Standard', 'ZoneStandard'), ('FontName', 'ZoneFontName'), ('FontSize', 'ZoneFontSize')):
            field(zones, public, page.scalar(own))
        field(zones, 'FontLineWidth', stroke_width(page.one('FontLineWidth').arguments[0], units))
        field(zones, 'Border', _boolean(page.scalar('ZoneBorder')))
        length(zones, 'HorzBorderSize', page.one('HorzZoneBorder').arguments[0], units)
        length(zones, 'VertBorderSize', page.one('VertZoneBorder').arguments[0], units)
        from .dchxml_tables import append_title_blocks
        append_title_blocks(page, sheet, units=units)
    return result


def _choice(settings, first, second, labels):
    left, right = _boolean(settings.scalar(first)), _boolean(settings.scalar(second))
    if left == right:
        raise ValueError(f'{first}/{second}: choose one XML mode explicitly')
    return labels[0 if left else 1]


def project_settings(schematic, *, units: DchXmlUnits, grid_snap, style: MarkingStyle,
                     use_part_font_color=None, project_dir=None):
    result = Element('Settings')
    settings = schematic.one('Settings')
    markings = result.add('Markings')
    vector = _boolean(schematic.scalar('PartFontVector'))
    field(markings, 'FontVector', vector)
    family = style.font_name or settings.scalar('MarkingFontName', '')
    if family or not vector:
        field(markings, 'FontName', family)
    field(markings, 'FontSize', settings.scalar('PartFontSize', style.font_size))
    field(markings, 'FontWidth', stroke_width(schematic.one('PartFontWidth').arguments[0], units))
    number(markings, 'FontScale', schematic.one('PartFontScale').arguments[0])
    color_mode = settings.scalar('UsePartFontColor') if use_part_font_color is None else use_part_font_color
    field(markings, 'UsePartFontColor', _boolean(color_mode))
    field(markings, 'FontColor', settings.scalar('PartFontColor', style.font_color))
    for name in ('RefDes', 'Name', 'Value', 'Manufacturer', 'Datasheet'):
        values = schematic.one('Show'+name+'_Global').values
        marking = markings.add(name+'Global')
        set_attribute(marking, 'Show', enum_text(values[0], SHOW))
        if name in ('RefDes', 'Name'):
            set_attribute(marking, 'ShowPart', enum_text(values[1], SHOW))
        set_attribute(marking, 'Align', enum_text(values[-1], ALIGN))
    users = schematic.select('ShowUserfield_Global/pt')
    if users:
        fields = markings.add('AddFieldsGlobal')
        for user in users:
            if len(user.arguments) != 4:
                raise ValueError('global user-field choices require display name, key, show and alignment')
            display, key, show, alignment = user.values
            item = fields.add('AddField')
            set_attribute(item, 'Show', enum_text(show, SHOW))
            set_attribute(item, 'Align', enum_text(alignment, ALIGN))
            field(item, 'Name', display)
            field(item, 'Value', key)
    grid = result.add('Grid')
    field(grid, 'Visible', _boolean(settings.scalar('GridEnabled')))
    field(grid, 'Snap', _boolean(grid_snap))
    length(grid, 'Size', settings.one('GridSize').arguments[0], units)
    origin = result.add('Origin')
    field(origin, 'Visible', _boolean(settings.scalar('OriginEnabled')))
    field(origin, 'AxisColor', settings.scalar('clAxis'))
    x, y = units.point(schematic.one('OriginX').arguments[0], schematic.one('OriginY').arguments[0])
    number(origin, 'X', x)
    number(origin, 'Y', y)
    widths = result.add('LineWidth')
    for public, own in (('Wire', 'WireLineWidth'), ('NodeSize', 'NodeSize'), ('Bus', 'BusLineWidth'),
                        ('Table', 'TableLineWidth'), ('Titles', 'TitlesLineWidth')):
        length(widths, public, settings.one(own).arguments[0], units)
    buses = result.add('BusConnections')
    field(buses, 'Show', _choice(settings, 'BusConNetName', 'BusConNetNumber', ('NetName', 'Number')))
    field(buses, 'Position', _choice(settings, 'BusConAbove', 'BusConBelow', ('Above', 'Below')))
    field(buses, 'FontSize', settings.scalar('BusConnectionFont'))
    pins = result.add('PinNumbers')
    set_attribute(pins, 'Visible', _choice(settings, 'ShowPinNumbers', 'HidePinNumbers', (True, False)))
    set_attribute(pins, 'Font', settings.scalar('PinNumberFont'))
    field(result, 'HidePower', _boolean(schematic.scalar('HidePower')))
    directory = schematic.scalar('ProjectDir') if project_dir is None else project_dir
    if not isinstance(directory, str):
        raise ValueError('project_dir is required for XML export')
    field(result, 'ProjectDir', directory)
    return result


def project_erc(schematic):
    settings = schematic.one('Settings')
    result = Element('ERC')
    for public, own in (('CheckPinType', 'ERC_PinType'), ('CheckNotConnected', 'ERC_NotConnected'),
                        ('CheckSinglePin', 'ERC_SinglePin'), ('CheckShort', 'ERC_Short'),
                        ('CheckPinSuperimpose', 'ERC_PinSuperimpose')):
        set_attribute(result, public, _boolean(settings.scalar(own)))
    field(result, 'VCCTemplate', settings.scalar('ERC_VCCTemplate'))
    field(result, 'GNDTemplate', settings.scalar('ERC_GNDTemplate'))
    return result
