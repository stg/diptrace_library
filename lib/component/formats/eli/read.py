"""Read standalone ELI into the current editable component-library model."""
from ....common.conversion import import_diagnostics
from ..import_components import construct_library
from .decode import decode


@import_diagnostics('eli')
def parse(data, *, source=None, ansi_encoding='cp1252'):
    return construct(decode(data, source=source, ansi_encoding=ansi_encoding))


def construct(decoded):
    return construct_library(decoded.root, name=decoded.header.name, hint=decoded.header.hint)
