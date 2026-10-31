"""Adapt dimension endpoints whose calculated drawing has no XML record."""
from ....common.conversion import warn


def marking_endpoint(dimension, side, shape, *, report=None):
    """Return a free endpoint for omitted marking text, otherwise no adaptation."""
    if shape['Type'] != 7 or not shape.get('MarkingGenerated', False):
        return None
    warn(report, 'dimension-marking-attachment', 'dipxml',
         f'XML omits dimension endpoint {side}\'s attachment to calculated marking geometry',
         (dimension, shape),
         recoverability='endpoint coordinates remain; the endpoint is exported as unattached')
    return -1, 0, 0, 0
