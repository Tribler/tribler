from __future__ import absolute_import

from datetime import datetime
from struct import unpack

from ipv8.database import database_blob

from pony import orm
from pony.orm import db_session

from six import text_type

from Tribler.Core.Category.Category import default_category_filter
from Tribler.Core.Category.FamilyFilter import default_xxx_filter
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import COMMITTED, LEGACY_ENTRY
from Tribler.Core.Modules.MetadataStore.serialization import EPOCH, REGULAR_TORRENT, TorrentMetadataPayload
from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url
from Tribler.Core.Utilities.unicode import hexlify

NULL_KEY_SUBST = b"\00"


# This function is used to devise id_ from infohash in deterministic way. Used in FFA channels.
def infohash_to_id(infohash):
    return abs(unpack(">q", infohash[:8])[0])


def tdef_to_metadata_dict(tdef):
    """
    Helper function to create a TorrentMetadata-compatible dict from TorrentDef
    """
    # We only want to determine the type of the data. XXX filtering is done by the receiving side
    tags = default_category_filter.calculateCategory(tdef.metainfo, tdef.get_name_as_unicode())
    try:
        torrent_date = datetime.fromtimestamp(tdef.get_creation_date())
    except ValueError:
        torrent_date = EPOCH

    return {
        "infohash": tdef.get_infohash(),
        "title": tdef.get_name_as_unicode()[:300],  # TODO: do proper size checking based on bytes
        "tags": tags[:200],  # TODO: do proper size checking based on bytes
        "size": tdef.get_length(),
        "torrent_date": torrent_date if torrent_date >= EPOCH else EPOCH,
        "tracker_info": get_uniformed_tracker_url((tdef.get_tracker() or b'').decode('utf-8')) or '',
    }


def define_binding(db):
    class TorrentMetadata(db.MetadataNode):
        """
        This ORM binding class is intended to store Torrent objects, i.e. infohashes along with some related metadata.
        """

        _discriminator_ = REGULAR_TORRENT

        # Serializable
        infohash = orm.Required(database_blob, index=True)
        size = orm.Optional(int, size=64, default=0, index=True)
        torrent_date = orm.Optional(datetime, default=datetime.utcnow, index=True)
        tracker_info = orm.Optional(str, default='')

        orm.composite_key(db.ChannelNode.public_key, db.ChannelNode.origin_id, infohash)

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
                kwargs["health"] = db.TorrentState.get(infohash=kwargs["infohash"]) or db.TorrentState(
                    infohash=kwargs["infohash"]
                )
            if 'xxx' not in kwargs:
                kwargs["xxx"] = default_xxx_filter.isXXXTorrentMetadataDict(kwargs)

            super(TorrentMetadata, self).__init__(*args, **kwargs)

            if 'tracker_info' in kwargs:
                self.add_tracker(kwargs["tracker_info"])

        def add_tracker(self, tracker_url):
            sanitized_url = get_uniformed_tracker_url(tracker_url)
            if sanitized_url:
                tracker = db.TrackerState.get(url=sanitized_url) or db.TrackerState(url=sanitized_url)
                self.health.trackers.add(tracker)

        def before_update(self):
            self.add_tracker(self.tracker_info)

        def get_magnet(self):
            return ("magnet:?xt=urn:btih:%s&dn=%s" % (hexlify(self.infohash), self.title)) + (
                "&tr=%s" % self.tracker_info if self.tracker_info else ""
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
            ih_blob = database_blob(ffa_dict["infohash"])
            pk_blob = database_blob(b"")
            if cls.exists(lambda g: (g.infohash == ih_blob) or (g.id_ == id_ and g.public_key == pk_blob)):
                return None
            # Add the torrent as a free-for-all entry if it is unknown to GigaChannel
            return cls.from_dict(dict(ffa_dict, public_key=b'', status=COMMITTED, id_=id_))

        @classmethod
        @db_session
        def get_random_torrents(cls, limit):
            """
            Return some random torrents from the database.
            """
            return TorrentMetadata.select(
                lambda g: g.metadata_type == REGULAR_TORRENT and g.status != LEGACY_ENTRY
            ).random(limit)

        @db_session
        def to_simple_dict(self, include_trackers=False):
            """
            Return a basic dictionary with information about the channel.
            """
            simple_dict = super(TorrentMetadata, self).to_simple_dict()
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

            if include_trackers:
                simple_dict['trackers'] = [tracker.url for tracker in self.health.trackers]

            return simple_dict

        def metadata_conflicting(self, b):
            # Check if metadata in the given dict has conflicts with this entry
            # WARNING! This does NOT check the INFOHASH
            a = self.to_dict()
            for comp in ["title", "size", "tags", "torrent_date", "tracker_info"]:
                if (comp not in b) or (text_type(a[comp]) == text_type(b[comp])):
                    continue
                return True
            return False

        @classmethod
        @db_session
        def get_with_infohash(cls, infohash):
            return cls.select(lambda g: g.infohash == database_blob(infohash)).first()

        @classmethod
        @db_session
        def get_torrent_title(cls, infohash):
            md = cls.get_with_infohash(infohash)
            return md.title if md else None

    return TorrentMetadata
