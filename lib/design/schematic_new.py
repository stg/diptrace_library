"""Owned starting values for new data and public-format imports."""
from .model import Document, Element, Value
from .simulation import default_simulator


def fields(parent, **values):
    for name, value in values.items():
        parent.add(name, value)
    return parent


def new_page(name='Sheet 1'):
    page = Element('Page', name)
    fields(page, Zones=False, PageWidth=630, PageHeight=891, HorzZones=8, VertZones=8,
           ZoneStandard=0, ZoneFontName='Arial', ZoneFontSize=6, ZoneBorder=False,
           HorzZoneBorder=0, VertZoneBorder=0, PageXPos=0, PageyPos=0, PageScale=1,
           PageType=0, PageHiddenId=0, FLeft=0, FTop=0, FRight=0, FBottom=0)
    page.add('FontLineWidth', -1).annotations['asc_omit'] = 'zone font pen is not present in ASC'
    titles = page.add('TitleBlocks')
    titles.annotations['asc_omit'] = 'format schematic ASC omits title grids'
    for index in range(6):
        grid = titles.add('TitleBlock', index, '')
        fields(grid, Width=0, Height=0)
        for key in ('ColWidths', 'RowHeights', 'Cells', 'Contents'):
            grid.add(key)
    return page


def new_settings():
    settings = Element('Settings')
    fields(settings, GridSize=3, OriginEnabled=False, clAxis=0, BusConnectionFont=6,
           PinNumberFont=6, PartFontSize=6, PartFontColor=0, UsePartFontColor=True,
           GridEnabled=True, GridSnap=True, DisplayTitles=False, DisplaySheet=True,
           BusConNetName=True, BusConNetNumber=False, ShowPinNumbers=True, HidePinNumbers=False,
           BusConAbove=True, BusConBelow=False, BusLineWidth=.9, WireLineWidth=.3,
           TableLineWidth=.3, TitlesLineWidth=.3, NodeSize=.9,
           UnitsMM=True, UnitsMIL=False, UnitsINCH=False,
           ERC_PinType=True, ERC_NotConnected=True, ERC_SinglePin=True, ERC_Short=True,
           ERC_VCCTemplate='VCC', ERC_GNDTemplate='GND', ERC_PinSuperimpose=True)
    return settings


def new_schematic(*, sheet_name='Sheet 1'):
    """Create an empty shared schematic with declared, editable authoring data."""
    document = Document(representation='schematic')
    document.root.add('Source', 'DipTrace-Schematic', 46)
    document.root.add('Scale', Value(100, 'number', '%'))
    document.root.add('Xpos', 0)
    document.root.add('Ypos', 0)
    schematic = document.root.add('Schematic')
    pages = schematic.add('Pages')
    pages.append(new_page(sheet_name))
    fields(schematic, PictureCount=0, HidePower=False, OriginX=0, OriginY=0,
           PartFontVector=True, PartFontWidth=-1, PartFontScale=1, ProjectDir='',
           ProjectLibs_Name='', ProjectLibs_Type=0, ProjectLibs_Content=0,
           ProjectLibs_Sorted=False, DesignCache_Count=-1)
    schematic.add('NetClasses').add('NetClass', 'Default', 0, -1, -1, 0, -1, 0, 0, 0, 0)
    schematic.add('DifferentialPairs')
    for name in ('RefDes', 'Name'):
        schematic.add('Show'+name+'_Global', 1 if name == 'RefDes' else 2, 1 if name == 'RefDes' else 2, 7)
    for name in ('Value', 'Manufacturer', 'Datasheet'):
        schematic.add('Show'+name+'_Global', 1 if name == 'Value' else 2, 7)
    schematic.add('ShowUserfield_Global')
    for name in ('Components', 'PageConnectors', 'Shapes', 'Nets', 'Buses', 'Groups', 'Tables',
                 'ProjectLibs_Folders', 'ProjectLibs_Libs', 'DesignCache_Links'):
        schematic.add(name)
    schematic.append(new_settings())
    schematic.append(default_simulator())
    cache = schematic.add('CacheLib')
    for name in ('Categories', 'Subfolders', 'Slots'):
        cache.add(name)
    document.metadata.update(source_format='schematic', source_version=46,
                             binary_consumed=False, missing_data_policy='declared authoring defaults')
    from .schematic_refs import bind_schematic_references
    bind_schematic_references(document)
    return document
