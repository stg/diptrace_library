"""Cell.Text is authoritative; public line lists are generated format views."""


def cell_text_lines(text):
    """Split LF and discard trailing ASCII-space-only lines in cell views."""
    result = text.split('\n')
    while result and not result[-1].replace(' ', ''):
        result.pop()
    return result


def _line_values(cell, lines):
    values = []
    for line in lines.children():
        if line.kind != 'pt' or len(line.arguments) != 1 or line.arguments[0].kind != 'string' or line.children():
            raise ValueError(f'{cell.path}: cell text lines require plain pt strings')
        values.append(line.values[0])
    return values


def cell_text(cell):
    """Return the one current text value, independent of edit history."""
    text = cell.one('Text')
    if len(text.arguments) != 1 or text.arguments[0].kind != 'string' or text.children():
        raise ValueError(f'{cell.path}: cell Text requires a plain string')
    if cell.child('TextLine') is not None:
        raise ValueError(f'{cell.path}: edit Text; TextLine is an output view')
    return text.values[0]


def cell_lines(cell):
    return cell_text_lines(cell_text(cell))


def unpack_asc_cell_text(cell):
    """The modern line list takes precedence over ASC's older scalar view."""
    text, lines = cell.one('Text'), cell.child('TextLine')
    if len(text.arguments) != 1 or text.arguments[0].kind != 'string' or text.children():
        raise ValueError(f'{cell.path}: cell Text requires a plain string')
    if lines is not None:
        current = '\n'.join(_line_values(cell, lines))
        text.set_values(current)
        lines.detach()


def asc_cell_text(cell):
    """Generate ASC's redundant compatibility scalar from current text."""
    return '\n'.join(cell_lines(cell))


def normalized_cell_text(text):
    """Remove trailing empty or ASCII-space-only rows, preserving other text."""
    return '\n'.join(cell_text_lines(text))


def modernize_cell_text(owner, *, paths):
    for path in paths:
        for cell in owner.select(path):
            field = cell.child('Text')
            if field is None:
                continue
            if len(field.arguments) != 1 or field.arguments[0].kind != 'string' or field.arguments[0].unit:
                raise TypeError('cell text must be one plain string')
            text = normalized_cell_text(field.values[0])
            if text != field.values[0]:
                field.set_values(text)
