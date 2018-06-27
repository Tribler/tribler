
import os
from datetime import datetime

from libtorrent import add_files, bdecode, bencode, create_torrent, file_storage, set_piece_hashes
from MDPackXDR import serialize_metadata_gossip, deserialize_metadata_gossip, CHANNEL_TORRENT, MD_DELETE

from orm import *

channels_dir = "/tmp"

def create_torrent_from_dir(directory, torrent_filename):
    fs = file_storage()
    add_files(fs, directory)
    t = create_torrent(fs, flags=19 ) #??? 19 ???
    t.set_priv(False)
    set_piece_hashes(t, os.path.dirname(directory))
    generated = t.generate()
    with open(torrent_filename, 'w') as f:
        f.write(bencode(generated))

    return generated

def create_channel_torrent(channels_store_dir, title, buf_list, version):
    # Create dir for metadata files
    channel_dir = os.path.abspath(os.path.join(channels_store_dir, title))
    if not os.path.isdir(channel_dir):
        os.makedirs(channel_dir)

    # Write serialized and signed metadata into files
    for buf in buf_list:
        version += 1
        with open(os.path.join(channel_dir, str(version)), 'w') as f:
            f.write(buf)

    # Make torrent out of dir with metadata files
    torrent_filename = os.path.join(channels_store_dir, title + ".torrent")
    torrent = create_torrent_from_dir(channel_dir, torrent_filename) 

    return torrent, version

def update_channel(key, channel, add_list=[], remove_list=[]):
    buf_list = []
    for e in remove_list:
        del_entry = {"type"       : MD_DELETE,
                     "public_key" : e.public_key,
                     "timestamp"  : datetime.utcnow(),
                     "tc_pointer" : 0,
                     "delete_sig" : e.sig}
        buf = serialize_metadata_gossip(del_entry, key)
        buf_list.append(buf)

    new_channel = create_channel(key, channel.title, buf_list, add_list,
            version=channel.version, tags=channel.tags)
    channel.delete()

    # Re-read the renewed channel torrent dir to delete obsolete entries
    process_channel_dir(os.path.join(channels_dir, channel.title))
    return new_channel

def create_channel(key, title, buf_list=[], add_list=[], version=0, tags = ""):
    buf_list.extend([e.serialized() for e in add_list])
    (torrent, version) = create_channel_torrent(channels_dir, title,
            buf_list, version)

    now = datetime.utcnow()
    md = create_metadata_gossip(key, 
           {"type":         CHANNEL_TORRENT,
            "infohash":     torrent['info']['root hash'],
            "title":        title,
            "tags":         tags,
            "size":         len(buf_list),#FIXME
            "timestamp":    now,
            "version":      version,
            "torrent_date": now,
            "tc_pointer":   0,
            "public_key":   key.pub().key_to_bin()})
    return md

def create_metadata_gossip(key, md_dict):
    md_ser = serialize_metadata_gossip(md_dict, key)
    md = MetadataGossip(**md_dict)
    return md

def join_channel(PK):
    channel_dir = libtorrent_download(ChannelORM.infohash)
    process_channel_dir(channel_dir)

def process_channel_dir(dirname):
    # TODO: add skip on file numbers for efficiency of updates.
    now = datetime.utcnow()
    for filename in sorted(os.listdir(dirname)):
        with open(os.path.join(dirname, filename)) as f:
            gsp = deserialize_metadata_gossip(f.read())
            if check_gossip(gsp):
                if gsp["type"] == MD_DELETE:
                    # We check for public key to prevent abuse
                    obsolete_entry = MetadataGossip.get(sig=gsp["delete_sig"],
                            public_key=gsp["public_key"])
                    if obsolete_entry:
                        obsolete_entry.delete()
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

    #parent_channel = MetadataGossip.get(type=CHANNEL_TORRENT, public_key=PK)
    if known_sig(gsp["sig"]):
        # We already have this gossip.
        return

    return True

