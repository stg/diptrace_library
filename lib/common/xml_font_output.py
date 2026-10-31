"""Generate XML compatibility font fields from the authoritative model size."""
from .font_codec import compatibility_size
from .xml import set_attribute


def project_size(source, target, *, size='FontSize', legacy='FontSize',
                 floating='FontSizeFloat', mono='FontMono', fractional=True, attribute=True):
    """The family adapter chooses whether fractional and monospace fields exist."""
    emit = set_attribute if attribute else lambda parent, name, value: parent.set_field(name, value)
    value = source.scalar(size)
    # Generate integer syntax even when an equal Decimal retains a fraction.
    if (previous := target.child(legacy)) is not None:
        previous.set_values()
    emit(target, legacy, compatibility_size(value))
    if fractional:
        emit(target, floating, value)
        if mono:
            emit(target, 'FontMono', source.scalar(mono, False))
