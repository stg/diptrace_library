"""Neutral point and literal text records shared by design families."""
from .schema import Child, Field, Record


POINT = Record('Point', {name: Field(name, 'number', required=True, default=0, unit='shared length')
                         for name in ('X', 'Y')}, ('X', 'Y'))
TEXT_LINE = Record('TextLine', {
    'Text': Field('Text', 'text', required=True, default='',
                  description='Literal text, or calculated content while bound to a component field.'),
}, ('Text',))
POINTS = Record('Points', {}, description='An ordered collection of Point records.',
                children={'pt': Child('pt', POINT.name, maximum=None)})
TEXT_LINES = Record('TextLines', {}, description='An ordered collection of TextLine records.',
                    children={'pt': Child('pt', TEXT_LINE.name, maximum=None)})
