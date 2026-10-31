"""Connection kinds shared by the PCB binary and public text adapters."""

CONNECTION_CODES = {'Free': -1, 'Pad': 0, 'Trace': 1, 'Segment': 5, 'Separate Trace': 6}
CONNECTION_NAMES = {code: name for name, code in CONNECTION_CODES.items()}
# The text enumeration also accepts its final, positive Free entry.
CONNECTION_NAMES[7] = 'Free'
