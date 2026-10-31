"""Temporary XML keys terminate at the import boundary."""
from ..errors import PcbError


def position(key, choices, *, label, path):
    if key == -1:
        return -1
    target = choices.get(key)
    if target is None:
        raise PcbError(f'{path}: unresolved {label} {key}')
    return target._ordinal()


def unique_id(record, choices, *, label):
    key = record.integer('Id')
    if key < 0 or key in choices:
        raise PcbError(f'{record.node.path}: invalid or duplicate {label} Id {key}')
    return key


def pad_position(component, number, placements):
    placement = placements.get(component)
    if placement is None or number not in placement.pad_positions:
        raise PcbError(f'unresolved XML pad reference ({component}, {number})')
    return placement.pad_positions[number]
