"""Editable public schematic simulator settings."""
from .model import Element


def default_simulator():
    """Default simulator."""
    result=Element('ssimulator')
    result.add('tp',0)
    result.add('signals',0)
    for name,count in [('sim_ac',4),('sim_dc',11),('sim_tran',3),('sim_noise',8)]:
        values=result.add(name,count)
        for index in range(count):
            values.add('pt','-' if name=='sim_dc' and index==5 else '#')
    result.add('gndnum',-1)
    result.add('gndname','')
    return result
