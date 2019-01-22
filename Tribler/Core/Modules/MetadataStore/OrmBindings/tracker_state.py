from pony import orm

from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url, MalformedTrackerURLException


def define_binding(db):
    class TrackerState(db.Entity):
        rowid = orm.PrimaryKey(int, auto=True)
        url = orm.Required(str, unique=True)
        last_check = orm.Optional(int, size=64, default=0)
        alive = orm.Optional(bool, default=True)
        torrents = orm.Set('TorrentState', reverse='trackers')
        failures = orm.Optional(int, size=32, default=0)

        def __init__(self, *args, **kwargs):
            # Sanitize and canonicalize the tracker URL
            sanitized = get_uniformed_tracker_url(kwargs['url'])
            if sanitized:
                kwargs['url'] = sanitized
            else:
                raise MalformedTrackerURLException("Could not canonicalize tracker URL (%s)" % kwargs['url'])

            super(TrackerState, self).__init__(*args, **kwargs)

    return TrackerState
