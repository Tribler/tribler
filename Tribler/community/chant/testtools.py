import datetime
from MDPackXDR import MD_DELETE, CHANNEL_TORRENT, REGULAR_TORRENT
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto

crypto = ECCrypto()
key = crypto.generate_key('curve25519')
public_key = key.pub().key_to_bin()

def get_regular_md_dict(n=1):
    template = {"type": REGULAR_TORRENT,
                "infohash"     : str(0x1)*20,
                "title"        : "Regular Torrent " + str(n),
                "tags"         : "tag1.tag2. tag3 . tag4:bla.",
                "size"         : long(n+1),
                "timestamp"    : datetime.datetime(2005, 7, 14, 12, 30),
                "torrent_date" : datetime.datetime(2005, 7, 14, 12, 30),
                "tc_pointer"   : long(0),
                "public_key"   : key.pub().key_to_bin()}
    return template 


