"""Numeric views used for derived calculations."""


def calculation_number(node, index=0):
    """Read the current numeric value for a floating-point calculation."""
    return float(node.arguments[index].value)
