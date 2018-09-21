import os
from datetime import datetime

from libtorrent import file_storage, add_files, create_torrent, set_piece_hashes, bencode, torrent_info
from pony import orm

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Modules.MetadataStore.serialization import serialize_metadata_gossip, MetadataTypes
from Tribler.Core.TorrentDef import TorrentDef

CHANNEL_DIR_NAME_LENGTH = 60  # Its not 40 so it could be distinguished from infohash
BLOB_EXTENSION = '.mdblob'

def define_binding(db):
    class ChannelMD(db.TorrentMD):
        _discriminator_ = MetadataTypes.CHANNEL_TORRENT.value
        version = orm.Optional(int, size=64, default=0)
        subscribed = orm.Optional(bool, default=False)
        votes = orm.Optional(int, size=64, default=0)

        @classmethod
        def from_dict(cls, key, md_dict):
            return super(ChannelMD, cls).from_dict(key, md_dict)

        def update_metadata(self, key, update_dict=None):
            now = datetime.utcnow()
            channel_dict = self.to_dict()
            channel_dict.update(update_dict or {})
            channel_dict.update({"size": len(self.contents_list),
                                 "timestamp": now,
                                 "torrent_date": now})
            serialize_metadata_gossip(channel_dict, key)
            self.set(**channel_dict)

        @property
        def contents_list(self):
            return self.contents[:]

        @property
        def contents(self):
            return db.TorrentMD.select(
                lambda g: g.public_key == self.public_key and g != self)

        @property
        def newer_entries(self):
            return db.SignedGossip.select(
                lambda g: g.timestamp > self.timestamp and g.public_key == self.public_key)

        @property
        def older_entries(self):
            return db.SignedGossip.select(
                lambda g: g.timestamp < self.timestamp and g.public_key == self.public_key)

        def garbage_collect(self):
            orm.delete(g for g in self.older_entries if g.type == MetadataTypes.DELETED.value)

        @property
        def get_dirname(self):
            # Have to limit this to support Windows file path length limit
            return str(self.public_key).encode('hex')[-CHANNEL_DIR_NAME_LENGTH:]

        def seed(self, channels_dir, lm):
            torrent_filename = os.path.join(channels_dir, self.get_dirname + ".torrent")
            tdef = TorrentDef.load(torrent_filename)
            dcfg = DownloadStartupConfig()
            dcfg.set_dest_dir(channels_dir)
            lm.add(tdef, dcfg, hidden=False)

        def commit_to_torrent(self, key, seeding_dir, md_list=None, buf_list=None):
            buf_list = buf_list or []
            buf_list.extend([e.serialized() for e in md_list or []])

            (infohash, version) = create_channel_torrent(
                seeding_dir, self.get_dirname, buf_list, self.version)

            self.update_metadata(key, update_dict={"infohash": infohash, "version": version})
            self.garbage_collect()
    return ChannelMD


def create_channel_torrent(channels_dir, name, buf_list, version):
    # Create dir for metadata files
    channel_dir = os.path.abspath(os.path.join(channels_dir, name))
    if not os.path.isdir(channel_dir):
        os.makedirs(channel_dir)

    # TODO: Smash together new metadata entries belonging to a single update into one giant file-blob
    # Write serialized and signed metadata into files
    for buf in buf_list:
        version += 1
        with open(os.path.join(channel_dir, str(version).zfill(9) + BLOB_EXTENSION), 'wb') as f:
            f.write(buf)

    # Make torrent out of dir with metadata files
    infohash = create_torrent_from_dir(channel_dir,
        os.path.join(channels_dir, name + ".torrent"))
    return infohash, version

def create_torrent_from_dir(directory, torrent_filename):
    fs = file_storage()
    add_files(fs, directory)
    t = create_torrent(fs)
    # For a torrent created with flags=19 with 200+ small files
    # libtorrent client_test can't see its files on disk.
    # optimize_alignment + merkle + mutable_torrent_support = 19
    # t = create_torrent(fs, flags=19) # BUG?
    t.set_priv(False)
    set_piece_hashes(t, os.path.dirname(directory))
    torrent = t.generate()
    with open(torrent_filename, 'wb') as f:
        f.write(bencode(torrent))

    infohash = torrent_info(torrent).info_hash().to_bytes()
    return infohash
