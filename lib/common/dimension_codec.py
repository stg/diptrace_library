"""Shared dimension geometry, attachments and display properties."""
from .model import SourceSpan


def read_dimension_properties(reader, dimension):
    reader.fields(dimension, (
        *((name, 'integer') for name in ('Type', 'Connected1', 'Object1', 'SubObject1', 'Point1',
                                         'Connected2', 'Object2', 'SubObject2', 'Point2', 'Layer')),
        *((name, 'number') for name in ('X1', 'Y1', 'X2', 'Y2', 'XD', 'YD', 'ArrowSize')),
        ('Units', 'integer'), ('VectorFont', 'boolean'), ('FontName', 'text'),
        ('FontSize', 'integer'), ('FontScale', 'number'), ('FontWidth', 'number'),
        ('ShowUnits', 'boolean'), ('Angle', 'number'), ('ExternalRadius', 'integer'),
        ('PointerMode', 'integer'), ('PointerText', 'text'),
    ))
    return dimension


def read_dimensions(reader, owner):
    dimensions = owner.add('Dimensions')
    for index in range(reader.count('footprint dimensions')):
        dimension = reader.record(dimensions, 'Dimension')
        dimension.set_values(index)
        reader.fields(dimension, (('Enabled', 'boolean'), ('Locked', 'boolean')))
        read_dimension_properties(reader, dimension)
        dimension.source = SourceSpan(reader.source_format, dimension.source.start,
                                      reader.pos, reader.source)
    return dimensions
