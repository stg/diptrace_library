"""Temporary typed inputs while decoding older drawing representations.

Complete imports remove these after modernization establishes current geometry
and text. They are not properties of a complete shared design.
"""


def stored_data(parent):
    node = parent.child('StoredData')
    if node is None:
        node = parent.add('StoredData')
        node.annotations['asc_omit'] = 'temporary drawing decoding inputs'
    return node
