
import os
from libtorrent import add_files, bdecode, bencode, create_torrent, file_storage, set_piece_hashes
from MDPackXDR import serialize_metadata_gossip, deserialize_metadata_gossip, CHANNEL_TORRENT, MD_DELETE

from orm import *

PIECE_SIZE = 1024*1024 # 1 MB

from datetime import datetime

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
    md = MetadataGossip(**md_dict)
    return md

def join_channel(PK):
    channel_dir = fetch_channel(ChannelORM)
    process_channel_dir(channel_dir)

def fetch_channel(ChannelORM):
    libtorrent_download(ChannelORM.infohash)

def process_channel_dir(dirname):
    # TODO: add skip on file numbers for efficiency of updates.
    now = datetime.utcnow()
    for filename in sorted(os.listdir(dirname)):
        with open(os.path.join(dirname, filename)) as f:
            gsp = deserialize_metadata_gossip(f.read())
            if check_gossip(gsp):
                if gsp["type"] == MD_DELETE:
                    # We check for public key to prevent abuse
                    MetadataGossip.get(sig=gsp["delete_sig"],
                            public_key=gsp["public_key"])
                else:
                    MetadataGossip(addition_timestamp=now,**gsp)

def process_new_PK(pk):
    # Stub
    Peer(public_key=pk, trusted=True, update_timestamp=datetime.utcnow())

def check_gossip(gsp):
    PK = gsp["public_key"]
    # If PK is unknown, we:
    #  *first* wait until all necessary
    #   procedures to add it are completed (e.g. asking friends, etc.)
    if not known_pk(PK):
        process_new_PK(PK)
    #  *next* check if it is trusted or not.
    if not trusted_pk(PK):
        return

    parent_channel = MetadataGossip.get(type=CHANNEL_TORRENT, public_key=PK)

    #if gsp["timestamp"] < parent_channel.timestamp:
        # This gossip is outdated.
        #return

    if known_sig(gsp["sig"]):
        # We already have this gossip.
        return

    return True

            


