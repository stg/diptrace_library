"""Public XML labels shared by physical footprint adapters."""


HORZ = ('Center', 'Right', 'Left')
VERT = ('Center', 'Bottom', 'Top')
MASK_STATES = ('Common', 'Open', 'Tented', 'By Paste')
PASTE_STATES = ('Common', 'Solder', 'No Solder', 'Segments')
PATTERN_TYPES = ('Free', 'Right Angle', 'Left Angle', 'T', 'Circle', 'Lines', 'Square', 'Matrix',
                 'Rectangle', 'Zig-Zag', 'IPC-7351')
DRAWING_TYPES = ('None', 'Line', 'Rectangle', 'Obround', 'FillRect', 'FillObround', 'Arc', 'Text', 'Polyline', 'Polygon')
LAYERS = ('Top Silk', 'Top Assy', 'Top Mask', 'Top Paste', 'Bottom Paste', 'Bottom Mask', 'Bottom Assy',
    'Bottom Silk', 'Top', 'Top Keepout', 'Bottom Keepout', 'Bottom', 'Board Cutout', 'Top Dimension',
    'Bottom Dimension', 'Non-Signal', 'Top Courtyard', 'Bottom Courtyard', 'Top Outline', 'Bottom Outline',
    'Top Terminals', 'Bottom Terminals')
TEXT_SHOW = ('Any Text', 'Name', 'RefDes', 'Value', 'Manufacturer', 'Unique Name', 'Datasheet')
POINTER_MODES = ('Coordinates', 'Comment')
