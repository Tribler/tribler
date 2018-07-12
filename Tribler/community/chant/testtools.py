import datetime
from Tribler.community.chant.MDPackXDR import REGULAR_TORRENT, deserialize_metadata_gossip
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto

from Tribler.community.chant.chant import MetadataGossip, create_channel, create_metadata_gossip
from pony.orm import db_session
from Tribler.community.chant.orm import start_orm, db
import os
from pony import orm
from pony.orm import db_session

crypto = ECCrypto()
key = crypto.generate_key('curve25519')
public_key = key.pub().key_to_bin()

def get_regular_md_dict(n=1):
    template = {"type": REGULAR_TORRENT,
                "infohash"     : str(n).zfill(40).decode("hex"),
                "title"        : "Regular Torrent" + str(n),
                "tags"         : "testcat.tag1.tag2. tag3 . tag4:bla.",
                "size"         : long(n+1),
                "timestamp"    : datetime.datetime(2005, 7, 14, 12, 30),
                "torrent_date" : datetime.datetime(2005, 7, 14, 12, 30),
                "tc_pointer"   : long(0),
                "public_key"   : key.pub().key_to_bin()}
    return template


def create_chan_serialized(sz=1000):
    db_filename = ":memory:"
    start_orm(db_filename, create_db=True)
    title = "Channel 1"
    md_dict_list = [get_regular_md_dict(n) for n in range(0, sz)]
    for md_dict in md_dict_list:
        create_metadata_gossip(key=key, md_dict=md_dict)
    md_list = orm.select(g for g in MetadataGossip)[:]

    channels_dir = os.path.abspath('./testdata')
    channel_dir = os.path.abspath(os.path.join(channels_dir, title))
    chan = create_channel(key, title, channels_dir, add_list=md_list, tags="some.tags")
    with open(os.path.join(channels_dir, 'channel.serialized'), 'w') as f:
        f.write(chan.serialized())

@db_session
def LoadGspFromDisk(filename):
    with open(filename) as f:
        gsp = deserialize_metadata_gossip(f.read())
    now = datetime.datetime.utcnow()
    return MetadataGossip(addition_timestamp=now, **gsp)


def create_sample_db(db_filename, chans=10, chansize=100):
    start_orm(db_filename, create_db=True)
    channels_dir = os.path.abspath('./testdata')

    with db_session:
        for startnum in xrange(0, chans*chansize, chansize):
            key = crypto.generate_key('curve25519')
            public_key = key.pub().key_to_bin()
            md_list = []
            for md_dict in [get_regular_md_dict(n) for n in xrange(startnum, startnum+chansize)]:
                md_list.append(create_metadata_gossip(key=key, md_dict=md_dict))
            title = "Test chan " + str(startnum)
            chan = create_channel(key, title, channels_dir,
                    add_list=md_list, tags="tchan chn" + str(startnum))
    


