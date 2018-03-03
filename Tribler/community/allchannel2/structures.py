import os

from libtorrent import add_files, bdecode, bencode, create_torrent, file_storage, set_piece_hashes


PIECE_SIZE = 16*1024*1024 # 16 MB: Holds 762600 magnetlinks without metadata


class Chunk(object):
    """
    A `PIECE_SIZE` sized file filled with magnet links/metadata.
    """

    def __init__(self):
        """
        Initialize the Chunk: it is still in memory.
        The value of `serialize()` can be written to disk.
        """
        super(Chunk, self).__init__()
        self.data = {}
        self.current_length = 0
        self.max_length = PIECE_SIZE - 2 # 16MB - len('d') len('e')

    def add(self, key, value):
        """
        Add a key, value (magnetlink, metadata) store to the Chunk.
        This may fail if the key/value is too big to fit into this Chunk.

        :param key: the key / magnetlink
        :param value: the value / metadata
        :returns: whether the store was added successfully
        """
        key_len = len(key)
        value_len = len(value)
        combined_len = len(str(key_len)) + len(str(value_len)) + key_len + value_len + 4

        if self.current_length + combined_len <= self.max_length:
            self.data[key] = value
            self.current_length += combined_len
            return True
        return False

    def remove(self, key):
        """
        Remove a key, value store by key.
        They key does not need to exist in this Chunk.

        :param key: the key to remove by
        :returns: None
        """
        self.data.pop(key, None)

    def serialize(self):
        """
        Create a serialized form of this Chunk.
        :return: the bencoding of this Chunk
        """
        return bencode(self.data)

    @classmethod
    def unserialize(cls, data):
        """
        Read in a Chunk from a file.

        :param data: the file contents
        :return: a Chunk object derived from the input data
        """
        out = cls()
        for key, value in bdecode(data).iteritems():
            out.add(key, value)
        return out


class ChunkedTable(object):
    """
    Table managing Chunk objects.
    May incomplete if the ChunkedTable was created from an incomplete torrent download.
    """

    def __init__(self):
        """
        Initialize the ChunkedTable.
        """
        super(ChunkedTable, self).__init__()
        self.chunklist = {}

    def add(self, key, value):
        """
        Add a key, value (magnetlink, metadata) store to the Chunk.
        This may fail if the key/value is too big to fit into this Chunk.

        :param key: the key / magnetlink
        :param value: the value / metadata
        :returns: whether the store was added successfully
        """
        for chunk in self.chunklist.values():
            if chunk.add(key, value):
                return
        chunk = Chunk()
        if not chunk.add(key, value):
            return False # key value pair too large for any container
        self.chunklist[len(self.chunklist)] = chunk

    def remove(self, key):
        """
        Remove a key, value store by key.
        They key does not need to exist in this Chunk.

        :param key: the key to remove by
        :returns: None
        """
        empty_chunks = {}
        high_id = 0
        for chunk_id, chunk in self.chunklist.iteritems():
            if chunk_id > high_id:
                high_id = chunk_id
            chunk.remove(key)
            if not chunk.data.keys():
                empty_chunks[chunk_id] = chunk
        # Get the sequential highest-order first list of empty chunks
        if empty_chunks:
            empty_chunk_id_list = sorted(empty_chunks.keys(), reverse=True)
            index = 0
            empty_count = len(empty_chunks.keys())
            for i in xrange(high_id, -1, -1):
                if index >= empty_count:
                    break
                if empty_chunk_id_list[index] == i:
                    self.chunklist.pop(i)
                else:
                    break
                index += 1

    def serialize(self):
        """
        Create a map of Chunk serializations. Maps (chunkid -> Chunk).

        :returns: the serialized Chunk mapping
        """
        out = {}
        for i in range(len(self.chunklist)):
            out[str(i)] = self.chunklist[i].serialize()
        return out

    @classmethod
    def unserialize(cls, mapping):
        """
        Read in a ChunkedTable from a map of filenames to file contents.

        :param mapping: the serialized Chunkforms per chunk id
        :returns: the ChunkedTable corresponding to the input map
        """
        chunk_table = ChunkedTable()
        for i in mapping.keys():
            chunk_table.chunklist[int(i)] = Chunk.unserialize(mapping[i])
        return chunk_table

    def get_all(self):
        """
        Get all key/value stores in each of the Chunks.

        :return: the complete dictionary of data in the Chunks
        """
        out = {}
        for chunk in self.chunklist.values():
            out.update(chunk.data)
        return out


class Channel(object):

    def __init__(self, name, directory=".", allow_edit=False):
        """
        Create a new Channel.

        :param name: the name of the Channel
        :param directory: the directory to store the Channel
        :param allow_edit: allow addition/removal of magnetlinks (only for the Channel owner)
        """
        super(Channel, self).__init__()

        self.name = name
        self.allow_edit = allow_edit
        self.channel_directory = os.path.abspath(os.path.join(directory, name))
        if not os.path.isdir(self.channel_directory):
            os.makedirs(self.channel_directory)
        self.chunked_table = ChunkedTable()

    def add_magnetlink(self, magnetlink):
        """
        Add a magnetlink to this channel.

        TODO Future work: add metadata (always "" for now)

        :param magnetlink: the magnetlink to add
        :returns: None
        """
        self.chunked_table.add(magnetlink, "")

    def remove_magnetlink(self, magnetlink):
        """
        Remove a magnetlink from this channel.

        :param magnetlink: the magnetlink to remove
        :returns: None
        """
        self.chunked_table.remove(magnetlink)
        to_remove = set(os.listdir(self.channel_directory)) - set(self.chunked_table.chunklist.keys())
        for filename in to_remove:
            real_file = os.path.abspath(os.path.join(self.channel_directory, filename))
            os.remove(real_file)

    def get_magnetlinks(self):
        """
        Get all known magnetlinks in this Channel.

        :return: the list of magnetlinks
        """
        return self.chunked_table.get_all().keys()

    def commit(self):
        """
        Commit the added and/or removed magnetlinks to the file structure.

        :returns: None
        """
        for filename, content in self.chunked_table.serialize().iteritems():
            with open(os.path.join(self.channel_directory, filename), 'w') as f:
                f.write(content)

    def make_torrent(self):
        """
        Create a torrent from the last committed file stucture.

        :return: the resulting torrent file name, the info hash
        """
        fs = file_storage()
        add_files(fs, self.channel_directory)
        flags = 19
        t = create_torrent(fs, piece_size=PIECE_SIZE, flags=flags)
        t.set_priv(False)
        set_piece_hashes(t, os.path.dirname(self.channel_directory))
        torrent_name = os.path.join(self.channel_directory, self.name + ".torrent")
        generated = t.generate()
        with open(torrent_name, 'w') as f:
            f.write(bencode(generated))
        return torrent_name, generated['info']['root hash']

    def load(self):
        """
        Load the channel from the last committed file structure.

        :returns: None
        """
        files = os.listdir(self.channel_directory)
        data = {}
        for filename in files:
            if filename.isdigit():
                with open(os.path.join(self.channel_directory, filename), 'r') as f:
                    data[filename] = f.read()
        self.chunked_table = ChunkedTable.unserialize(data)
