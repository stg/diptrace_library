"""SPICE model text at the ASC boundary, with owned lines in the shared model."""
from .model import Element


def project_model_body(body):
    if body.arguments:
        raise ValueError(f'{body.path}: shared model bodies use Line records')
    lines = body.children()
    if any(line.kind != 'Line' or line.children() or len(line.arguments) != 1 or
           line.arguments[0].kind != 'string' for line in lines):
        raise ValueError(f'{body.path}: expected one string per model Line')
    return Element('ModelBody', *(line.arguments[0] for line in lines))


def unpack_model_body(body):
    """Normalize flat ASC strings, retaining blank lines and their order."""
    if body.arguments:
        if body.children() or any(value.kind != 'string' for value in body.arguments):
            raise ValueError(f'{body.path}: expected flat model text strings')
        values = body.arguments
        body.set_values()
        for value in values:
            body.add('Line', value)
    # Also accept the owned row spelling emitted by earlier library versions.
    project_model_body(body)
