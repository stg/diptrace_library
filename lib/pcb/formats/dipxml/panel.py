"""Panel copy layout and tab data, normalized from XML compatibility variants."""
from ....common.xml_records import enum_value, length
from ...model.board_records import PANEL


def read_panel(record, board, *, units, version):
    if record is None:
        return
    panel = board.add('Panel')
    for public, own in (('Columns', 'PanelX'), ('Rows', 'PanelY')):
        if record.has(public):
            board.add(own, record.integer(public))
    for public, own in (('ColumnSpacing', 'PanelDX'), ('RowSpacing', 'PanelDY')):
        if record.has(public):
            board.add(own, length(record.number(public), units,
                reverse=public == 'RowSpacing' and version.legacy_panel_coordinates))
    if record.has('RailShow'):
        board.add('RailShow', record.boolean('RailShow'))
    for name in ('RailLeft', 'RailRight', 'RailTop', 'RailBottom'):
        if record.has(name):
            value = record.number(name)
            board.add(name, length(value, units) if version.panel_metrics_in_display_units else value)
    if record.has('Type'):
        panel.add('Type', enum_value(record.value('Type'), ('V-Scoring', 'Tab Routing')))
    for name, field in PANEL.fields.items():
        if name == 'Type' or not record.has(name):
            continue
        if field.kind == 'number':
            value = record.number(name)
            panel.add(name, length(value, units) if version.panel_metrics_in_display_units else value)
        else:
            panel.add(name, getattr(record, field.kind)(name))
    for name in ('HorzTabsX', 'VertTabsY'):
        positions = panel.add(name)
        for source in record.rows(name, 'Item'):
            value = source.content()
            if value.kind != 'number' or value.unit:
                raise ValueError(f'{source.node.path}: expected a panel tab position')
            positions.add('Item', value if version.legacy_panel_coordinates else
                          length(value, units, reverse=name == 'VertTabsY'))
            source.finish(allow_text=True)
    record.finish()
