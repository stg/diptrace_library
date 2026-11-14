"""Complete named-field coverage before adapting standalone library output."""


def check_fields(document, *, family):
    for record in document.root._record_walk(include_self=True):
        if record.schema is None:
            parent = record.parent
            if parent is not None and parent.schema is not None and record.kind in parent.schema.fields:
                continue
            raise NotImplementedError(f'{record.path}: unimplemented {family} output record')
        for child in record.children():
            if child.kind not in record.schema.fields and child.kind not in record.schema.children:
                raise NotImplementedError(f'{child.path}: unimplemented {family} output field')
