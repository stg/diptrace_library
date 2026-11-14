"""Named semantic assertions shared by portable standalone format tests."""
from lib.common.model import Element
from lib.common.schema import MISSING


def snapshot(document):
    facts = {}
    for node in document.root.walk(include_self=True):
        if node.schema is None:
            continue
        for name, definition in node.schema.fields.items():
            if definition.getter is None and node.child(name) is None and definition.default is MISSING:
                continue
            value = node.get(name, None if definition.default is MISSING else definition.default)
            facts[node.path+'/'+name] = (definition.kind, value.path if isinstance(value, Element) else value)
    return facts


def assert_equivalent(self, before, output):
    after = snapshot(output)
    self.assertEqual(before.keys(), after.keys())
    for name, (kind, value) in before.items():
        if kind == 'number':
            self.assertAlmostEqual(value, after[name][1], delta=.0001, msg=name)
        else:
            self.assertEqual((kind, value), after[name], name)
