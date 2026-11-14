"""Small library designs and temporary adapter registration for app tests."""
from contextlib import contextmanager
from importlib import import_module
from unittest.mock import patch

import lib
from lib.common.library_context import ExportContext


FAMILIES = (('pattern', 'lib', 'libxml'), ('component', 'eli', 'elixml'))


@contextmanager
def registered(family):
    """Exercise implemented adapters without publishing unfinished families."""
    api = import_module(f'lib.{family}.formats.io')
    package = import_module(f'lib.{family}')
    with patch.dict(lib._FAMILY_ADAPTERS, {family: api}), \
            patch.object(package, 'ExportContext', ExportContext, create=True):
        yield api


def example(family):
    model = import_module(f'lib.{family}.model')
    document = model.new_library('Examples')
    if family == 'pattern':
        pattern = document.one('/Library/Patterns').append(model.new_pattern('Example'))
    else:
        component = document.one('/Library/Components').append(model.new_component('Example', 'U'))
        pattern = component.append(model.new_pattern('Physical'))
    for name, value in dict(PadShape=2, PadWidth=3, PadHeight=3, SurfacePad=True).items():
        pattern[name] = value
    pad = pattern.one('Pads').append(model.new_pad('1'))
    for name, value in dict(PadShape_New=2, PadWidth_New=3, PadHeight_New=3, SurfacePad=True).items():
        pad[name] = value
    if family == 'component':
        pin = component.one('Parts/Part/Pins').append(model.new_pin())
        pin['StringNumber'], pin['Pad'] = '1', pad
    return document
