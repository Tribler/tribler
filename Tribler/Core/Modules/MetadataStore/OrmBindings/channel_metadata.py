from __future__ import absolute_import, division

import os
from datetime import datetime

from ipv8.database import database_blob

from libtorrent import add_files, bencode, create_torrent, file_storage, set_piece_hashes, torrent_info

import lz4.frame

from pony import orm
from pony.orm import db_session, desc, raw_sql, select

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import (
    COMMITTED,
    LEGACY_ENTRY,
    NEW,
    PUBLIC_KEY_LEN,
    TODELETE,
    UPDATED,
)
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, ChannelMetadataPayload
from Tribler.Core.Utilities.random_utils import random_infohash
from Tribler.Core.Utilities.unicode import hexlify

CHANNEL_DIR_NAME_PK_LENGTH = 32  # Its not 40 so it could be distinguished from infohash
CHANNEL_DIR_NAME_ID_LENGTH = 16  # Zero-padded long int in hex form
CHANNEL_DIR_NAME_LENGTH = CHANNEL_DIR_NAME_PK_LENGTH + CHANNEL_DIR_NAME_ID_LENGTH
BLOB_EXTENSION = '.mdblob'
LZ4_END_MARK_SIZE = 4  # in bytes, from original specification. We don't use CRC


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i : i + n]


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
            blob = c.compress((metadata.serialized_delete() if metadata.status == TODELETE else metadata.serialized()))
            # Chunk size limit reached?
            if offset + len(blob) > (chunk_size - LZ4_END_MARK_SIZE):
                break
            # Now that we now it will fit in, we can safely append it
            offset += len(blob)
            last_entry_index = index
            out_list.append(blob)
        out_list.append(c.flush())  # LZ4 end mark

    chunk = b''.join(out_list)
    if last_entry_index is None:
        raise Exception('Serialized entry size > blob size limit!', hexlify(metadata_list[start_index].signature))
    return chunk, last_entry_index + 1


def define_binding(db):
    class ChannelMetadata(db.TorrentMetadata, db.CollectionNode):
        """
        This ORM binding represents Channel entries in the GigaChannel system. Each channel is a Collection that
        additionally has Torrent properties, such as infohash, etc. The torrent properties are used to associate
        a torrent that holds the contents of the channel dumped on the disk in the serialized form.
        Methods for committing channels into the torrent form are implemented in this class.
        """

        _discriminator_ = CHANNEL_TORRENT

        # Serializable
        start_timestamp = orm.Optional(int, size=64, default=0)

        # Local
        subscribed = orm.Optional(bool, default=False, index=True)
        share = orm.Optional(bool, default=False, index=True)
        votes = orm.Optional(float, default=0.0, index=True)
        individual_votes = orm.Set("ChannelVote", reverse="channel")
        local_version = orm.Optional(int, size=64, default=0)

        votes_scaling = 1.0

        # Special class-level properties
        _payload_class = ChannelMetadataPayload
        _channels_dir = None
        _category_filter = None
        _CHUNK_SIZE_LIMIT = 1 * 1024 * 1024  # We use 1MB chunks as a workaround for Python's lack of string pointers
        payload_arguments = _payload_class.__init__.__code__.co_varnames[
            : _payload_class.__init__.__code__.co_argcount
        ][1:]

        # As channel metadata depends on the public key, we can't include the infohash in nonpersonal_attributes
        nonpersonal_attributes = set(db.CollectionNode.nonpersonal_attributes)

        @classmethod
        @db_session
        def get_my_channel(cls):
            # return ChannelMetadata.get(public_key=database_blob(cls._my_key.pub().key_to_bin()[10:]), id_=0)
            # This is a workaround to fetch the most current personal channel
            # It should be replaced with the above line as soon as we move to nested channels
            return cls.get_recent_channel_with_public_key(cls._my_key.pub().key_to_bin()[10:])

        @classmethod
        @db_session
        def get_my_channels(cls):
            return ChannelMetadata.select(
                lambda g: g.origin_id == 0 and g.public_key == database_blob(cls._my_key.pub().key_to_bin()[10:])
            )

        @classmethod
        @db_session
        def create_channel(cls, title, description="", origin_id=0):
            """
            Create a channel and sign it with a given key.
            :param title: The title of the channel
            :param description: The description of the channel
            :param origin_id: id_ of the parent channel
            :return: The channel metadata
            """
            my_channel = cls(
                origin_id=origin_id,
                public_key=database_blob(cls._my_key.pub().key_to_bin()[10:]),
                title=title,
                tags=description,
                subscribed=True,
                share=True,
                status=NEW,
                infohash=os.urandom(20),
            )
            # random infohash is necessary to avoid triggering DB uniqueness constraints
            my_channel.sign()
            return my_channel

        @db_session
        def consolidate_channel_torrent(self):
            """
            Delete the channel dir contents and create it anew.
            Use it to consolidate fragmented channel torrent directories.
            :param key: The public/private key, used to sign the data
            """

            # TODO: optimize this stuff with SQL and better tree traversal algorithms?
            # Cleanup entries marked for deletion

            db.CollectionNode.collapse_deleted_subtrees()
            # TODO: optimize me: stop calling get_contents_to_commit here
            commit_queue = self.get_contents_to_commit()
            for entry in commit_queue:
                if entry.status == TODELETE:
                    entry.delete()

            folder = os.path.join(self._channels_dir, self.dirname)
            # We check if we need to re-create the channel dir in case it was deleted for some reason
            if not os.path.isdir(folder):
                os.makedirs(folder)
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                # We only remove mdblobs and leave the rest as it is
                if filename.endswith(BLOB_EXTENSION) or filename.endswith(BLOB_EXTENSION + '.lz4'):
                    os.unlink(file_path)

            # Channel should get a new starting timestamp and its contents should get higher timestamps
            start_timestamp = self._clock.tick()

            def update_timestamps_recursive(node):
                if issubclass(type(node), db.CollectionNode):
                    for child in node.contents:
                        update_timestamps_recursive(child)
                if node.status in [COMMITTED, UPDATED, NEW]:
                    node.status = UPDATED
                    node.timestamp = self._clock.tick()
                    node.sign()

            update_timestamps_recursive(self)

            return self.commit_channel_torrent(new_start_timestamp=start_timestamp)

        def update_channel_torrent(self, metadata_list, final_timestamp):
            """
            Channel torrents are append-only to support seeding the old versions
            from the same dir and avoid updating already downloaded blobs.
            :param metadata_list: The list of metadata entries to add to the torrent dir
            :param final_timestamp: The timestamp that will be used as the filename of the last mdblob in the update
            :return The new infohash, should be used to update the downloads
            """
            # Create dir for metadata files
            channel_dir = os.path.abspath(os.path.join(self._channels_dir, self.dirname))
            if not os.path.isdir(channel_dir):
                os.makedirs(channel_dir)

            index = 0
            while index < len(metadata_list):
                # Squash several serialized and signed metadata entries into a single file
                data, index = entries_to_chunk(metadata_list, self._CHUNK_SIZE_LIMIT, start_index=index)
                # The final file in the sequence should get the same (new) timestamp as the channel entry itself.
                # Otherwise, the local channel version will never become equal to its timestamp.
                blob_timestamp = metadata_list[index - 1].timestamp if index < len(metadata_list) else final_timestamp
                blob_filename = str(blob_timestamp).zfill(12) + BLOB_EXTENSION + '.lz4'
                with open(os.path.join(channel_dir, blob_filename), 'wb') as f:
                    f.write(data)

            # TODO: add error-handling routines to make sure the timestamp is not messed up in case of an error

            # Make torrent out of dir with metadata files
            torrent, infohash = create_torrent_from_dir(
                channel_dir, os.path.join(self._channels_dir, self.dirname + ".torrent")
            )
            torrent_date = datetime.utcfromtimestamp(torrent[b'creation date'])

            return ({"infohash": infohash, "timestamp": final_timestamp, "torrent_date": torrent_date}, torrent)

        def commit_channel_torrent(self, new_start_timestamp=None, commit_list=None):
            """
            Collect new/uncommitted and marked for deletion metadata entries, commit them to a channel torrent and
            remove the obsolete entries if the commit succeeds.
            :param new_start_timestamp: change the start_timestamp of the commited channel entry to this value
            :param commit_list: the list of ORM objects to commit into this channel torrent
            :return The new infohash, should be used to update the downloads
            """
            md_list = commit_list or self.get_contents_to_commit()

            if not md_list:
                return None

            final_timestamp = self._clock.tick()
            try:
                update_dict, torrent = self.update_channel_torrent(md_list, final_timestamp)
            except IOError:
                self._logger.error(
                    "Error during channel torrent commit, not going to garbage collect the channel. Channel %s",
                    hexlify(self.public_key),
                )
                return None

            if new_start_timestamp:
                update_dict['start_timestamp'] = new_start_timestamp
            for attr, val in update_dict.items():
                setattr(self, attr, val)
            self.local_version = self.timestamp
            self.sign()

            # Change the statuses of committed entries and clean up obsolete TODELETE entries
            for g in md_list:
                if g.status in [NEW, UPDATED]:
                    g.status = COMMITTED
                elif g.status == TODELETE:
                    g.delete()

            # Write the channel mdblob to disk
            self.status = COMMITTED
            self.to_file(os.path.join(self._channels_dir, self.dirname + BLOB_EXTENSION))

            self._logger.info(
                "Channel %s committed with %i new entries. New version is %i",
                hexlify(self.public_key),
                len(md_list),
                update_dict['timestamp'],
            )
            return torrent

        @db_session
        def torrent_exists(self, infohash):
            """
            Return True if torrent with given infohash exists in the user channel
            :param infohash: The infohash of the torrent
            :return: True if torrent exists else False
            """
            return db.TorrentMetadata.exists(
                lambda g: g.public_key == self.public_key
                and g.infohash == database_blob(infohash)
                and g.status != LEGACY_ENTRY
            )

        @property
        def dirname(self):
            # Have to limit this to support Windows file path length limit
            return hexlify(self.public_key)[:CHANNEL_DIR_NAME_PK_LENGTH] + "{:0>16x}".format(self.id_)

        @classmethod
        @db_session
        def get_channel_with_infohash(cls, infohash):
            return cls.get(infohash=database_blob(infohash))

        @classmethod
        @db_session
        def get_recent_channel_with_public_key(cls, public_key):
            return (
                cls.select(lambda g: g.public_key == database_blob(public_key)).sort_by(lambda g: desc(g.id_)).first()
                or None
            )

        @classmethod
        @db_session
        def get_channel_with_dirname(cls, dirname):
            # Parse the public key part of the dirname
            pk_part = dirname[:-CHANNEL_DIR_NAME_ID_LENGTH]

            def extend_to_bitmask(txt):
                return txt + "0" * (PUBLIC_KEY_LEN * 2 - CHANNEL_DIR_NAME_LENGTH)

            pk_binmask_start = "x'" + extend_to_bitmask(pk_part) + "'"
            pk_plus_one = ("%X" % (int(pk_part, 16) + 1)).zfill(len(pk_part))
            pk_binmask_end = "x'" + extend_to_bitmask(pk_plus_one) + "'"
            # It is impossible to use LIKE queries on BLOBs, so we have to use comparisons
            sql = "g.public_key >= " + pk_binmask_start + " AND g.public_key < " + pk_binmask_end

            # Parse the id part of the dirname
            id_part = dirname[-CHANNEL_DIR_NAME_ID_LENGTH:]
            id_ = int(id_part, 16)

            return orm.select(g for g in cls if g.id_ == id_ and raw_sql(sql)).first()

        @classmethod
        @db_session
        def get_random_channels(cls, limit, only_subscribed=False, only_downloaded=False):
            """
            Fetch up to some limit of torrents from this channel

            :param limit: the maximum amount of torrents to fetch
            :param only_subscribed: whether we only want random channels we are subscribed to
            :param only_downloaded: whether we only want channels that were downloaded/seeded from a torrent
            :return: the subset of random channels we are subscribed to
            :rtype: list
            """
            query = db.ChannelMetadata.select(
                lambda g: g.status not in [LEGACY_ENTRY, NEW, UPDATED, TODELETE] and g.num_entries > 0
            and
                g.public_key != database_blob(cls._my_key.pub().key_to_bin()[10:]))
            query = query.where(subscribed=True) if only_subscribed else query
            query = query.where(lambda g: g.local_version == g.timestamp) if only_downloaded else query
            return query.random(limit)

        @classmethod
        @db_session
        def get_updated_channels(cls):
            return select(
                g
                for g in cls
                if g.subscribed
                and (g.local_version < g.timestamp)
                and g.public_key != database_blob(cls._my_key.pub().key_to_bin()[10:])
            )

        @classmethod
        @db_session
        def get_entries_query(cls, subscribed=None, **kwargs):
            # This method filters channels-related arguments and translates them into Pony query parameters
            pony_query = super(ChannelMetadata, cls).get_entries_query(**kwargs)
            pony_query = pony_query.where(subscribed=subscribed) if subscribed is not None else pony_query
            return pony_query

        @property
        @db_session
        def state(self):
            """
            This property describes the current state of the channel.
            :return: Text-based status
            """
            # TODO: optimize this by stopping doing blob comparisons on each call, and instead remember rowid?
            if self.is_personal:
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
        def to_simple_dict(self, **kwargs):
            """
            Return a basic dictionary with information about the channel.
            """
            result = super(ChannelMetadata, self).to_simple_dict(**kwargs)
            result.update(
                {
                    "state": self.state,
                    "subscribed": self.subscribed,
                    "votes": self.votes / db.ChannelMetadata.votes_scaling,
                }
            )
            return result

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
            channel = cls.get_channel_with_infohash(infohash)
            if not channel:
                try:
                    channel = cls.get_channel_with_dirname(name)
                except UnicodeEncodeError:
                    channel = None

            if not channel:
                return name
            if channel.infohash == database_blob(infohash):
                return channel.title
            else:
                return u'OLD:' + channel.title

        @db_session
        def update_properties(self, update_dict):
            updated_self = super(ChannelMetadata, self).update_properties(update_dict)
            if updated_self.origin_id != 0:
                # Coerce to CollectionNode
                # ACHTUNG! This is a little bit awkward way to re-create the entry as an instance of
                # another class. Be very careful with it!
                self_dict = updated_self.to_dict()
                updated_self.delete(recursive=False)
                self_dict.pop("rowid")
                self_dict.pop("metadata_type")
                self_dict["sign_with"] = self._my_key
                updated_self = db.CollectionNode.from_dict(self_dict)
            return updated_self

        def make_copy(self, tgt_parent_id, **kwargs):
            return db.CollectionNode.make_copy(
                self, tgt_parent_id, attributes_override={'infohash': random_infohash()}, **kwargs
            )

    return ChannelMetadata
