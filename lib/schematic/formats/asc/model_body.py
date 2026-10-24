"""SPICE model text at the ASC boundary, with owned lines in the shared model."""
from ....common.model import (Element)


def project_model_body(body):
    if body.arguments:
        raise ValueError(f'{body.path}: shared model bodies use Line records')
    lines = body.children()
    for line in lines:
        parameters = line.schema.parameters if line.schema is not None else ()
        children = [child for child in line.children() if child.kind not in parameters]
        if line.kind != 'Line' or children or len(line.arguments) != 1 or line.arguments[0].kind != 'string':
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
