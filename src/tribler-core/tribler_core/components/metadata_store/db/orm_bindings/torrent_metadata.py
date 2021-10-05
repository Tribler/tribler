from datetime import datetime
from struct import unpack

from pony import orm
from pony.orm import db_session

from tribler_core.components.metadata_store.category_filter.category import default_category_filter
from tribler_core.components.metadata_store.category_filter.family_filter import default_xxx_filter
from tribler_core.components.metadata_store.db.orm_bindings.channel_node import COMMITTED
from tribler_core.components.metadata_store.db.serialization import EPOCH, REGULAR_TORRENT, TorrentMetadataPayload
from tribler_core.utilities.tracker_utils import get_uniformed_tracker_url
from tribler_core.utilities.unicode import ensure_unicode, hexlify

NULL_KEY_SUBST = b"\00"


# This function is used to devise id_ from infohash in deterministic way. Used in FFA channels.
def infohash_to_id(infohash):
    return abs(unpack(">q", infohash[:8])[0])


def tdef_to_metadata_dict(tdef):
    """
    Helper function to create a TorrentMetadata-compatible dict from TorrentDef
    """
    # We only want to determine the type of the data. XXX filtering is done by the receiving side
    try:
        tags = default_category_filter.calculateCategory(tdef.metainfo, tdef.get_name_as_unicode())
    except UnicodeDecodeError:
        tags = "Unknown"

    try:
        torrent_date = datetime.fromtimestamp(tdef.get_creation_date())
    except ValueError:
        torrent_date = EPOCH

    return {
        "infohash": tdef.get_infohash(),
        "title": tdef.get_name_as_unicode()[:300],
        "tags": tags[:200],
        "size": tdef.get_length(),
        "torrent_date": torrent_date if torrent_date >= EPOCH else EPOCH,
        "tracker_info": get_uniformed_tracker_url(ensure_unicode(tdef.get_tracker() or '', 'utf-8')) or '',
    }


def define_binding(db):
    class TorrentMetadata(db.MetadataNode):
        """
        This ORM binding class is intended to store Torrent objects, i.e. infohashes along with some related metadata.
        """

        _discriminator_ = REGULAR_TORRENT

        # Serializable
        infohash = orm.Required(bytes, index=True)
        size = orm.Optional(int, size=64, default=0)
        torrent_date = orm.Optional(datetime, default=datetime.utcnow, index=True)
        tracker_info = orm.Optional(str, default='')

        # Local
        xxx = orm.Optional(float, default=0)
        health = orm.Optional('TorrentState', reverse='metadata')

        # Special class-level properties
        _payload_class = TorrentMetadataPayload
        payload_arguments = _payload_class.__init__.__code__.co_varnames[
            : _payload_class.__init__.__code__.co_argcount
        ][1:]
        nonpersonal_attributes = db.MetadataNode.nonpersonal_attributes + (
            'infohash',
            'size',
            'torrent_date',
            'tracker_info',
        )

        def __init__(self, *args, **kwargs):
            if "health" not in kwargs and "infohash" in kwargs:
                infohash = kwargs["infohash"]
                health = db.TorrentState.get_for_update(infohash=infohash) or db.TorrentState(infohash=infohash)
                kwargs["health"] = health
            if 'xxx' not in kwargs:
                kwargs["xxx"] = default_xxx_filter.isXXXTorrentMetadataDict(kwargs)

            super().__init__(*args, **kwargs)

            if 'tracker_info' in kwargs:
                self.add_tracker(kwargs["tracker_info"])

        def add_tracker(self, tracker_url):
            sanitized_url = get_uniformed_tracker_url(tracker_url)
            if sanitized_url:
                tracker = db.TrackerState.get_for_update(url=sanitized_url) or db.TrackerState(url=sanitized_url)
                self.health.trackers.add(tracker)

        def before_update(self):
            self.add_tracker(self.tracker_info)

        def get_magnet(self):
            return (f"magnet:?xt=urn:btih:{hexlify(self.infohash)}&dn={self.title}") + (
                f"&tr={self.tracker_info}" if self.tracker_info else ""
            )

        @classmethod
        @db_session
        def add_ffa_from_dict(cls, ffa_dict):
            # To produce a relatively unique id_ we take some bytes of the infohash and convert these to a number.
            # abs is necessary as the conversion can produce a negative value, and we do not support that.
            id_ = infohash_to_id(ffa_dict["infohash"])
            # Check that this torrent is yet unknown to GigaChannel, and if there is no duplicate FFA entry.
            # Test for a duplicate id_+public_key is necessary to account for a (highly improbable) situation when
            # two entries have different infohashes but the same id_. We do not want people to exploit this.
            ih_blob = ffa_dict["infohash"]
            pk_blob = b""
            if cls.exists(lambda g: (g.infohash == ih_blob) or (g.id_ == id_ and g.public_key == pk_blob)):
                return None
            # Add the torrent as a free-for-all entry if it is unknown to GigaChannel
            return cls.from_dict(dict(ffa_dict, public_key=b'', status=COMMITTED, id_=id_))

        @db_session
        def to_simple_dict(self):
            """
            Return a basic dictionary with information about the channel.
            """
            simple_dict = super().to_simple_dict()
            epoch = datetime.utcfromtimestamp(0)
            simple_dict.update(
                {
                    "infohash": hexlify(self.infohash),
                    "size": self.size,
                    "num_seeders": self.health.seeders,
                    "num_leechers": self.health.leechers,
                    "last_tracker_check": self.health.last_check,
                    "updated": int((self.torrent_date - epoch).total_seconds()),
                }
            )

            return simple_dict

        def metadata_conflicting(self, b):
            # Check if metadata in the given dict has conflicts with this entry
            # WARNING! This does NOT check the INFOHASH
            a = self.to_dict()
            for comp in ["title", "size", "tags", "torrent_date", "tracker_info"]:
                if (comp not in b) or (str(a[comp]) == str(b[comp])):
                    continue
                return True
            return False

        @classmethod
        @db_session
        def get_with_infohash(cls, infohash):
            return cls.select(lambda g: g.infohash == infohash).first()

        @classmethod
        @db_session
        def get_torrent_title(cls, infohash):
            md = cls.get_with_infohash(infohash)
            return md.title if md else None

        def serialized_health(self) -> bytes:
            health = self.health
            if not health or (not health.seeders and not health.leechers and not health.last_check):
                return b';'
            return b'%d,%d,%d;' % (health.seeders or 0, health.leechers or 0, health.last_check or 0)

    return TorrentMetadata
