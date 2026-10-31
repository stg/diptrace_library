"""Keep authored picture sources; consume reconstructable raster cache indices."""
from ....common.conversion import import_notice
from ....common.picture_sources import picture_reference_index
from ..errors import PcbError


def prepare_pictures(board, drawings):
    cached, unresolved = [], []
    count = board.child('PictureCount')
    if count is not None:
        if len(count.values) != 1 or type(count.values[0]) is not int or count.values[0] < 0 or count.children():
            raise PcbError('PictureCount requires one nonnegative integer')
        count.detach()
    for shape in drawings:
        raster = shape.child('RasterIndex')
        if raster is not None:
            if len(raster.values) != 1 or type(raster.values[0]) is not int or raster.children():
                raise PcbError('RasterIndex requires one integer cache position')
            if raster.values[0] >= 0:
                cached.append(shape)
            raster.detach()
        bitmap = shape.child('BitmapIndex')
        if shape.get('Type') != 7:
            if bitmap is not None:
                bitmap.detach()
            continue
        index = picture_reference_index(shape, shape.get('BitmapIndex', -1))
        if bitmap is None:
            shape.add('BitmapIndex', index)
        else:
            bitmap.set_values(index)
        if index >= 0:
            unresolved.append(shape)
    if cached:
        import_notice('info', 'picture-raster-cache', 'Discarded raster cache indices; picture sources remain unchanged',
            cached, recoverability='raster display data is reconstructed from the picture source')
    if unresolved:
        import_notice('warning', 'unresolved-picture-reference',
            'Legacy pictures refer to external companions unavailable in the supplied file', unresolved,
            recoverability='supply Picture_File or Picture_File_Variable; no companion files are opened')
