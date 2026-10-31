"""Public sheet, global display and net-class data into shared records."""
from ....common.xml_records import (XmlRecord, enum_value, length, point, replace_rows)
from .settings import (SHOW, ALIGN)
from ...layout.markings import (MarkingStyle)
from ....common.model import (Element)
from ...model.new import (new_page)
from ....common.xml_font_import import (read_size)


def read_sheets(record, schematic, *, units):
    settings = schematic.one('Settings')
    settings.set_field('DisplayTitles', record.boolean('DisplayTitles', False))
    settings.set_field('DisplaySheet', record.boolean('DisplaySheet', True))
    active = record.integer('ActiveSheet', 0)
    pages, ids = [], {}
    for index, item in enumerate(record.rows('Sheets', 'Sheet')):
        key = item.integer('Id', index)
        if key in ids:
            raise ValueError('duplicate XML sheet Id')
        ids[key] = index
        page = new_page(item.text('Name', ''))
        page.set_field('PageType', enum_value(item.value('Type', 'Normal'), ('Normal', 'Hierarchy Block')))
        page.set_field('PageHiddenId', item.integer('BlockId', 0))
        for name, value in zip(('PageXPos', 'PageyPos'), point(item, units, ('XPos', 'YPos'), 0)):
            page.set_field(name, value)
        page.set_field('PageScale', item.number('Scale', 1))
        for public, own in (('SheetWidth', 'PageWidth'), ('SheetHeight', 'PageHeight'),
                            ('LeftMargin', 'FLeft'), ('TopMargin', 'FTop'),
                            ('RightMargin', 'FRight'), ('BottomMargin', 'FBottom')):
            page.set_field(own, length(item.number(public, 0), units))
        zones = item.take('BorderZones')
        if zones is not None:
            for public, own in (('Visible', 'Zones'), ('Border', 'ZoneBorder')):
                page.set_field(own, zones.boolean(public, False))
            for public, own in (('HorzZones', 'HorzZones'), ('VertZones', 'VertZones'),
                                ('Standard', 'ZoneStandard')):
                page.set_field(own, zones.integer(public, 0))
            page.set_field('ZoneFontName', zones.text('FontName', ''))
            page.set_field('ZoneFontSize', read_size(zones, default=0))
            for public, own in (('HorzBorderSize', 'HorzZoneBorder'), ('VertBorderSize', 'VertZoneBorder')):
                page.set_field(own, length(zones.number(public, 0), units))
            width = zones.number('FontLineWidth', -1)
            page.set_field('FontLineWidth', width if width.value < 0 else length(width, units))
            zones.finish()
        from ....common.xml_cells import read_title_blocks
        read_title_blocks(item, page, units=units)
        item.finish()
        pages.append(page)
    record.finish()
    if not pages:
        raise ValueError('shared schematics require at least one XML sheet')
    replace_rows(schematic, 'Pages', pages)
    return ids, active


def read_settings(record, schematic, *, units):
    settings = schematic.one('Settings')
    markings = record.take('Markings', required=True)
    vector = markings.boolean('FontVector', True)
    font = markings.text('FontName', '')
    schematic.set_field('PartFontVector', vector)
    settings.set_field('PartFontSize', read_size(markings))
    settings.set_field('PartFontMono', markings.boolean('FontMono', False))
    width = markings.number('FontWidth', -1)
    schematic.set_field('PartFontWidth', width if width.value < 0 else length(width, units))
    schematic.set_field('PartFontScale', markings.number('FontScale', 1))
    settings.set_field('UsePartFontColor', markings.boolean('UsePartFontColor', True))
    settings.set_field('PartFontColor', markings.integer('FontColor', 0))
    settings.add('MarkingFontName', font)
    for name in ('RefDes', 'Name', 'Value', 'Manufacturer', 'Datasheet'):
        source = markings.take(name+'Global', required=True)
        values = [enum_value(source.value('Show', 'Common'), SHOW)]
        if name in ('RefDes', 'Name'):
            values.append(enum_value(source.value('ShowPart', 'Common'), SHOW))
        values.append(enum_value(source.value('Align', 'Common'), ALIGN))
        schematic.one('Show'+name+'_Global').set_values(*values)
        source.finish()
    users = schematic.one('ShowUserfield_Global')
    for source in markings.rows('AddFieldsGlobal', 'AddField'):
        name, value = source.text('Name', ''), source.text('Value', '')
        users.add('pt', name, value, enum_value(source.value('Show', 'Common'), SHOW),
                  enum_value(source.value('Align', 'Common'), ALIGN))
        source.finish()
    markings.finish()
    grid = record.take('Grid', required=True)
    settings.set_field('GridEnabled', grid.boolean('Visible', True))
    settings.set_field('GridSnap', grid.boolean('Snap', True))
    size = length(grid.number('Size'), units)
    settings.set_field('GridSize', size)
    grid.finish()
    origin = record.take('Origin', required=True)
    settings.set_field('OriginEnabled', origin.boolean('Visible', False))
    settings.set_field('clAxis', origin.integer('AxisColor', 0))
    for own, value in zip(('OriginX', 'OriginY'), point(origin, units, default=0)):
        schematic.set_field(own, value)
    origin.finish()
    widths = record.take('LineWidth', required=True)
    for public, own in (('Wire', 'WireLineWidth'), ('NodeSize', 'NodeSize'), ('Bus', 'BusLineWidth'),
                        ('Table', 'TableLineWidth'), ('Titles', 'TitlesLineWidth')):
        settings.set_field(own, length(widths.number(public), units))
    widths.finish()
    buses = record.take('BusConnections', required=True)
    show = enum_value(buses.value('Show'), ('NetName', 'Number'))
    position = enum_value(buses.value('Position'), ('Above', 'Below'))
    settings.set_field('BusConNetName', show == 0)
    settings.set_field('BusConNetNumber', show == 1)
    settings.set_field('BusConAbove', position == 0)
    settings.set_field('BusConBelow', position == 1)
    settings.set_field('BusConnectionFont', read_size(buses))
    buses.finish()
    pins = record.take('PinNumbers', required=True)
    visible = pins.boolean('Visible', True)
    settings.set_field('ShowPinNumbers', visible)
    settings.set_field('HidePinNumbers', not visible)
    settings.set_field('PinNumberFont', read_size(pins, 'Font'))
    pins.finish()
    net_name = record.take('NetName')
    if net_name is not None:
        settings.set_field('NetNameFontSize', read_size(net_name, default=4))
        net_name.finish()
    schematic.set_field('HidePower', record.boolean('HidePower', False))
    schematic.set_field('ProjectDir', record.text('ProjectDir', ''))
    record.finish()
    return MarkingStyle(vector=vector, font_name=font, font_size=settings.scalar('PartFontSize'),
                        font_width=float(schematic.scalar('PartFontWidth')), font_scale=float(schematic.scalar('PartFontScale')),
                        font_color=settings.scalar('PartFontColor'))


def read_erc(record, schematic):
    settings = schematic.one('Settings')
    for public, own in (('CheckPinType', 'ERC_PinType'), ('CheckNotConnected', 'ERC_NotConnected'),
                        ('CheckSinglePin', 'ERC_SinglePin'), ('CheckShort', 'ERC_Short'),
                        ('CheckPinSuperimpose', 'ERC_PinSuperimpose')):
        settings.set_field(own, record.boolean(public, True))
    for public, own in (('VCCTemplate', 'ERC_VCCTemplate'), ('GNDTemplate', 'ERC_GNDTemplate')):
        settings.set_field(own, record.text(public, ''))
    record.finish()


def read_classes(record, schematic, *, units):
    rows = record.rows('NetClasses', 'NetClass')
    classes, ids = [], {}
    for index, source in enumerate(rows):
        key = source.integer('Id', index)
        if key in ids:
            raise ValueError('duplicate XML net-class Id')
        ids[key] = index
        kind = enum_value(source.value('Type', 'Normal'), ('Normal', 'Differential Pair'))
        values = [source.text('Name', ''), kind]
        for name in ('Width', 'Clearance'):
            values.append(length(source.number(name), units) if source.has(name) else -1)
        values.append(source.integer('UpdateId', 0))
        for name in ('DifClearance', 'MaxUncoupledLength', 'Tolerance', 'Phase', 'Phase_ErrorLength'):
            values.append(-1 if name == 'DifClearance' and not source.has(name)
                          else length(source.number(name, 0), units))
        classes.append(Element('NetClass', *values))
        source.finish()
    if classes:
        replace_rows(schematic, 'NetClasses', classes)
    return ids
