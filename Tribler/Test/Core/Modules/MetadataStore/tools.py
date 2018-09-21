import filecmp
import os.path
import threading
import time
from datetime import datetime

from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.base import MetadataStore
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto

# FIXME global vars! shadowing!
crypto = ECCrypto()
key = crypto.generate_key('curve25519')
public_key = key.pub().key_to_bin()


def are_dir_trees_equal(dir1, dir2):
    """
    Shameless copypaste from https://stackoverflow.com/questions/4187564
    Compare two directories recursively. Files in each directory are
    assumed to be equal if their names and contents are equal.

    @param dir1: First directory path
    @param dir2: Second directory path

    @return: True if the directory trees are the same and
        there were no errors while accessing the directories or files,
        False otherwise.
   """

    dirs_cmp = filecmp.dircmp(dir1, dir2)
    if len(dirs_cmp.left_only) > 0 or len(dirs_cmp.right_only) > 0 or \
            len(dirs_cmp.funny_files) > 0:
        return False
    (_, mismatch, errors) = filecmp.cmpfiles(
        dir1, dir2, dirs_cmp.common_files, shallow=False)
    if len(mismatch) > 0 or len(errors) > 0:
        return False
    for common_dir in dirs_cmp.common_dirs:
        new_dir1 = os.path.join(dir1, common_dir)
        new_dir2 = os.path.join(dir2, common_dir)
        if not are_dir_trees_equal(new_dir1, new_dir2):
            return False
    return True


def generate_torrent_md_dict(n=1, key_loc=None):
    key_loc = key_loc or key
    template = {"infohash": buffer(str(n).zfill(40).decode("hex")),
                "title": "Regular Torrent" + str(n),
                "tags": "testcat.tag1.tag2. tag3 . tag4:bla.",
                "size": long(n + 1),
                "timestamp": datetime.utcnow(),
                "torrent_date": datetime.utcnow(),
                "tc_pointer": long(0),
                "public_key": buffer(key_loc.pub().key_to_bin())}
    return template


def generate_channel_md_dict(n=1, key_loc=None):
    t = generate_torrent_md_dict(n, key_loc)
    t.update({"title": "Test channel " + str(n), "version": 0})
    return t


def create_chan_serialized(results_dir, sz=10):
    mds = MetadataStore(":memory:", results_dir)
    with db_session:
        chan = mds.ChannelMD.from_dict(
            key, generate_channel_md_dict(
                n=1, key_loc=key))
        md_list = [
            mds.TorrentMD.from_dict(key, generate_torrent_md_dict(n, key))
            for n in range(0, sz)]
        chan.commit_to_torrent(key, results_dir, md_list=md_list)
        chan.to_file(os.path.join(results_dir, str(chan.title) + ".mdblob"))

def get_sample_torrent_dict(prkey):
    return {"infohash": buffer("1" * 20),
            "size": 123,
            "timestamp": datetime.utcnow(),
            "torrent_date": datetime.utcnow(),
            "tags": "bla",
            "tc_pointer": 123,
            "public_key": buffer(prkey.pub().key_to_bin()),
            "to_delete": False,
            "title": "lalala"}

def get_sample_channel_dict(prkey):
    return dict(get_sample_torrent_dict(prkey),
                votes=222,
                subscribed=False,
                version=1)
