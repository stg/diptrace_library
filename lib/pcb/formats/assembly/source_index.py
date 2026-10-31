"""Temporary source-key lookup, separate from the records being imported."""
from collections.abc import Mapping

from ..errors import PcbError


class SourceIndex(Mapping):
    """Retain every record and require an unambiguous key only on lookup.

    Source numbers are consumed during import. They are not the identities of
    current model objects; an unused repeated number must not merge those objects.
    """
    def __init__(self, entries, label):
        self.entries = tuple(entries)
        self.records = tuple(record for _, record in self.entries)
        self.label = label
        self._choices = {}
        for key, record in self.entries:
            self._choices.setdefault(key, []).append(record)

    def __getitem__(self, key):
        choices = self._choices[key]
        if len(choices) != 1:
            raise PcbError(f'ambiguous saved {self.label} reference {key}')
        return choices[0]

    def __iter__(self):
        return iter(self._choices)

    def __len__(self):
        return len(self._choices)

    @property
    def repeated_keys(self):
        return tuple(key for key, records in self._choices.items() if len(records) > 1)
