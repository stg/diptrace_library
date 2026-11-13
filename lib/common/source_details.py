"""Optional source positions/spelling, separate from authored design facts."""
from .model import Value
from .element_storage import RecordItems, _kind


def discard_source(root):
    """Drop provenance after import consumed all source-dependent syntax."""
    for node in root._record_walk(include_self=True):
        node._source = node._syntax = None
        content = node._content
        if type(content) is RecordItems:
            for slot, detail in list(content.details.items()):
                detail.source = None
                value = content.storage._values[slot]
                values = value if content.storage.layout.definitions[slot].kind == 'tuple' else (value,)
                metadata = tuple((item[0], item[1], None, None)
                                 if item is not None and (item[1] or index < len(values)
                                     and item[0] != _kind(values[index])) else None
                                 for index, item in enumerate(detail.arguments))
                detail.arguments = metadata if any(item is not None for item in metadata) else ()
                if detail.notes is None and not detail.arguments:
                    del content.details[slot]
            items = content.order
        else:
            items = content
        for index, value in enumerate(items):
            if isinstance(value, Value) and (value.source is not None or value.lexeme is not None):
                items[index] = Value(value.value, value.kind, value.unit)
    return root
