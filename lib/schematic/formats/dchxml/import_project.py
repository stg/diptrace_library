"""Public paths and string-valued simulator configuration into shared data."""
from .import_library_values import (read_path)
from .import_values import (enum_value, replace_rows)
from ...model.simulation import (SIMULATION_TYPES, SIMULATION_FIELDS)
from ....common.model import (Element)
from ...model.new import (fields)


def read_project(record, schematic):
    libraries = record.take('ProjectLibs')
    if libraries is not None:
        for own, public, kind in (('ProjectLibs_Folders', 'Folders', 'Folder'), ('ProjectLibs_Libs', 'Libs', 'Lib')):
            rows = []
            for item in libraries.rows(public, kind):
                actual, variable = read_path(item)
                path = Element(kind, actual)
                path.add('VariablePath', variable)
                rows.append(path)
            replace_rows(schematic, own, rows)
        schematic.set_field('ProjectLibs_Sorted', libraries.boolean('Sorted', False))
        libraries.finish()
    simulator = record.take('Simulator')
    if simulator is None:
        return
    target = schematic.one('ssimulator')
    target.set_field('tp', enum_value(simulator.value('Type', 'None'), SIMULATION_TYPES))
    signals = []
    for source in simulator.rows('Signals', 'Signal'):
        signal = Element('signal')
        fields(signal, signal_tp=enum_value(source.value('Type'), ('Current', 'Voltage')),
               signal_num=source.integer('Id'), signal_display_name=source.text('DisplayName', ''),
               signal_plotted=source.boolean('Plotted', False), signal_visible=source.boolean('Visible', False),
               signal_color=source.integer('Color', 0))
        source.finish()
        signals.append(signal)
    replace_rows(target, 'signals', signals)
    for own, public, names in SIMULATION_FIELDS:
        source = simulator.take(public)
        if source is None:
            if own != 'sim_digital':
                replace_rows(target, own, [])
            continue
        present = [index for index, name in enumerate(names) if source.has(name)]
        if present and present != list(range(max(present)+1)):
            raise ValueError(f'{source.node.path}: incomplete named simulator argument sequence')
        values = [Element(names[index], source.text(names[index])) for index in present]
        for item in source.children('Item'):
            name = names[len(values)] if len(values) < len(names) else 'Item'
            values.append(Element(name, item.content()))
            item.finish(allow_text=True)
        source.finish()
        replace_rows(target, own, values)
    from ...model.simulation import (OPTION_FIELDS)
    for group in dict.fromkeys(item[0] for item in OPTION_FIELDS):
        source = simulator.take(group)
        if source is None:
            continue
        for owner, name, kind, default in OPTION_FIELDS:
            if owner == group:
                method = {'text': source.text, 'integer': source.integer, 'boolean': source.boolean}[kind]
                target.one(group).set_field(name, method(name, default))
        source.finish()
    target.set_field('gndnum', simulator.integer('GndNetId', -1))
    target.set_field('gndname', simulator.text('GndNetName', ''))
    simulator.finish()
