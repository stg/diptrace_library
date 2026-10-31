"""Resolve board drawing colors against an optional import display environment."""
from ....common.conversion import import_notice


def normalize_graphic_colors(decoded, context):
    """Keep drawings visible under the selected canvas, without source backups."""
    background = context.background_color
    if background is None:
        return
    contrast = 0xC0C0C0 if background == 0 else 0xFFFFFF - background
    changed = []
    for shape in decoded.board.select('Shapes/Shape'):
        if not shape.get('Enabled', True):
            continue
        updated = False
        for name in ('Color', 'BrushColor', 'FontColor'):
            if shape.scalar(name) == background:
                shape.set_field(name, contrast)
                updated = True
        if updated:
            changed.append(shape)
    if changed:
        import_notice('info', 'drawing-background-color',
                      'Adjusted drawing colors matching the import canvas background.', changed)
