from __future__ import absolute_import, division

import math
import os
import random
import sys
from binascii import hexlify
from datetime import datetime

from ipv8.database import database_blob

from libtorrent import add_files, bencode, create_torrent, file_storage, set_piece_hashes, torrent_info

import lz4.frame

from pony import orm
from pony.orm import db_session, raw_sql, select

from Tribler.Core.Category.Category import default_category_filter
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import COMMITTED, LEGACY_ENTRY, NEW, PUBLIC_KEY_LEN, \
    TODELETE, UPDATED
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, ChannelMetadataPayload, REGULAR_TORRENT
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url
from Tribler.Core.exceptions import DuplicateChannelIdError, DuplicateTorrentFileError

CHANNEL_DIR_NAME_LENGTH = 32  # Its not 40 so it could be distinguished from infohash
BLOB_EXTENSION = '.mdblob'
LZ4_END_MARK_SIZE = 4  # in bytes, from original specification. We don't use CRC
ROOT_CHANNEL_ID = 0


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def create_torrent_from_dir(directory, torrent_filename):
    fs = file_storage()
    add_files(fs, directory)
    t = create_torrent(fs)
    # t = create_torrent(fs, flags=17) # piece alignment
    t.set_priv(False)
    set_piece_hashes(t, os.path.dirname(directory))
    torrent = t.generate()
    with open(torrent_filename, 'wb') as f:
        f.write(bencode(torrent))

    infohash = torrent_info(torrent).info_hash().to_bytes()
    return torrent, infohash


def entries_to_chunk(metadata_list, chunk_size, start_index=0):
    """
    For efficiency reasons, this is deliberately written in C style
    :param metadata_list: the list of metadata to process.
    :param chunk_size: the desired chunk size limit, in bytes. The produced chunk's size will never exceed this value.
    :param start_index: the index of the element of metadata_list from which the processing should start.
    :return: (chunk, last_entry_index) tuple, where chunk is the resulting chunk in string form and
        last_entry_index is the index of the element of the input list that was put into the chunk the last.
    """
    # Try to fit as many blobs into this chunk as permitted by chunk_size and
    # calculate their ends' offsets in the blob

    last_entry_index = None
    with lz4.frame.LZ4FrameCompressor(auto_flush=True) as c:
        header = c.begin()
        offset = len(header)
        out_list = [header]  # LZ4 header
        for index, metadata in enumerate(metadata_list[start_index:], start_index):
            blob = c.compress(
                ''.join(metadata.serialized_delete() if metadata.status == TODELETE else metadata.serialized()))
            # Chunk size limit reached?
            if offset + len(blob) > (chunk_size - LZ4_END_MARK_SIZE):
                break
            # Now that we now it will fit in, we can safely append it
            offset += len(blob)
            last_entry_index = index
            out_list.append(blob)
        out_list.append(c.flush())  # LZ4 end mark

    chunk = ''.join(out_list)
    if last_entry_index is None:
        raise Exception('Serialized entry size > blob size limit!',
                        hexlify(str(metadata_list[start_index].signature)))
    return chunk, last_entry_index + 1


def define_binding(db):
    class ChannelMetadata(db.TorrentMetadata):
        _discriminator_ = CHANNEL_TORRENT

        # Serializable
        num_entries = orm.Optional(int, size=64, default=0)
        start_timestamp = orm.Optional(int, size=64, default=0)

        # Local
        subscribed = orm.Optional(bool, default=False)
        votes = orm.Optional(float, default=0.0)
        local_version = orm.Optional(int, size=64, default=0)

        _payload_class = ChannelMetadataPayload
        _channels_dir = None
        _category_filter = None
        _CHUNK_SIZE_LIMIT = 1 * 1024 * 1024  # We use 1MB chunks as a workaround for Python's lack of string pointers

        # VSIDS-based votes ratings
        bump_amount = 1.0
        decay_coefficient = 0.98
        rescale_threshold = 10.0**100
        vsids_last_bump = datetime.utcnow()
        vsids_exp_period = 24.0*60*60  # decay e times over this period
        vsids_total_activity = 0.0



        @db_session
        def update_metadata(self, update_dict=None):
            channel_dict = self.to_dict()
            channel_dict.update(update_dict or {})
            self.set(**channel_dict)
            self.sign()

        @classmethod
        @db_session
        def process_channel_metadata_payload(cls, payload):
            """
            Process some channel metadata.
            :param payload: The channel metadata, in serialized form.
            :return: The ChannelMetadata object that contains the latest version of the channel
            """
            channel = ChannelMetadata.get_channel_with_id(payload.public_key)
            if not channel:
                return ChannelMetadata.from_payload(payload)

            if payload.timestamp > channel.timestamp:
                channel.set(**payload.to_dict())
            return channel

        @classmethod
        @db_session
        def get_my_channel(cls):
            return ChannelMetadata.get_channel_with_id(cls._my_key.pub().key_to_bin()[10:])

        @classmethod
        @db_session
        def create_channel(cls, title, description=""):
            """
            Create a channel and sign it with a given key.
            :param title: The title of the channel
            :param description: The description of the channel
            :return: The channel metadata
            """
            if ChannelMetadata.get_channel_with_id(cls._my_key.pub().key_to_bin()[10:]):
                raise DuplicateChannelIdError()

            my_channel = cls(id_=ROOT_CHANNEL_ID, public_key=database_blob(cls._my_key.pub().key_to_bin()[10:]),
                             title=title, tags=description, subscribed=True, infohash=str(random.getrandbits(160)))
            my_channel.sign()
            return my_channel

        def consolidate_channel_torrent(self):
            """
            Delete the channel dir contents and create it anew.
            Use it to consolidate fragmented channel torrent directories.
            :param key: The public/private key, used to sign the data
            """

            self.commit_channel_torrent()

            folder = os.path.join(self._channels_dir, self.dir_name)
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                # We only remove mdblobs and leave the rest as it is
                if filename.endswith(BLOB_EXTENSION) or filename.endswith(BLOB_EXTENSION + '.lz4'):
                    os.unlink(file_path)

            # Channel should get a new starting timestamp and its contents should get higher timestamps
            start_timestamp = self._clock.tick()
            for g in self.contents:
                if g.status == COMMITTED:
                    g.status = UPDATED
                    g.timestamp = self._clock.tick()
                    g.sign()

            return self.commit_channel_torrent(new_start_timestamp=start_timestamp)

        def update_channel_torrent(self, metadata_list):
            """
            Channel torrents are append-only to support seeding the old versions
            from the same dir and avoid updating already downloaded blobs.
            :param metadata_list: The list of metadata entries to add to the torrent dir
            :return The new infohash, should be used to update the downloads
            """
            # Create dir for metadata files
            channel_dir = os.path.abspath(os.path.join(self._channels_dir, self.dir_name))
            if not os.path.isdir(channel_dir):
                os.makedirs(channel_dir)

            index = 0
            new_timestamp = self.timestamp
            while index < len(metadata_list):
                # Squash several serialized and signed metadata entries into a single file
                data, index = entries_to_chunk(metadata_list, self._CHUNK_SIZE_LIMIT, start_index=index)
                new_timestamp = self._clock.tick()
                blob_filename = str(new_timestamp).zfill(12) + BLOB_EXTENSION + '.lz4'
                with open(os.path.join(channel_dir, blob_filename), 'wb') as f:
                    f.write(data)

            # TODO: add error-handling routines to make sure the timestamp is not messed up in case of an error

            # Make torrent out of dir with metadata files
            torrent, infohash = create_torrent_from_dir(channel_dir,
                                                        os.path.join(self._channels_dir, self.dir_name + ".torrent"))
            torrent_date = datetime.utcfromtimestamp(torrent['creation date'])

            return {"infohash": infohash, "num_entries": self.contents_len,
                    "timestamp": new_timestamp, "torrent_date": torrent_date}, torrent

        def commit_channel_torrent(self, new_start_timestamp=None):
            """
            Collect new/uncommitted and marked for deletion metadata entries, commit them to a channel torrent and
            remove the obsolete entries if the commit succeeds.
            :return The new infohash, should be used to update the downloads
            """
            torrent = None
            md_list = self.staged_entries_list
            if not md_list:
                return None

            try:
                update_dict, torrent = self.update_channel_torrent(md_list)
            except IOError:
                self._logger.error(
                    "Error during channel torrent commit, not going to garbage collect the channel. Channel %s",
                    hexlify(str(self.public_key)))
            else:
                if new_start_timestamp:
                    update_dict['start_timestamp'] = new_start_timestamp
                self.update_metadata(update_dict)
                self.local_version = self.timestamp
                # Change status of committed metadata and clean up obsolete TODELETE entries
                for g in md_list:
                    if g.status in [NEW, UPDATED]:
                        g.status = COMMITTED
                    elif g.status == TODELETE:
                        g.delete()

                # Write the channel mdblob to disk
                self.to_file(os.path.join(self._channels_dir, self.dir_name + BLOB_EXTENSION))

                self._logger.info("Channel %s committed with %i new entries. New version is %i",
                                  hexlify(str(self.public_key)), len(md_list), update_dict['timestamp'])
            return torrent

        @db_session
        def get_torrent(self, infohash):
            """
            Return the torrent with a provided infohash.
            :param infohash: The infohash of the torrent to search for
            :return: TorrentMetadata if the torrent exists in the channel, else None
            """
            return db.TorrentMetadata.get(public_key=self.public_key, infohash=infohash)

        @db_session
        def torrent_exists(self, infohash):
            """
            Return True if torrent with given infohash exists in the user channel
            :param infohash: The infohash of the torrent
            :return: True if torrent exists else False
            """
            return db.TorrentMetadata.exists(lambda g: g.metadata_type == REGULAR_TORRENT
                                             and g.status != LEGACY_ENTRY
                                             and g.public_key == self.public_key
                                             and g.infohash == database_blob(infohash))

        @db_session
        def add_torrent_to_channel(self, tdef, extra_info=None):
            """
            Add a torrent to your channel.
            :param tdef: The torrent definition file of the torrent to add
            :param extra_info: Optional extra info to add to the torrent
            """
            if extra_info:
                tags = extra_info.get('description', '')
            else:
                # We only want to determine the type of the data. XXX filtering is done by the receiving side
                tags = default_category_filter.calculateCategory(tdef.metainfo, tdef.get_name_as_unicode())

            new_entry_dict = {
                "infohash": tdef.get_infohash(),
                "title": tdef.get_name_as_unicode()[:300],  # TODO: do proper size checking based on bytes
                "tags": tags[:200],  # TODO: do proper size checking based on bytes
                "size": tdef.get_length(),
                "torrent_date": datetime.fromtimestamp(tdef.get_creation_date()),
                "tracker_info": get_uniformed_tracker_url(tdef.get_tracker() or '') or '',
                "status": NEW}

            # See if the torrent is already in the channel
            old_torrent = self.get_torrent(tdef.get_infohash())
            if old_torrent:
                # If it is there, check if we were going to delete it
                if old_torrent.status == TODELETE:
                    if old_torrent.metadata_conflicting(new_entry_dict):
                        # Metadata from torrent we're trying to add is conflicting with the
                        # deleted old torrent's metadata. We will replace the old metadata.
                        new_timestamp = self._clock.tick()
                        old_torrent.set(timestamp=new_timestamp, **new_entry_dict)
                        old_torrent.sign()
                    else:
                        # No conflict. This means the user is trying to replace the deleted torrent
                        # with the same one. Just recover the old one.
                        old_torrent.status = COMMITTED
                    torrent_metadata = old_torrent
                else:
                    raise DuplicateTorrentFileError()
            else:
                torrent_metadata = db.TorrentMetadata.from_dict(new_entry_dict)
            return torrent_metadata

        @db_session
        def copy_to_channel(self, infohash):
            return db.TorrentMetadata.copy_to_channel(infohash)

        @property
        def dirty(self):
            return self.contents.where(lambda g: g.status in [NEW, TODELETE, UPDATED]).exists()

        @property
        def contents(self):
            return db.TorrentMetadata.select(lambda g: g.public_key == self.public_key and g != self)

        @property
        def uncommitted_contents(self):
            return self.contents.where(lambda g: g.status in [NEW, UPDATED])

        @property
        def deleted_contents(self):
            return self.contents.where(lambda g: g.status == TODELETE)

        @property
        def dir_name(self):
            # Have to limit this to support Windows file path length limit
            return hexlify(self.public_key)[:CHANNEL_DIR_NAME_LENGTH]

        @property
        @db_session
        def staged_entries_list(self):
            return list(self.deleted_contents) + list(self.uncommitted_contents)

        @property
        @db_session
        def contents_list(self):
            return list(self.contents)

        @property
        def contents_len(self):
            return orm.count(self.contents)

        @db_session
        def delete_torrent(self, infohash):
            """
            Remove a torrent from this channel.
            Obsolete blob files are never deleted except on defragmentation of the channel.
            :param infohash: The infohash of the torrent to remove
            :return True if deleted, False if no MD with the given infohash found
            """
            torrent_metadata = db.TorrentMetadata.get(public_key=self.public_key, infohash=infohash)
            if not torrent_metadata:
                return False

            if torrent_metadata.status in [NEW, UPDATED]:
                # Uncommited metadata. Delete immediately
                torrent_metadata.delete()
            else:
                torrent_metadata.status = TODELETE

            return True

        @classmethod
        @db_session
        def get_channel_with_id(cls, channel_id):
            """
            Fetch a channel with a specific id.
            :param channel_id: The ID of the channel to fetch.
            :return: the ChannelMetadata object, or None if it is not available.
            """
            return cls.get(public_key=database_blob(channel_id))

        @db_session
        def drop_channel_contents(self):
            """
            Remove all torrents from the channel
            """
            # Immediately delete uncommitted metadata
            self.uncommitted_contents.delete()
            # Mark the rest as deleted
            for g in self.contents:
                g.status = TODELETE

        @classmethod
        @db_session
        def get_channel_with_infohash(cls, infohash):
            return cls.get(infohash=database_blob(infohash))

        @classmethod
        @db_session
        def get_channel_with_dirname(cls, dirname):
            # It is impossible to use LIKE queries on BLOBs, so we have to use comparisons
            def extend_to_bitmask(txt):
                return txt + "0" * (PUBLIC_KEY_LEN * 2 - CHANNEL_DIR_NAME_LENGTH)

            dirname_binmask_start = "x'" + extend_to_bitmask(dirname) + "'"

            binmask_plus_one = ("%X" % (int(dirname, 16) + 1)).zfill(len(dirname))
            dirname_binmask_end = "x'" + extend_to_bitmask(binmask_plus_one) + "'"

            sql = "g.public_key >= " + dirname_binmask_start + " AND g.public_key < " + dirname_binmask_end
            return orm.get(g for g in cls if raw_sql(sql))

        @classmethod
        @db_session
        def get_random_channels(cls, limit, only_subscribed=False):
            """
            Fetch up to some limit of torrents from this channel

            :param limit: the maximum amount of torrents to fetch
            :param only_subscribed: whether we only want random channels we are subscribed to
            :return: the subset of random channels we are subscribed to
            :rtype: list
            """
            if only_subscribed:
                select_lambda = lambda g: g.subscribed and g.status not in [LEGACY_ENTRY, NEW, UPDATED,
                                                                            TODELETE] and g.num_entries > 0
            else:
                select_lambda = lambda g: g.status not in [LEGACY_ENTRY, NEW, UPDATED,
                                                           TODELETE] and g.num_entries > 0

            return db.ChannelMetadata.select(select_lambda).random(limit)

        @db_session
        def get_random_torrents(self, limit):
            return self.contents.where(lambda g: g.status not in [NEW, TODELETE]).random(limit)

        @classmethod
        @db_session
        def get_updated_channels(cls):
            return select(g for g in cls if g.subscribed and (g.local_version < g.timestamp))

        @classmethod
        @db_session
        def get_entries(cls, first=None, last=None, subscribed=False, metadata_type=CHANNEL_TORRENT, **kwargs):
            """
            Get some channels. Optionally sort the results by a specific field, or filter the channels based
            on a keyword/whether you are subscribed to it.
            :return: A tuple. The first entry is a list of ChannelMetadata entries. The second entry indicates
                     the total number of results, regardless the passed first/last parameter.
            """
            pony_query, count = super(ChannelMetadata, cls).get_entries(metadata_type=metadata_type, **kwargs)
            if subscribed:
                pony_query = pony_query.where(subscribed=subscribed)

            return pony_query[(first or 1) - 1:last] if first or last else pony_query, count

        @property
        @db_session
        def channel_state(self):
            """
            This property describes the current state of the channel.
            :return: Text-based status
            """
            # TODO: optimize this by stopping doing blob comparisons on each call, and instead remember rowid?
            is_personal = database_blob(self._my_key.pub().key_to_bin()[10:]) == database_blob(self.public_key)
            if is_personal:
                return "Personal"
            if self.status == LEGACY_ENTRY:
                return "Legacy"
            if self.local_version == self.timestamp:
                return "Complete"
            if self.local_version > 0:
                return "Updating"
            if self.subscribed:
                return "Downloading"
            return "Preview"

        @db_session
        def to_simple_dict(self):
            """
            Return a basic dictionary with information about the channel.
            """
            epoch = datetime.utcfromtimestamp(0)
            return {
                "id": self.rowid,
                "public_key": hexlify(self.public_key),
                "name": self.title,
                "torrents": self.num_entries,
                "subscribed": self.subscribed,
                "votes": math.log1p(self.votes/db.ChannelMetadata.vsids_total_activity),
                "status": self.status,
                "updated": int((self.torrent_date - epoch).total_seconds()),
                "timestamp": self.timestamp,
                "state": self.channel_state
            }

        @classmethod
        @db_session
        def get_channel_name(cls, name, infohash):
            """
            Try to translate a Tribler download name into matching channel name. By searching for a channel with the
            given dirname and/or infohash. Try do determine if infohash belongs to an older version of
            some channel we already have.
            :param name - name of the download. Should match the directory name of the channel.
            :param infohash - infohash of the download.
            :return: Channel title as a string, prefixed with 'OLD:' for older versions
            """
            try:
                channel = cls.get_channel_with_dirname(name)
            except UnicodeEncodeError:
                channel = cls.get_channel_with_infohash(infohash)

            if not channel:
                return name
            if channel.infohash == database_blob(infohash):
                return channel.title
            else:
                return u'OLD:' + channel.title

        @db_session
        def add_torrents_from_dir(self, torrents_dir, recursive=False):
            # TODO: Optimize this properly!!!!
            torrents_list = []
            errors_list = []

            if recursive:
                def rec_gen():
                    for root, _, filenames in os.walk(torrents_dir):
                        for fn in filenames:
                            yield os.path.join(root, fn)

                filename_generator = rec_gen()
            else:
                filename_generator = os.listdir(torrents_dir)

            # Build list of .torrents to process
            for f in filename_generator:
                filepath = os.path.join(torrents_dir, f)
                filename = str(filepath) if sys.platform == 'win32' else filepath.decode('utf-8')
                if os.path.isfile(filepath) and filename.endswith(u'.torrent'):
                    torrents_list.append(filepath)

            for chunk in chunks(torrents_list, 100):  # 100 is a reasonable chunk size for commits
                for f in chunk:
                    try:
                        self.add_torrent_to_channel(TorrentDef.load(f))
                    except DuplicateTorrentFileError:
                        pass
                    except:
                        errors_list.append(f)
                orm.commit()  # Kinda optimization to drop excess cache?

            return torrents_list, errors_list

        @classmethod
        @db_session
        def vsids_rescale(cls):
            for channel in cls.select():
                channel.votes /= cls.bump_amount
            db.ChannelMetadata.vsids_total_activity /= cls.bump_amount
            cls.bump_amount = 1.0

        @classmethod
        @db_session
        def vsids_normalize(cls):
            # If we run the normalization for the first time during the runtime, we have to gather the activity from DB
            db.ChannelMetadata.vsids_total_activity = db.ChannelMetadata.vsids_total_activity or\
                                                      orm.sum(g.votes for g in db.ChannelMetadata)
            channel_count = orm.count(db.ChannelMetadata.select())
            if not channel_count:
                return
            if db.ChannelMetadata.vsids_total_activity > 0.0:
                cls.bump_amount = db.ChannelMetadata.vsids_total_activity / channel_count
                cls.vsids_rescale()

        def vote_bump(self):
            self.votes += self.bump_amount
            db.ChannelMetadata.vsids_total_activity += self.bump_amount
            db.ChannelMetadata.bump_amount *= math.exp(
                (datetime.utcnow() - db.ChannelMetadata.vsids_last_bump).total_seconds() /
                db.ChannelMetadata.vsids_exp_period)
            if self.bump_amount > self.rescale_threshold:
                db.ChannelMetadata.vsids_rescale()

    return ChannelMetadata
