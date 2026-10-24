"""Document display choices with deterministic defaults for absent settings."""


def default_line_width(layer):
    """Standard physical pen width when no application context is supplied."""
    return .1


def display_units(document):
    settings = document.one('/Schematic/Settings')
    choices = [name for field, name in (('UnitsMM', 'mm'), ('UnitsMIL', 'mil'), ('UnitsINCH', 'inch'))
               if settings.scalar(field, False) in (True, 'Y')]
    return choices[0] if len(choices) == 1 else 'mm'
