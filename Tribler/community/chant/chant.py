import os
from datetime import datetime

from pony import orm
from pony.orm import db_session
from libtorrent import add_files, bdecode, bencode, create_torrent, file_storage, set_piece_hashes, torrent_info
from Tribler.community.chant.MDPackXDR import serialize_metadata_gossip, \
    deserialize_metadata_gossip, CHANNEL_TORRENT, MD_DELETE, REGULAR_TORRENT

from Tribler.community.chant.orm import MetadataGossip, PeerORM, known_signature, known_pk, trusted_pk



def create_torrent_from_dir(directory, torrent_filename):
    fs = file_storage()
    add_files(fs, directory)
    t = create_torrent(fs)
    # FIXME: for a torrent created with flags=19 with 200+ small files
    # libtorrent client_test can't see it's files on disk.
    # optimize_alignment + merke + mutable_torrent_support = 19
    #t = create_torrent(fs, flags=19) # BUG?
    t.set_priv(False)
    set_piece_hashes(t, os.path.dirname(directory))
    torrent = t.generate()
    with open(torrent_filename, 'w') as f:
        f.write(bencode(torrent))

    infohash = torrent_info(torrent).info_hash().to_bytes()
    return infohash


def create_channel_torrent(channels_store_dir, title, buf_list, version):
    # Create dir for metadata files
    channel_dir = os.path.abspath(os.path.join(channels_store_dir, title))
    if not os.path.isdir(channel_dir):
        os.makedirs(channel_dir)

    # Write serialized and signed metadata into files
    for buf in buf_list:
        version += 1
        with open(os.path.join(channel_dir, str(version).zfill(9)), 'w') as f:
            f.write(buf)

    # Make torrent out of dir with metadata files
    torrent_filename = os.path.join(channels_store_dir, title + ".torrent")
    infohash = create_torrent_from_dir(channel_dir, torrent_filename)

    return infohash, version


def update_channel(key, old_channel, channels_dir, add_list=None, remove_list=None, buf_list=None):
    if not add_list:
        add_list = []
    if not remove_list:
        remove_list = []
    if not buf_list:
        buf_list = []
    for e in remove_list:
        del_entry = {"type": MD_DELETE,
                     "public_key": e.public_key,
                     "timestamp": datetime.utcnow(),
                     "tc_pointer": 0,
                     "delete_signature": e.signature}
        buf = serialize_metadata_gossip(del_entry, key)
        buf_list.append(buf)

    new_channel = create_channel(key, old_channel.title, channels_dir, buf_list, add_list,
                                 version=old_channel.version, tags=old_channel.tags)
    old_channel.delete()

    # Re-read the renewed channel torrent dir to delete obsolete entries
    process_channel_dir(os.path.join(channels_dir, old_channel.title))
    return new_channel


def create_channel(key, title, channels_dir, buf_list=None, add_list=None, version=0, tags=""):
    if not add_list:
        add_list = []
    if not buf_list:
        buf_list = []
    buf_list.extend([e.serialized() for e in add_list])
    (infohash, version) = create_channel_torrent(channels_dir, title,
                                                buf_list, version)

    #print str(infohash).encode("hex")

    now = datetime.utcnow()
    md = create_metadata_gossip(key,
                                {"type": CHANNEL_TORRENT,
                                 "infohash": infohash ,
                                 "title": title,
                                 "tags": tags,
                                 "size": len(buf_list),  # FIXME
                                 "timestamp": now,
                                 "version": version,
                                 "torrent_date": now,
                                 "tc_pointer": 0,
                                 "public_key": key.pub().key_to_bin()})
    return md


def create_metadata_gossip(key, md_dict):
    serialize_metadata_gossip(md_dict, key)
    md = MetadataGossip(**md_dict)
    return md


@db_session
def process_channel_dir(dirname):
    # TODO: add skip on file numbers for efficiency of updates.
    now = datetime.utcnow()
    for filename in sorted(os.listdir(dirname)):
        with open(os.path.join(dirname, filename)) as f:
            gsp = deserialize_metadata_gossip(f.read())
            #print filename
            if check_gossip(gsp):
                if gsp["type"] == MD_DELETE:
                    # We check for public key to prevent abuse
                    obsolete_entry = MetadataGossip.get(signature=gsp["delete_signature"],
                                                        public_key=gsp["public_key"])
                    if obsolete_entry:
                        obsolete_entry.delete()
                else:
                    MetadataGossip(addition_timestamp=now, **gsp)


def process_new_PK(pk):
    # Stub
    PeerORM(public_key=pk, trusted=True, update_timestamp=datetime.utcnow())


def check_gossip(gsp):
    PK = gsp["public_key"]
    # If PK is unknown, we:
    #  *first* wait until all necessary
    #   procedures to add it are completed (e.g. asking friends, etc.)
    if not known_pk(PK):
        process_new_PK(PK)
    #  *next* check if it is trusted or not.
    if not trusted_pk(PK):
        return False

    # parent_channel = MetadataGossip.get(type=CHANNEL_TORRENT, public_key=PK)
    if known_signature(gsp["signature"]):
        # We already have this gossip.
        return False

    return True


def list_channel(channel):
    md_list = orm.select(g for g in MetadataGossip if
                         g.public_key == channel.public_key and
                         g.type == REGULAR_TORRENT)[:]
    return md_list

@db_session
def search_local_channels(query):
    from time import mktime
    results_list = MetadataGossip.search_keyword(query, CHANNEL_TORRENT)
    # Format:
    #  0 |       1      |   2  |       3     |       4     |  5          |   6      |     7    |         |     8           |
    # id | dispersy_cid | name | description | nr_torrents | nr_favorite | nr_spam  | modified | my_vote | relevance_score |
    search_results = []

    for r in results_list:
        favorite = 1
        my_vote = 0
        spam = 0
        relevance = 0.9
        unix_timestamp = r.torrent_date
        entry = (r.rowid, str(r.public_key), r.title, r.tags, int(r.size), favorite, spam , unix_timestamp, my_vote, relevance)
        search_results.append(entry)

    return search_results

@db_session
def search_local_torrents(query):
    results_list = MetadataGossip.search_keyword(query, REGULAR_TORRENT)
    search_results = []

    for r in results_list:
        favorite = 1
        my_vote = 0
        spam = 0
        relevance = 0.9
        unix_timestamp = r.torrent_date
        seeders = 0
        leechers = 0
        last_tracker_check = 0
        category = r.tags.split(".")[0]
        infohash = str(r.infohash)
        entry = (r.rowid, infohash, r.title, int(r.size), category, seeders, leechers, last_tracker_check, None, relevance)
        search_results.append(entry)

    return search_results


def getAutoCompleteTerms(keyword, max_terms, limit=100):
    #FIXME: kinda works, but far from perfect
    with db_session:
        result = MetadataGossip.search_keyword(keyword+"*", lim=limit)
        titles = [g.title.lower() for g in result]

    #Totally copy-pasted from the old DBHandler
    all_terms = set()
    for line in titles:
        if len(all_terms) >= max_terms:
            break
        i1 = line.find(keyword)
        i2 = line.find(' ', i1 + len(keyword))
        all_terms.add(line[i1:i2] if i2 >= 0 else line[i1:])

    if keyword in all_terms:
        all_terms.remove(keyword)
    if '' in all_terms:
        all_terms.remove('')

    return list(all_terms)




