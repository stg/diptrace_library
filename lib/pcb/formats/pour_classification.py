"""Project classification availability independently of primitive assignments."""
from ...common.conversion import info, warn
from ..model import pour_regions
from .errors import PcbError
from .output_validation import check_tree


def available(fill, *, destination, report=None):
    if fill is None:
        return False
    collection = fill.child('Regions')
    if collection is None:
        if next(pour_regions.primitives(fill), None) is not None:
            info(report, 'pour-regions-unavailable', destination,
                'Calculated pour classification remains unavailable in output.', (fill,),
                recoverability='fill geometry remains; a geometric editor can classify it')
        return False
    check_tree(collection, pour_regions.REGIONS, destination=destination.upper())
    try:
        pour_regions.validate_collection(collection)
    except (TypeError, ValueError) as error:
        raise PcbError(f'{collection.path}: {error}') from error
    used = {target for primitive in pour_regions.primitives(fill)
            if (target := primitive['Region']) is not None}
    unused = tuple(region for region in collection.children('Region') if region not in used)
    if unused:
        warn(report, 'unused-pour-regions', destination,
             'Pour groups without member geometry have no independent output record.', unused,
             recoverability='assigned groups and classification availability remain; unused numeric labels are omitted')
    return True
