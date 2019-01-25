from __future__ import absolute_import

import os
from binascii import hexlify
from datetime import datetime
from libtorrent import add_files, bencode, create_torrent, file_storage, set_piece_hashes, torrent_info

import lz4.frame
from pony import orm
from pony.orm import db_session, raw_sql, select

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import COMMITTED, NEW, PUBLIC_KEY_LEN, TODELETE, \
    LEGACY_ENTRY
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, ChannelMetadataPayload
from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url
from Tribler.Core.exceptions import DuplicateChannelNameError, DuplicateTorrentFileError
from Tribler.pyipv8.ipv8.database import database_blob

CHANNEL_DIR_NAME_LENGTH = 32  # Its not 40 so it could be distinguished from infohash
BLOB_EXTENSION = '.mdblob'
LZ4_END_MARK_SIZE = 4  # in bytes, from original specification. We don't use CRC
ROOT_CHANNEL_ID = 0


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
                        str(metadata_list[start_index].signature).encode('hex'))
    return chunk, last_entry_index + 1


def define_binding(db):
    class ChannelMetadata(db.TorrentMetadata):
        _discriminator_ = CHANNEL_TORRENT

        # Serializable
        num_entries = orm.Optional(int, size=64, default=0)

        # Local
        subscribed = orm.Optional(bool, default=False)
        votes = orm.Optional(int, size=64, default=0)
        local_version = orm.Optional(int, size=64, default=0)

        _payload_class = ChannelMetadataPayload
        _channels_dir = None
        _category_filter = None
        _CHUNK_SIZE_LIMIT = 1 * 1024 * 1024  # We use 1MB chunks as a workaround for Python's lack of string pointers

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
        def create_channel(cls, title, description):
            """
            Create a channel and sign it with a given key.
            :param title: The title of the channel
            :param description: The description of the channel
            :return: The channel metadata
            """
            if ChannelMetadata.get_channel_with_id(cls._my_key.pub().key_to_bin()[10:]):
                raise DuplicateChannelNameError()

            my_channel = cls(id_=ROOT_CHANNEL_ID, public_key=database_blob(cls._my_key.pub().key_to_bin()[10:]),
                             title=title, tags=description, subscribed=True)
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
            for g in self.contents:
                g.status = NEW
            self.commit_channel_torrent()

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
                    "timestamp": new_timestamp, "torrent_date": torrent_date}

        def commit_channel_torrent(self):
            """
            Collect new/uncommitted and marked for deletion metadata entries, commit them to a channel torrent and
            remove the obsolete entries if the commit succeeds.
            :return The new infohash, should be used to update the downloads
            """
            new_infohash = None
            md_list = self.staged_entries_list
            if not md_list:
                return None

            try:
                update_dict = self.update_channel_torrent(md_list)
            except IOError:
                self._logger.error(
                    "Error during channel torrent commit, not going to garbage collect the channel. Channel %s",
                    str(self.public_key).encode("hex"))
            else:
                self.update_metadata(update_dict)
                self.local_version = self.timestamp
                # Change status of committed metadata and clean up obsolete TODELETE entries
                for g in md_list:
                    if g.status == NEW:
                        g.status = COMMITTED
                    elif g.status == TODELETE:
                        g.delete()

                # Write the channel mdblob to disk
                self.to_file(os.path.join(self._channels_dir, self.dir_name + BLOB_EXTENSION))

                self._logger.info("Channel %s committed with %i new entries. New version is %i",
                                  str(self.public_key).encode("hex"), len(md_list), update_dict['timestamp'])
            return new_infohash

        @db_session
        def get_torrent(self, infohash):
            """
            Return the torrent with a provided infohash.
            :param infohash: The infohash of the torrent to search for
            :return: TorrentMetadata if the torrent exists in the channel, else None
            """
            return db.TorrentMetadata.get(public_key=self.public_key, infohash=infohash)

        @db_session
        def add_torrent_to_channel(self, tdef, extra_info):
            """
            Add a torrent to your channel.
            :param tdef: The torrent definition file of the torrent to add
            :param extra_info: Optional extra info to add to the torrent
            """
            if extra_info:
                tags = extra_info.get('description', '')
            elif self._category_filter:
                tags = self._category_filter.calculateCategory(tdef.metainfo, tdef.get_name_as_unicode())
            else:
                tags = ''

            new_entry_dict = {
                "infohash": tdef.get_infohash(),
                "title": tdef.get_name_as_unicode(),
                "tags": tags,
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
                torrent_metadata.parents.add(self)
            return torrent_metadata

        @property
        def dirty(self):
            return self.contents.where(lambda g: g.status == NEW or g.status == TODELETE).exists()

        @property
        def contents(self):
            return db.TorrentMetadata.select(lambda g: g.public_key == self.public_key and g != self)

        @property
        def uncommitted_contents(self):
            return self.contents.where(lambda g: g.status == NEW)

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

            if torrent_metadata.status == NEW:
                # Uncommited metadata. Delete immediately
                torrent_metadata.delete()
            else:
                torrent_metadata.status = TODELETE

            return True

        @db_session
        def cancel_torrent_deletion(self, infohash):
            """
            Cancel pending removal of torrent marked for deletion.
            :param infohash: The infohash of the torrent to act upon
            :return True if deleteion cancelled, False if no MD with the given infohash found
            """
            if self.get_torrent(infohash):
                torrent_metadata = db.TorrentMetadata.get(public_key=self.public_key, infohash=infohash)
            else:
                return False

            # As any NEW metadata is deleted immediately, only COMMITTED -> TODELETE
            # Therefore we restore the entry's status to COMMITTED
            if torrent_metadata.status == TODELETE:
                torrent_metadata.status = COMMITTED
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
        def get_random_channels(cls, limit, subscribed=False):
            """
            Fetch up to some limit of torrents from this channel

            :param limit: the maximum amount of torrents to fetch
            :param subscribed: whether we want random channels we are subscribed to
            :return: the subset of random channels we are subscribed to
            :rtype: list
            """
            return db.ChannelMetadata.select(
                lambda g: g.subscribed == subscribed and g.status != LEGACY_ENTRY and g.num_entries > 0).random(
                limit)

        @db_session
        def get_random_torrents(self, limit):
            return self.contents.random(limit)

        @db_session
        def remove_contents(self):
            self.contents.delete()

        @classmethod
        @db_session
        def get_updated_channels(cls):
            return select(g for g in cls if g.subscribed and (g.local_version < g.timestamp))

        @classmethod
        @db_session
        def get_channels(cls, first=1, last=50, sort_by=None, sort_asc=True, query_filter=None, subscribed=False):
            """
            Get some channels. Optionally sort the results by a specific field, or filter the channels based
            on a keyword/whether you are subscribed to it.
            :return: A tuple. The first entry is a list of ChannelMetadata entries. The second entry indicates
                     the total number of results, regardless the passed first/last parameter.
            """
            pony_query = ChannelMetadata.get_entries_query(sort_by=sort_by, sort_asc=sort_asc,
                                                           query_filter=query_filter)

            # Filter subscribed/non-subscribed
            if subscribed:
                pony_query = pony_query.where(subscribed=subscribed)

            total_results = pony_query.count()

            return pony_query[first - 1:last], total_results

        @db_session
        def to_simple_dict(self):
            """
            Return a basic dictionary with information about the channel.
            """
            return {
                "id": self.rowid,
                "public_key": hexlify(self.public_key),
                "name": self.title,
                "torrents": self.contents_len,
                "subscribed": self.subscribed,
                "votes": self.votes,
                "status": self.status,

                # TODO: optimize this?
                "my_channel": database_blob(self._my_key.pub().key_to_bin()[10:]) == database_blob(self.public_key)
            }

    return ChannelMetadata
