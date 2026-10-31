"""Current board outline, layers, drawings and picture data in PCB XML."""
from ....common.conversion import warn
from ....common.model import Element
from ....common.picture_sources import picture_source_paths
from ....common.xml import set_attribute
from ....common.xml_font_output import project_size
from ....common.xml_footprint_vocabulary import HORZ, VERT
from ....common.xml_output import enum_text, field, numeric, point_attributes, stroke_width
from ...model import graphic_records, settings_records
from ..errors import PcbError
from ..output_validation import check_tree, field_value
from .graphics import TYPES, LAYERS


def project_outline(board, *, units):
    result = Element('BoardOutline')
    for name in ('Enabled', 'Selected', 'Locked', 'PanelExclude'):
        if name in board:
            set_attribute(result, name, board[name])
    if (shield := board.get('ShieldGroup')) is not None and shield >= 0:
        set_attribute(result, 'ShieldGroup', shield)
    if (source := board.child('Points')) is not None:
        check_tree(source, graphic_records.OUTLINE_POINTS, destination='DIPXML')
        points = result.add('Points') if source.children() else None
        for point in source.children('pt'):
            row = points.add('Point')
            point_attributes(row, point['X'], point['Y'], units)
            set_attribute(row, 'Arc', point['Arc'])
    return result


def project_non_signals(board):
    result = Element('NonSignals')
    for source in board.select('NonSignals/NonSignal'):
        check_tree(source, graphic_records.NON_SIGNAL, destination='DIPXML')
        row = result.add('NonSignal')
        for name in ('Id', 'Color'):
            set_attribute(row, name, field_value(source, name))
        set_attribute(row, 'Side', enum_text(field_value(source, 'Side'), ('None', 'Top', 'Bottom')))
        field(row, 'Name', field_value(source, 'Name'))
    return result


def project_layer_panel(board):
    settings = board.child('Settings')
    source = settings.child('LayerPanel') if settings is not None else None
    rows = board.select('NonSignals/NonSignal')
    result = Element('LayerPanel')
    if source is not None:
        check_tree(source, settings_records.LAYER_PANEL, destination='DIPXML')
        for name in settings_records.LAYER_PANEL.fields:
            if source.child(name) is not None:
                set_attribute(result, name, source[name])
    missing = False
    for row in rows:
        if row.child('Visible') is None:
            missing = True
        elif missing:
            raise PcbError(f'{row.path}: XML visibility cannot skip an earlier custom layer')
        else:
            field(result, 'NonSignal', 'Y' if row['Visible'] else 'N')
    return result


def _picture(source, result, *, units, legacy_picture_files, report):
    actual, variable, unresolved = picture_source_paths(source, filenames=legacy_picture_files)
    if unresolved >= 0:
        warn(report, 'unresolved-picture-reference', 'dipxml',
             'Unresolved companion picture reference becomes an unassigned picture source', (source,),
             recoverability='supply Picture_File or an explicit legacy_picture_files table; source references remain intact')
    if actual or variable:
        target = result.add('PictureFile')
        field(target, 'Path', actual)
        field(target, 'Var', variable)
    if (vector := source.child('PictureVector')) is not None:
        target = result.add('PictureVector')
        for name in ('Width', 'Height'):
            set_attribute(target, name, numeric(units.length(field_value(vector, name))))
        polygons = target.add('Polygons')
        for polygon in vector.select('Polygons/Polygon'):
            points = polygons.add('Polygon').add('Points')
            for vertex in polygon.select('Points/Item'):
                point_attributes(points.add('Point'), vertex['X'], vertex['Y'], units)


def project_drawings(board, *, units, report=None, legacy_picture_files=None, physical_font_width=True):
    result = Element('Shapes')
    for source in board.select('Shapes/Shape'):
        check_tree(source, graphic_records.SHAPE, destination='DIPXML')
        if not field_value(source, 'Enabled'):
            raise PcbError(f'{source.path}: inactive drawing needs output normalization')
        if graphic_records.layer_scope(source) is not None and source['LayerTarget'] is None:
            raise PcbError(f'{source.path}: select a drawing layer before export')
        target = result.add('Shape')
        kind = field_value(source, 'Type')
        for name, value in (('Id', source['Id']), ('Type', enum_text(kind, TYPES)),
                            ('Layer', enum_text(field_value(source, 'Layer'), LAYERS)), ('LayId', source['LayId']),
                            ('NetId', source['NetNumber']), ('Group', source['GroupId'])):
            set_attribute(target, name, value)
        for name in ('Enabled', 'Selected', 'AllLayers', 'Locked', 'PanelExclude'):
            set_attribute(target, name, field_value(source, name))
        if kind in (6, 7):
            for public, own, labels in (('HorzAlign', 'TextHorz', HORZ), ('VertAlign', 'TextVert', VERT)):
                set_attribute(target, public, enum_text(field_value(source, own), labels, negative=labels[-1]))
            set_attribute(target, 'Inverted', field_value(source, 'Inverted'))
        if kind in (6, 10):
            set_attribute(target, 'TextAlign', enum_text(field_value(source, 'TextAlign'), HORZ, negative=HORZ[-1]))
        set_attribute(target, 'Angle', field_value(source, 'TextAngle'))
        if kind == 6:
            set_attribute(target, 'FontVector', field_value(source, 'VectorFont'))
            project_size(source, target)
            width = field_value(source, 'FontWidth')
            set_attribute(target, 'FontWidth', stroke_width(width, units) if physical_font_width else width)
            for name in ('FontScale', 'LineSpacing'):
                set_attribute(target, name, field_value(source, name))
        if field_value(source, 'PenWidth') != -1:
            set_attribute(target, 'LineWidth', numeric(units.length(field_value(source, 'PenWidth'))))
        if kind == 7:
            for name in ('PictureRaster', 'PictureProportions', 'PictureFlipped', 'PictureTransparent'):
                set_attribute(target, name, field_value(source, name))
            for name in ('PictureWidth', 'PictureHeight'):
                set_attribute(target, name, numeric(units.length(field_value(source, name))))
        if kind in (6, 10):
            field(target, 'FontName', field_value(source, 'FontName'))
            lines = target.add('TextLines')
            for line in source.select('TextLine/pt'):
                field(lines, 'TextLine', line['Text'])
        points = target.add('Points')
        for point in source.select('Points/pt'):
            point_attributes(points.add('Point'), point['X'], point['Y'], units)
        if kind == 7:
            _picture(source, target, units=units, legacy_picture_files=legacy_picture_files, report=report)
        omitted = [name for name in ('Color', 'BrushColor', 'FontColor', 'ShieldGroup')
                   if field_value(source, name) != -1]
        if omitted:
            warn(report, 'board-drawing-options', 'dipxml', 'XML omits drawing '+', '.join(omitted), (source,))
    return result
