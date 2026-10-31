"""Public XML assembly names and placed-component exclusion positions."""


def read_variants(record, board):
    variants = board.add('AssemblyVariants')
    for item in record.rows('AssemblyVariants', 'AssemblyVariant'):
        value = item.content()
        if value.kind != 'string':
            raise ValueError(f'{item.node.path}: assembly variant requires a name')
        variants.add('AssemblyVariant', value)
        item.finish(allow_text=True)


def read_exclusions(record, component):
    collection = record.take('AssemblyExclude')
    if collection is None:
        return
    target = component.add('AssemblyExclude')
    for item in collection.children('Item'):
        value = item.content()
        if value.kind != 'number' or value.unit or type(value.value) is not int:
            raise ValueError(f'{item.node.path}: assembly exclusion requires an integer position')
        target.add('Item', value)
        item.finish(allow_text=True)
    collection.finish()
