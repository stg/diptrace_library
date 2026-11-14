"""One XML export's local keys, separate from current editable identities."""
from .conversion import warn
from .local_keys import public_keys
from . import unplaced_footprint_records as physical


def _warn(owner, destination, report):
    warn(report, 'unresolved-local-reference', destination,
         'A local selection has no available target.', (owner,),
         recoverability='its missing key remains in output; allocated keys avoid unrelated targets')


class GroupKeys:
    def __init__(self, owner, collection, members, *, destination, report=None):
        self.destination, self.report = destination, report
        self.keys = public_keys(owner.select(collection+'/pt'),
            (node['UnresolvedGroupId'] for node in members if node.child('UnresolvedGroupId') is not None))

    def key(self, group):
        return self.keys[group._ordinal()]

    def selection(self, owner):
        if (missing := owner.get('UnresolvedGroupId')) is not None:
            _warn(owner, self.destination, self.report)
            return missing
        key = owner['GroupId']
        return -1 if key < 0 else self.keys[key]


class PhysicalKeys:
    def __init__(self, pattern, *, pins=(), destination, report=None):
        self.destination, self.report = destination, report
        pads = pattern.select('Pads/Pad') if pattern is not None else ()
        shapes = pattern.select('Shapes/Shape') if pattern is not None else ()
        holes = pattern.select('Holes/Hole') if pattern is not None else ()
        dimensions = pattern.select('Dimensions/Dimension') if pattern is not None else ()
        pairs = pattern.select('InternalConnections/IntCon') if pattern is not None else ()
        reserved = {0: set(), 1: set(), 2: set()}
        self.missing_members, self.issues = set(), {}
        for owner in (*pins, *shapes):
            if (key := owner.get('UnresolvedPadId')) is not None:
                reserved[0].add(key)
        for pair in pairs:
            reserved[0].update(pair[name] for name in ('UnresolvedX', 'UnresolvedY') if pair.child(name) is not None)
        document = pattern._owner() if pattern is not None else None
        for dimension in dimensions:
            for issue in document.references._source_issues(dimension):
                role = issue.message.partition(':')[0]
                if role not in physical.DIMENSION_ROLES:
                    continue
                side = role[-1]
                self.issues[dimension, side] = issue
                mode = dimension['Connected'+side]
                if mode in (0, 1, 2):
                    missing_member = mode != 1 or not any(scope.kind == 'Points_New' for scope in issue.collections or ())
                    if missing_member:
                        self.missing_members.add((dimension, side))
                        reserved[mode].add(dimension['SubObject'+side])
        self.members = {mode: public_keys(rows, reserved[mode], start=1)
                        for mode, rows in ((0, pads), (1, shapes), (2, holes))}
        self.groups = (GroupKeys(pattern, 'Pattern_Groups', (*pads, *shapes, *holes, *dimensions),
                                destination=destination, report=report) if pattern is not None else None)

    def pad(self, pad):
        return self.members[0][pad._ordinal()+1]

    def shape(self, shape):
        return self.members[1][shape._ordinal()+1]

    def hole(self, hole):
        return self.members[2][hole._ordinal()+1]

    def pad_selection(self, owner):
        if (missing := owner.get('UnresolvedPadId')) is not None:
            _warn(owner, self.destination, self.report)
            return missing
        selected = owner['PadId']
        return -1 if selected < 0 else self.members[0][selected]

    def connection(self, pair):
        result = []
        for name in ('X', 'Y'):
            if pair.child('Unresolved'+name) is not None:
                result.append(pair['Unresolved'+name])
                _warn(pair, self.destination, self.report)
            else:
                key = pair[name]
                result.append(-1 if key < 0 else self.members[0][key])
        return tuple(result)

    def attachments(self, dimension):
        result = []
        for side in ('1', '2'):
            mode, owner, member, point = (dimension[name+side] for name in ('Connected', 'Object', 'SubObject', 'Point'))
            if mode >= 4:
                raise NotImplementedError('dimension mode has no standalone XML mapping')
            if (dimension, side) in self.issues:
                _warn(dimension, self.destination, self.report)
            if mode in self.members and member >= 0 and (dimension, side) not in self.missing_members:
                member = self.members[mode][member]
            # Terminal owners and vertices are positional in library XML, so
            # their existing graph-maintained selectors do not use public keys.
            result.append((mode, owner, member, point))
        return tuple(result)
