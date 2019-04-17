import collections

Location = collections.namedtuple('Location', ['lat', 'lng'])
Relation = collections.namedtuple(
    'Relation', ['other_event', 'distance', 'timedelta'])
