import os
from datetime import datetime
from libtorrent import add_files, bencode, create_torrent, file_storage, set_piece_hashes, torrent_info

from pony import orm
from pony.orm import db_session

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Modules.MetadataStore.serialization import serialize_metadata_gossip, deserialize_metadata_gossip, \
    MetadataTypes
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo

CHANNELS_DIR_RELATIVE_PATH = "channels"
CHANNEL_DIR_NAME_LENGTH = 60  # Its not 40 to be distinct from infohash
BLOB_EXTENSION = '.mdblob'


def define_channel_md(db):
    class ChannelMD(db.TorrentMD):
        _discriminator_ = MetadataTypes.CHANNEL_TORRENT.value
        version = orm.Optional(int, size=64, default=0)
        subscribed = orm.Optional(bool, default=False)
        votes = orm.Optional(int, size=64, default=0)

        @classmethod
        def from_dict(cls, key, md_dict):
            return super(ChannelMD, cls).from_dict(key, md_dict)

        def commit_to_torrent(
                self,
                key,
                seeding_dir,
                update_dict=None,
                md_list=None,
                buf_list=None):
            # TODO: split this into update_metadata and commit_to_torrent?
            buf_list = buf_list or []
            buf_list.extend([e.serialized() for e in md_list or []])

            (infohash, version) = create_channel_torrent(
                seeding_dir, self.get_dirname(), buf_list, self.version)
            # TODO: do not recreate the torrent when its contents don't change
            now = datetime.utcnow()
            channel_dict = self.to_dict()
            channel_dict.update(update_dict or {})
            channel_dict.update({"infohash": infohash,
                                 "size": len(self.list_contents()),
                                 "timestamp": now,
                                 "version": version,
                                 "torrent_date": now})
            serialize_metadata_gossip(channel_dict, key)
            self.set(**channel_dict)
            self.garbage_collect()

        def list_contents(self):
            return db.TorrentMD.select(
                lambda g: g.public_key == self.public_key and g != self)[:]

        # TODO: use some timer independent way to get determine newer entries?
        # Could try do this based on entry id, since it is increase monotonically
        def newer_entries(self):
            return db.SignedGossip.select(
                lambda g: g.timestamp > self.timestamp and g.public_key == self.public_key)[:]

        def older_entries(self):
            return db.SignedGossip.select(
                lambda g: g.timestamp < self.timestamp and g.public_key == self.public_key)[:]

        def get_dirname(self):
            # Have to limit this to support Windows file path length limit
            return str(self.public_key).encode('hex')[-CHANNEL_DIR_NAME_LENGTH:]

        # TODO: Pony ver. 0.7.4 introduces hybrid methods to optimize this
        def garbage_collect(self):
            for g in self.older_entries():
                if g.type == MetadataTypes.DELETED.value:
                    g.delete()


def create_torrent_from_dir(directory, torrent_filename):
    fs = file_storage()
    add_files(fs, directory)
    t = create_torrent(fs)
    # FIXME: for a torrent created with flags=19 with 200+ small files
    # libtorrent client_test can't see its files on disk.
    # optimize_alignment + merke + mutable_torrent_support = 19
    # t = create_torrent(fs, flags=19) # BUG?
    t.set_priv(False)
    set_piece_hashes(t, os.path.dirname(directory))
    torrent = t.generate()
    with open(torrent_filename, 'wb') as f:
        f.write(bencode(torrent))

    infohash = torrent_info(torrent).info_hash().to_bytes()
    return infohash


def create_channel_torrent(channels_store_dir, title, buf_list, version):
    # Create dir for metadata files
    channel_dir = os.path.abspath(os.path.join(channels_store_dir, title))
    if not os.path.isdir(channel_dir):
        os.makedirs(channel_dir)

    # TODO: Smash together new metadata entries belonging to a single update into one giant file-blob
    # Write serialized and signed metadata into files
    for buf in buf_list:
        version += 1
        with open(os.path.join(channel_dir, str(version).zfill(9)+BLOB_EXTENSION), 'wb') as f:
            f.write(buf)

    # Make torrent out of dir with metadata files
    torrent_filename = os.path.join(channels_store_dir, title + ".torrent")
    infohash = create_torrent_from_dir(channel_dir, torrent_filename)

    return infohash, version


@db_session
def process_channel_dir(db, dirname, start_num=0):
    for filename in sorted(os.listdir(dirname)):
        full_filename = os.path.join(dirname, filename)
        try:
            if filename.endswith(BLOB_EXTENSION):
                num = int(filename[:-len(BLOB_EXTENSION)])
                if num < 0:
                    raise NameError
            else:
                raise NameError
        except (ValueError, NameError):
            raise NameError('Wrong blob filename in channel dir:', full_filename)
        if num >= start_num:
            load_blob(db, full_filename)


# TODO: this should probably be moved to either the torrent manager, or ChannelMD method
def download_channel(session, infohash, title):
    dcfg = DownloadStartupConfig()
    dcfg.set_dest_dir(session.channels_dir)
    tdef = TorrentDefNoMetainfo(infohash=str(infohash), name=title)
    download = session.start_download_from_tdef(tdef, dcfg)

    def err(f):
        print ("we got an exception: %s" % (f.getTraceback(),))
        f.trap(RuntimeError)

    # FIXME! Twisted eats all error messages here!
    download.deferred_finished.addErrback(err)
    download.deferred_finished.addCallback(
        lambda handle: process_channel_dir(
            session.mds, handle.get_content_dest()))
    return download.deferred_finished


@db_session
def load_blob(db, filename):
    with open(filename, 'rb') as f:
        gsp = deserialize_metadata_gossip(f.read())
        # TODO: add various gossip blob checks here
        if db.SignedGossip.exists(signature=gsp["signature"]):
            # We already have this gossip.
            return db.SignedGossip.get(signature=gsp["signature"])
        if gsp["type"] == MetadataTypes.DELETED.value:
            # We only allow people to delete their own entries, thus PKs must
            # match
            md = db.SignedGossip.get(
                signature=gsp["delete_signature"],
                public_key=gsp["public_key"])
            if md:
                md.delete()
            # FIXME: return some temporary object here?
            return None
        elif gsp["type"] == MetadataTypes.REGULAR_TORRENT.value:
            return db.TorrentMD(**gsp)
        elif gsp["type"] == MetadataTypes.CHANNEL_TORRENT.value:
            return db.ChannelMD(**gsp)
        return None
