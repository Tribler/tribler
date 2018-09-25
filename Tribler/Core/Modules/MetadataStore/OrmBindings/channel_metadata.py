import os
from datetime import datetime

from libtorrent import file_storage, add_files, create_torrent, set_piece_hashes, bencode, torrent_info
from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.serialization import MetadataTypes, ChannelMetadataPayload, time2float, \
    float2time, MetadataPayload, TorrentMetadataPayload
from Tribler.Core.exceptions import DuplicateTorrentFileError, DuplicateChannelNameError
from Tribler.pyipv8.ipv8.attestation.trustchain.block import EMPTY_SIG
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer

CHANNEL_DIR_NAME_LENGTH = 60  # Its not 40 so it could be distinguished from infohash
BLOB_EXTENSION = '.mdblob'


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


def define_binding(db):
    class ChannelMetadata(db.TorrentMetadata):
        _discriminator_ = MetadataTypes.CHANNEL_TORRENT.value
        version = orm.Optional(int, size=64, default=0)
        subscribed = orm.Optional(bool, default=False)
        votes = orm.Optional(int, size=64, default=0)

        def serialized(self, signature=True):
            serializer = Serializer()
            payload = ChannelMetadataPayload(self.type, str(self.public_key), time2float(self.timestamp),
                                             self.tc_pointer, str(self.signature) if signature else EMPTY_SIG,
                                             str(self.infohash), self.size, str(self.title), str(self.tags),
                                             self.version)
            return serializer.pack_multiple(payload.to_pack_list())[0]

        @db_session
        def update_metadata(self, key, update_dict=None):
            now = datetime.utcnow()
            channel_dict = self.to_dict()
            channel_dict.update(update_dict or {})
            channel_dict.update({
                "size": len(self.contents_list),
                "timestamp": now,
                "torrent_date": now
            })
            self.set(**channel_dict)
            self.sign(key)

        @classmethod
        @db_session
        def process_channel_metadata_payload(cls, metadata_channel_payload):
            """
            Process some channel metadata.
            :param metadata_channel_payload: The channel metadata, in serialized form.
            :return: The ChannelMetadata object that contains the latest version of the channel
            """
            existing_channel_metadata = ChannelMetadata.get_channel_with_id(metadata_channel_payload.public_key)
            if existing_channel_metadata:
                if metadata_channel_payload.version > existing_channel_metadata.version:
                    existing_channel_metadata.delete()
                    return ChannelMetadata.from_payload(metadata_channel_payload)
                else:
                    return existing_channel_metadata
            else:
                return ChannelMetadata.from_payload(metadata_channel_payload)

        @property
        @db_session
        def contents_list(self):
            return list(self.contents)

        @property
        @db_session
        def contents(self):
            return db.TorrentMetadata.select(lambda g: g.public_key == self.public_key and g != self)

        @property
        def dir_name(self):
            # Have to limit this to support Windows file path length limit
            return str(self.public_key).encode('hex')[-CHANNEL_DIR_NAME_LENGTH:]

        @classmethod
        @db_session
        def create_channel(cls, key, title, description):
            """
            Create a channel and sign it with a given key.
            :param key: The key to sign the channel metadata with
            :param title: The title of the channel
            :param description: The description of the channel
            :return: The channel metadata
            """
            if ChannelMetadata.get_channel_with_id(key.pub().key_to_bin()):
                raise DuplicateChannelNameError()

            my_channel = cls(public_key=buffer(key.pub().key_to_bin()), title=title,
                             tags=description, subscribed=True, version=1)
            my_channel.sign(key)
            return my_channel

        def update_channel_torrent(self, key, channels_dir, metadata_list):
            # Create dir for metadata files
            channel_dir = os.path.abspath(os.path.join(channels_dir, self.dir_name))
            if not os.path.isdir(channel_dir):
                os.makedirs(channel_dir)

            new_version = self.version

            # Write serialized and signed metadata into files
            for metadata in metadata_list:
                new_version += 1
                with open(os.path.join(channel_dir, str(new_version).zfill(9) + BLOB_EXTENSION), 'wb') as f:
                    serialized = metadata.serialized()
                    f.write(serialized)

            # Make torrent out of dir with metadata files
            infohash = create_torrent_from_dir(channel_dir, os.path.join(channels_dir, self.dir_name + ".torrent"))
            self.update_metadata(key, update_dict={"infohash": infohash, "version": new_version})

            # Write the channel mdblob away
            with open(os.path.join(channels_dir, self.dir_name + BLOB_EXTENSION), 'wb') as out_file:
                out_file.write(self.serialized())

            return infohash

        @db_session
        def has_torrent(self, infohash):
            """
            Check whether this channel contains the torrent with a provided infohash.
            :param infohash: The infohash of the torrent to search for
            :return: True if the torrent exists in the channel, else False
            """
            return db.TorrentMetadata.get(public_key=self.public_key, infohash=infohash) is not None

        @db_session
        def add_torrent_to_channel(self, key, tdef, extra_info, channels_dir):
            """
            Add a torrent to your channel.
            :param key: The public/private key, used to sign the data
            :param tdef: The torrent definition file of the torrent to add
            :param extra_info: Optional extra info to add to the torrent
            :param channels_dir: The directory where all channels are stored
            :return The old and new infohash, should be used to update the downloads
            """
            if self.has_torrent(tdef.get_infohash()):
                raise DuplicateTorrentFileError()

            torrent_metadata = db.TorrentMetadata.from_dict({
                "infohash": tdef.get_infohash(),
                "title": tdef.get_name_as_unicode(),
                "tags": extra_info.get('description', '') if extra_info else '',
                "size": tdef.get_length(),
                "torrent_date": datetime.fromtimestamp(tdef.get_creation_date()),
                "tc_pointer": 0,
                "public_key": key.pub().key_to_bin()
            })
            torrent_metadata.sign(key)
            return self.add_metadata_to_channel(key, channels_dir, [torrent_metadata])

        @db_session
        def delete_torrent_from_channel(self, key, infohash, channels_dir):
            """
            Remove a torrent from this channel and recreate the channel torrent.
            :param key: The public/private key, used to sign the data
            :param infohash: The infohash of the torrent to remove
            :return The old and new infohash, should be used to update the downloads
            """
            serializer = Serializer()
            this_channel_dir = os.path.abspath(os.path.join(channels_dir, self.dir_name))
            file_to_edit = None
            torrent_metadata = None
            for filename in sorted(os.listdir(this_channel_dir)):
                full_path = os.path.join(this_channel_dir, filename)
                with open(full_path, 'rb') as blob_file:
                    serialized_data = blob_file.read()
                    metadata_payload = serializer.unpack_to_serializables([MetadataPayload, ], serialized_data)[0]
                    if metadata_payload.metadata_type == MetadataTypes.REGULAR_TORRENT.value:
                        torrent_metadata_payload = serializer.unpack_to_serializables(
                            [TorrentMetadataPayload, ], serialized_data)[0]
                        if torrent_metadata_payload.infohash == infohash:
                            # We found the file to edit
                            torrent_metadata = db.TorrentMetadata.from_payload(torrent_metadata_payload)
                            file_to_edit = full_path
                            break

            if not file_to_edit:
                # The torrent with the given infohash could not be found, do not apply an update
                return str(self.infohash), str(self.infohash)

            deleted_metadata = db.DeletedMetadata.from_dict({
                "public_key": self.public_key,
                "delete_signature": torrent_metadata.signature
            })
            with open(file_to_edit, 'wb') as output_file:
                output_file.write(deleted_metadata.serialized())

            # Delete the torrent itself
            db.TorrentMetadata.select(
                lambda metadata: metadata.signature == torrent_metadata.signature).delete(bulk=True)

            old_infohash = self.infohash
            new_infohash = self.update_channel_torrent(key, channels_dir, [])
            return str(old_infohash), str(new_infohash)

        @db_session
        def add_metadata_to_channel(self, key, channels_dir, metadata_list):
            """
            Commit a given list of metadata objects to a torrent. It also updates the metadata afterwards.
            :param key: The key, used to sign the new ChannelMetadata object
            :param channels_dir: The directory where all channels are stored
            :param metadata_list: The list with metadata objects to add to this channel
            :return The old and new infohash, should be used to update the downloads
            """
            old_infohash = self.infohash
            new_infohash = self.update_channel_torrent(key, channels_dir, metadata_list)

            return str(old_infohash), str(new_infohash)

        @classmethod
        @db_session
        def get_channel_with_id(cls, channel_id):
            """
            Fetch a channel with a specific id.
            :param channel_id: The ID of the channel to fetch.
            :return: the ChannelMetadata object, or None if it is not available.
            """
            return cls.get(public_key=buffer(channel_id))

        @classmethod
        @db_session
        def from_payload(cls, payload):
            metadata_dict = {
                "type": payload.metadata_type,
                "public_key": payload.public_key,
                "timestamp": float2time(payload.timestamp),
                "tc_pointer": payload.tc_pointer,
                "signature": payload.signature,
                "infohash": payload.infohash,
                "size": payload.size,
                "title": payload.title,
                "tags": payload.tags,
                "version": payload.version
            }
            return cls(**metadata_dict)

    return ChannelMetadata
