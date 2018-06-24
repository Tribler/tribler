
import os
from libtorrent import add_files, bdecode, bencode, create_torrent, file_storage, set_piece_hashes
from MDPackXDR import serialize_metadata_gossip, CHANNEL_TORRENT
from builtins import bytes

PIECE_SIZE = 1024*1024 # 1 MB



from pony import orm
from datetime import datetime
db = orm.Database()

class MetadataGossip(db.Entity):
    num          = orm.PrimaryKey(int, auto=True)
    sig          = orm.Required(buffer)
    type         = orm.Optional(int)
    infohash     = orm.Optional(buffer)
    title        = orm.Optional(str)
    size         = orm.Optional(int)
    timestamp    = orm.Optional(datetime)
    torrent_date = orm.Optional(datetime)
    tc_pointer   = orm.Optional(int)
    public_key   = orm.Optional(buffer)
    tags         = orm.Optional(str)
    
    @classmethod
    def fromdict(cls, md_dict):
        md = cls(
            sig          = md_dict["sig"],
            type         = md_dict["type"],
            public_key   = md_dict["public_key"],
            timestamp    = md_dict["timestamp"],
            tc_pointer   = md_dict["tc_pointer"],
            infohash     = md_dict["infohash"],
            size         = md_dict["size"],
            torrent_date = md_dict["torrent_date"],
            title        = md_dict["title"],
            tags         = md_dict["tags"])
        return md

    def todict(self):
        md_dict = {
            "sig":          self.sig,
            "type":         self.type,
            "public_key":   self.public_key,
            "timestamp":    self.timestamp,
            "tc_pointer":   self.tc_pointer,
            "infohash":     self.infohash,
            "size":         self.size,
            "torrent_date": self.torrent_date,
            "title":        self.title,
            "tags":         self.tags}
        return md_dict

    def serialized(self):
        md_dict = self.todict()
        return serialize_metadata_gossip(md_dict)


db.bind(provider='sqlite', filename=':memory:')
db.generate_mapping(create_tables=True)

def create_torrent_from_dir(directory, torrent_filename):
    fs = file_storage()
    add_files(fs, directory)
    flags = 19 # ???
    t = create_torrent(fs, flags=flags)
    #t = create_torrent(fs, piece_size=PIECE_SIZE, flags=flags)
    t.set_priv(False)
    set_piece_hashes(t, os.path.dirname(directory))
    generated = t.generate()
    with open(torrent_filename, 'w') as f:
        f.write(bencode(generated))

    return generated


def create_channel_torrent(channels_store_dir, title, entries_list):
    # Create dir for metadata files
    channel_dir = os.path.abspath(os.path.join(channels_store_dir, title))
    if not os.path.isdir(channel_dir):
        os.makedirs(channel_dir)

    # Write serialized and signed metadata into files
    for i,entry in enumerate(entries_list):
        with open(os.path.join(channel_dir, str(i)), 'w') as f:
            f.write(entry)

    # Make torrent out of dir with metadata files
    torrent_filename = os.path.join(channels_store_dir, title + ".torrent")
    torrent = create_torrent_from_dir(channel_dir, torrent_filename) 

    return torrent


def create_channel(key, title, md_list, tags = ""):
    md_ser_list = [md.serialized() for md in md_list]
    channels_dir = "/tmp"
    torrent = create_channel_torrent(channels_dir, title, md_ser_list)
    now = datetime.utcnow()
    md_dict = {
            "type":         CHANNEL_TORRENT,
            "infohash":     torrent['info']['root hash'],
            "title":        title,
            "tags":         tags,
            "size":         len(md_list),
            "timestamp":    now,
            "torrent_date": now,
            "tc_pointer":   0,
            "public_key":   key.pub().key_to_bin()}

    md = create_metadata_gossip(key, md_dict)
    return md

def create_metadata_gossip(key, md_dict):
    md_ser = serialize_metadata_gossip(md_dict, key)
    with orm.db_session:
        md = MetadataGossip.fromdict(md_dict)
    return md

def join_channel(PK):
    channel_dir = fetch_channel(ChannelORM)
    consume_contents(channel_dir)


def fetch_channel(ChannelORM):
    libtorrent_download(ChannelORM.infohash)


def consume_contents(dirname):
    # Metadata is only added if its timestamp is newer than
    # the timestamp of the channel in DB.
    # We can later add skip on file numbers for efficiency
    # of making updates.
    for f in sorted(files(dirname)):
        process_metadata_package(read_file(f))

def unpack_gossip(gsp_ser):
    try:
        gsp = deserialize_gossip(gsp_ser)
    except:
        process_deserialize_error(err)
        return

    if not gossip_signature_OK(gsp_ser):
        # Possibly decrease the sender's trust rating?
        return

    if known(sig):
        # We already have this package.
        return

    if timestamp < channel(PK).timestamp:
        # This is a package from the older version of this channel.
        # It was deleted in some earlier update. We don't want it.
        return

    # If PK is unknown, we:
    #  *first* wait until all necessary
    #   procedures to add it are completed (e.g. asking friends, etc.)
    #  *then* check if it is trusted or not. This is more
    #   robust than just blindly accepting every new PK. 
    if not known(PK):
        process_new_PK(PK, source_channel)

    if not trusted(PK):
        return

    return md_ser

def unpack_metadata(md_ser):
    try:
        md = deserialize_metadata(md_ser)
    except:
        process_deserialize_error(err)
    return md

def process_metadata_package(gsp_ser, allow_delete = False):
    md = unpack_metadata(unpack_gossip(gsp_ser))
    if md.type == MD_DELETE:
        DB.metadata.remove(md.sig)
    else:
        DB.metadata.add(md)

def DB_metadata_add(md):
    # We don't do deduplication of infohashes
    # because different packagers could make different
    # uses of the same torrent.

    mdtype = md.type
    infohash = md.infohash
    size = md.size
    data = md.date
    title = md.title
    terms = stemmer(title)
    tags_parsed = parse(tags)
    terms.extend(tags_parsed.searchable)
    addition_timestamp = channel_update_ts







    

    



            


