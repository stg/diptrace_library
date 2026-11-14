"""Public physical-library XML scalar vocabulary shared by standalone adapters."""

NUMBERS = frozenset('''UID32 Id Index Number X Y Z X1 Y1 X2 Y2 XD YD Width Height Angle
Orientation Float1 Float2 Float3 Int1 Int2 Hole HoleH Corner XOff YOff Diam HoleDiam
Segment_Percent Segment_EdgeGap Segment_Gap Segment_Side CustomSwell CustomShrink
IPC_XOff IPC_YOff AutoHeight AutoColor FontSize FontSizeFloat FontWidth FontScale TextWidth TextHeight
FontColor LineWidth LineSpacing Object1 Object2 SubObject1 SubObject2 Point1 Point2
ArrowSize ExternalRadius Group PadId'''.split())
FLAGS = frozenset('''Enabled Locked AllLayers FontVector FontMono DefStyle
LockTypeChange Cross Circle Mirror NoSearch KeepPins Generator Model HorzFlip ShowUnits'''.split())
