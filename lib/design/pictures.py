"""Legacy sheet pictures as editable file-backed drawings."""
from .asc_policy import calculation_number


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
    unresolved = []
    for shape in schematic.select('Shapes/Shape'):
        if shape.scalar('Type')!=11:
            continue
        index=shape.scalar('BitmapIndex',-1)
        if isinstance(index,bool) or not isinstance(index,int):
            raise TypeError(f'{shape.path}: BitmapIndex requires an integer')
        if index>=0 and not (shape.scalar('Picture_File','') or shape.scalar('Picture_File_Variable','')):
            if filenames is not None and index<len(filenames) and filenames[index]:
                shape.set_field('Picture_File',filenames[index])
            else:
                unresolved.append(shape)
                if destination == 'asc':
                    continue
        shape.set_field('BitmapIndex',-1)
    if unresolved:
        from .conversion import warn
        message = ('unresolved picture indices are retained; current application readers require picture filenames'
                   if destination == 'asc' else
                   'unresolved companion picture references become unassigned picture sources')
        warn(report, 'unresolved-picture-reference', destination, message, unresolved,
             recoverability='supply a current Picture_File or an explicit legacy_picture_files table; authoring references remain intact')
