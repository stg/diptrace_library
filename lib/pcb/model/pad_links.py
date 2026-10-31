"""Placed-pad references and their derived component/position views."""
from ...common.schema import Field
from .membership import component_of, component_inputs
from .relationships import linked, reference_field


def pad_fields(end, role):
    def pad(row):
        return linked(row, role)

    def component(row):
        target = pad(row)
        return component_of(target) if target is not None else None

    dependencies = lambda row: ((row, role, 'outgoing'),)
    return {
        'Pad'+str(end): reference_field('Pad'+str(end), role),
        'Component'+str(end): Field('Component'+str(end), 'reference', nullable=True,
            getter=component, ordinal_dependencies=lambda row: component_inputs(pad(row)),
            reference_dependencies=dependencies),
        'ComponentIndex'+str(end): Field('ComponentIndex'+str(end), 'integer',
            getter=lambda row: owner._ordinal() if (owner := component(row)) is not None else -1,
            ordinal_dependencies=lambda row: component_inputs(pad(row)),
            reference_dependencies=dependencies),
        'PadIndex'+str(end): Field('PadIndex'+str(end), 'integer',
            getter=lambda row: target._ordinal() if (target := pad(row)) is not None else -1,
            ordinal_dependencies=lambda row: (target,) if (target := pad(row)) is not None else (),
            reference_dependencies=dependencies),
    }
