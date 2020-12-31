import os
from datetime import datetime
from pathlib import Path

from ipv8.database import database_blob

from libtorrent import add_files, bencode, create_torrent, file_storage, set_piece_hashes, torrent_info

import lz4.frame

from pony import orm
from pony.orm import db_session, desc, raw_sql, select

from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.modules.metadata_store.discrete_clock import clock
from tribler_core.modules.metadata_store.orm_bindings.channel_node import (
    COMMITTED,
    LEGACY_ENTRY,
    NEW,
    PUBLIC_KEY_LEN,
    TODELETE,
    UPDATED,
)
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, ChannelMetadataPayload
from tribler_core.utilities import path_util
from tribler_core.utilities.path_util import str_path
from tribler_core.utilities.random_utils import random_infohash
from tribler_core.utilities.unicode import hexlify

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
    add_files(fs, str(directory))
    t = create_torrent(fs)
    # t = create_torrent(fs, flags=17) # piece alignment
    t.set_priv(False)
    set_piece_hashes(t, str(directory.parent))
    torrent = t.generate()
    with open(torrent_filename, 'wb') as f:
        f.write(bencode(torrent))

    infohash = torrent_info(torrent).info_hash().to_bytes()
    return torrent, infohash


def get_mdblob_sequence_number(filename):
    filepath = Path(filename)
    if filepath.suffixes == [BLOB_EXTENSION]:
        return int(filename.stem)
    if filepath.suffixes == [BLOB_EXTENSION, '.lz4']:
        return int(Path(filepath.stem).stem)
    return None


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
            blob = c.compress(metadata.serialized_delete() if metadata.status == TODELETE else metadata.serialized())
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

        infohash_to_channel_name_cache = {}

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
                infohash=random_infohash(),
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

            folder = Path(self._channels_dir) / self.dirname
            # We check if we need to re-create the channel dir in case it was deleted for some reason
            if not folder.is_dir():
                os.makedirs(folder)
            for filename in os.listdir(folder):
                file_path = folder / filename
                # We only remove mdblobs and leave the rest as it is
                if filename.endswith(BLOB_EXTENSION) or filename.endswith(BLOB_EXTENSION + '.lz4'):
                    os.unlink(str_path(file_path))

            # Channel should get a new starting timestamp and its contents should get higher timestamps
            start_timestamp = clock.tick()

            def update_timestamps_recursive(node):
                if issubclass(type(node), db.CollectionNode):
                    for child in node.contents:
                        update_timestamps_recursive(child)
                if node.status in [COMMITTED, UPDATED, NEW]:
                    node.status = UPDATED
                    node.timestamp = clock.tick()
                    node.sign()

            update_timestamps_recursive(self)

            return self.commit_channel_torrent(new_start_timestamp=start_timestamp)

        def update_channel_torrent(self, metadata_list):
            """
            Channel torrents are append-only to support seeding the old versions
            from the same dir and avoid updating already downloaded blobs.
            :param metadata_list: The list of metadata entries to add to the torrent dir.
            ACHTUNG: TODELETE entries _MUST_ be sorted to the end of the list to prevent channel corruption!
            :return The newly create channel torrent infohash, final timestamp for the channel and torrent date
            """
            # As a workaround for delete entries not having a timestamp in the DB, delete entries should
            # be placed after create/modify entries:
            # | create/modify entries | delete entries | <- final timestamp

            # Create dir for the metadata files
            channel_dir = path_util.abspath(self._channels_dir / self.dirname)
            if not channel_dir.is_dir():
                os.makedirs(str_path(channel_dir))

            existing_contents = sorted(channel_dir.iterdir())
            last_existing_blob_number = get_mdblob_sequence_number(existing_contents[-1]) if existing_contents else None

            index = 0
            while index < len(metadata_list):
                # Squash several serialized and signed metadata entries into a single file
                data, index = entries_to_chunk(metadata_list, self._CHUNK_SIZE_LIMIT, start_index=index)
                # Blobs ending with TODELETE entries increase the final timestamp as a workaround for delete commands
                # possessing no timestamp.
                if metadata_list[index - 1].status == TODELETE:
                    blob_timestamp = clock.tick()
                else:
                    blob_timestamp = metadata_list[index - 1].timestamp

                # The final file in the sequence should get a timestamp that is higher than the timestamp of
                # the last channel contents entry. This final timestamp then should be returned to the calling function
                # to be assigned to the corresponding channel entry.
                # Otherwise, the local channel version will never become equal to its timestamp.
                if index >= len(metadata_list):
                    blob_timestamp = clock.tick()
                # Check that the mdblob we're going to create has a greater timestamp than the existing ones
                assert last_existing_blob_number is None or (blob_timestamp > last_existing_blob_number)

                blob_filename = Path(channel_dir, str(blob_timestamp).zfill(12) + BLOB_EXTENSION + '.lz4')
                assert not blob_filename.exists()  # Never ever write over existing files.
                blob_filename.write_bytes(data)
                last_existing_blob_number = blob_timestamp

            # TODO: add error-handling routines to make sure the timestamp is not messed up in case of an error

            # Make torrent out of dir with metadata files
            torrent, infohash = create_torrent_from_dir(channel_dir, self._channels_dir / (self.dirname + ".torrent"))
            torrent_date = datetime.utcfromtimestamp(torrent[b'creation date'])

            return {"infohash": infohash, "timestamp": last_existing_blob_number, "torrent_date": torrent_date}, torrent

        def commit_channel_torrent(self, new_start_timestamp=None, commit_list=None):
            """
            Collect new/uncommitted and marked for deletion metadata entries, commit them to a channel torrent and
            remove the obsolete entries if the commit succeeds.
            :param new_start_timestamp: change the start_timestamp of the committed channel entry to this value
            :param commit_list: the list of ORM objects to commit into this channel torrent
            :return The new infohash, should be used to update the downloads
            """
            md_list = commit_list or self.get_contents_to_commit()

            if not md_list:
                return None

            try:
                update_dict, torrent = self.update_channel_torrent(md_list)
            except OSError:
                self._logger.error(
                    "Error during channel torrent commit, not going to garbage collect the channel. Channel %s",
                    hexlify(self.public_key),
                )
                return None

            if new_start_timestamp:
                update_dict['start_timestamp'] = new_start_timestamp
            # Update channel infohash, etc
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
            self.to_file(self._channels_dir / (self.dirname + BLOB_EXTENSION))

            self._logger.info(
                "Channel %s committed with %i new entries. New version is %i",
                hexlify(self.public_key),
                len(md_list),
                update_dict['timestamp'],
            )
            return torrent

        @property
        def dirname(self):
            # Have to limit this to support Windows file path length limit
            return hexlify(self.public_key)[:CHANNEL_DIR_NAME_PK_LENGTH] + f"{self.id_:0>16x}"

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
            pk_plus_one = f"{int(pk_part, 16) + 1:X}".zfill(len(pk_part))
            pk_binmask_end = "x'" + extend_to_bitmask(pk_plus_one) + "'"
            # It is impossible to use LIKE queries on BLOBs, so we have to use comparisons
            sql = "g.public_key >= " + pk_binmask_start + " AND g.public_key < " + pk_binmask_end

            # Parse the id part of the dirname
            id_part = dirname[-CHANNEL_DIR_NAME_ID_LENGTH:]
            id_ = int(id_part, 16)

            return orm.select(g for g in cls if g.id_ == id_ and raw_sql(sql)).first()

        @classmethod
        @db_session
        def get_updated_channels(cls):
            return select(
                g
                for g in cls
                if g.subscribed
                and g.status != LEGACY_ENTRY
                and (g.local_version < g.timestamp)
                and g.public_key != database_blob(cls._my_key.pub().key_to_bin()[10:])
            )

        @property
        @db_session
        def state(self):
            """
            This property describes the current state of the channel.
            :return: Text-based status
            """
            # TODO: optimize this by stopping doing blob comparisons on each call, and instead remember rowid?
            if self.is_personal:
                return CHANNEL_STATE.PERSONAL.value
            if self.status == LEGACY_ENTRY:
                return CHANNEL_STATE.LEGACY.value
            if self.local_version == self.timestamp:
                return CHANNEL_STATE.COMPLETE.value
            if self.local_version > 0:
                return CHANNEL_STATE.UPDATING.value
            if self.subscribed:
                return CHANNEL_STATE.METAINFO_LOOKUP.value
            return CHANNEL_STATE.PREVIEW.value

        def to_simple_dict(self, **kwargs):
            """
            Return a basic dictionary with information about the channel.
            """
            result = super().to_simple_dict(**kwargs)
            result.update(
                {
                    "state": self.state,
                    "subscribed": self.subscribed,
                    "votes": self.votes / db.ChannelMetadata.votes_scaling,
                }
            )
            return result

        @classmethod
        def get_channel_name_cached(cls, dl_name, infohash):
            # Querying the database each time is costly so we cache the name request in a dict.
            chan_name = cls.infohash_to_channel_name_cache.get(infohash)
            if chan_name is None:
                chan_name = cls.get_channel_name(dl_name, infohash)
                cls.infohash_to_channel_name_cache[infohash] = chan_name
            return chan_name

        @classmethod
        @db_session
        def get_channel_name(cls, dl_name, infohash):
            """
            Try to translate a Tribler download name into matching channel name. By searching for a channel with the
            given dirname and/or infohash. Try do determine if infohash belongs to an older version of
            some channel we already have.
            :param dl_name - name of the download. Should match the directory name of the channel.
            :param infohash - infohash of the download.
            :return: Channel title as a string, prefixed with 'OLD:' for older versions
            """
            channel = cls.get_channel_with_infohash(infohash)
            if not channel:
                try:
                    channel = cls.get_channel_with_dirname(dl_name)
                except UnicodeEncodeError:
                    channel = None

            if not channel:
                return dl_name
            if channel.infohash == database_blob(infohash):
                return channel.title
            else:
                return 'OLD:' + channel.title

        @db_session
        def update_properties(self, update_dict):
            updated_self = super().update_properties(update_dict)
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
