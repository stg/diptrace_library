"""Legacy sheet pictures as editable file-backed drawings."""
from ...common.numbers import (calculation_number)
from ...common.picture_sources import prepare_picture_sources


def upgrade_legacy_pictures(version,schematic):
    """Modernize pre-42 picture geometry once, during import.

    The old bitmap table belongs to the application environment, not the DCH
    scalar stream. An unresolved table index remains explicit until supplied.
    """
    if version>=42:
        return
    for shape in schematic.select('Shapes/Shape'):
        if shape.scalar('Type')!=11:
            continue
        points=shape.one('Points_New')
        records=points.children('pt')
        def coordinates(point):
            return tuple(calculation_number(point,i) for i in range(len(point.arguments)))
        anchor=coordinates(records[0]) if records else (0.,0.)
        if len(records)>1:
            other=coordinates(records[1])
            shape.set_field('Picture_Width',round(other[0]-anchor[0]))
            shape.set_field('Picture_Height',round(other[1]-anchor[1]))
            anchor=tuple(min(a,b) for a,b in zip(anchor,other))
        for point in records:
            points.remove(point)
        points.add('pt',*anchor)
        for name,value in [('TextHorz',-1),('TextVert',-1),('TextAngle',0),
                           ('Picture_Proportions',False),('Picture_Transparent',0)]:
            shape.set_field(name,value)


def prepare_pictures(schematic, *, destination, filenames=None, report=None):
    """Resolve current external picture references on an already detached view.

    An explicit file is authoritative. An optional filename table can resolve an
    old companion reference without opening another input. Missing entries remain
    unresolved in ASC; other destinations receive an unassigned source and a
    meaningful-loss warning. Geometry is never migrated here.
    """
    if destination not in ('dch', 'asc', 'dchxml'):
        raise ValueError('unsupported picture destination')
    prepare_picture_sources((shape for shape in schematic.select('Shapes/Shape') if shape.scalar('Type') == 11),
        destination=destination, keep_legacy_indices=destination == 'asc', filenames=filenames, report=report)
