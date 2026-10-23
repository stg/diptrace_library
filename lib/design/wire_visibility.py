"""Power-wire visibility from current component and route attachments."""


def net_wire_visibility(net,components,*,hide_power):
    """Return visibility flags, propagating hidden power connections by identity.

    Existing hidden flags seed the propagation while power hiding is enabled.
    Disabling it exposes all wires, including stale flags stored in older files.
    """
    lines=net.one('Lines').children('Line')
    if not hide_power:
        return [False]*len(lines)
    component_keys={int(p.scalar('Number')):p for p in components}
    line_keys={int(line.scalar('Number')):i for i,line in enumerate(lines)}
    hidden={i for i,line in enumerate(lines) if line.scalar('Hidden') in (True,'Y')}
    dependents={}
    for i,line in enumerate(lines):
        for end in (1,2):
            mode=line.scalar('ConnectMode'+str(end))
            key=int(line.scalar('Connect'+str(end)))
            if mode==0:
                component=component_keys.get(key)
                if component is None:
                    raise ValueError(f'{line.path}: missing attached component {key}')
                if component.scalar('Type')==1:
                    hidden.add(i)
            elif mode==1:
                target=line_keys.get(key)
                if target is None:
                    raise ValueError(f'{line.path}: missing attached wire {key}')
                dependents.setdefault(target,set()).add(i)
    pending=list(hidden)
    while pending:
        for index in dependents.get(pending.pop(),()):
            if index not in hidden:
                hidden.add(index)
                pending.append(index)
    return [i in hidden for i in range(len(lines))]


def update_wire_visibility(schematic):
    """Apply the loaded HidePower setting to current wire visibility."""
    components=schematic.one('Components').children('Part')
    hide=schematic.scalar('HidePower') in (True,'Y')
    for net in schematic.select('Nets/Net'):
        for line,hidden in zip(net.one('Lines').children('Line'),
                               net_wire_visibility(net,components,hide_power=hide)):
            field=line.one('Hidden')
            if field.values[0]!=hidden:
                field.set_values(hidden)
