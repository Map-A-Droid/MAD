import collections

Location = collections.namedtuple('Location', ['lat', 'lng'])
Relation = collections.namedtuple(
    'Relation', ['other_event', 'distance', 'timedelta'])
Trash = collections.namedtuple('Trash', ['x', 'y'])
