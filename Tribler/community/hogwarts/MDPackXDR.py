import xdrlib
from timeutils import time2float, float2time, EPOCH
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto

INFOHASH_SIZE = 20 # bytes
IPV8_PUBLICKEY_SIZE = 74 # bytes

class MetadataTMP():
    def __init__(self,
            type_ = 0,
            infohash = str(0x0)*INFOHASH_SIZE,
            size = 0,
            date = EPOCH,
            title = "",
            tags = ""):

        self.type     = type_
        self.infohash = infohash
        self.size     = size
        self.date     = date
        self.title    = title
        self.tags     = tags


class GossipTMP():
    def __init__(self,
            type_ = 0,
            public_key = str(0x0)*IPV8_PUBLICKEY_SIZE,
            tc_pointer = 0,
            date = EPOCH,
            content = "",
            sig = None):

        self.type       = type_
        self.public_key = public_key
        self.tc_pointer = tc_pointer
        self.date       = date
        self.content    = content
        self.sig        = sig


def serialize_metadata_gossip(md, key=None):
    p = xdrlib.Packer()

    p.pack_int(                   md["type"])
    p.pack_opaque(                md["public_key"])
    p.pack_double(time2float(     md["timestamp"])
    p.pack_uhyper(                md["tc_pointer"]) # TrustChain pointer
    p.pack_fopaque(INFOHASH_SIZE, md["infohash"])
    p.pack_uhyper(                md["size"])
    p.pack_double(time2float(     md["torrent_date"]))
    p.pack_string(                md["tags"])

    if key:
        # Now we sign it
        crypto = ECCrypto()
        sig = crypto.create_signature(key, p.get_buf())
        p.pack_opaque(sig)
        md["sig"] = sig
    else:
        assert(md["sig"])
        p.pack_opaque(md["sig"])

    return p.get_buf()

def deserialize_metadata_gossip(buf, check_sig = True):
    u = xdrlib.Unpacker(buf)
    md = {}

    md["type"]                    = u.unpack_int()
    md["public_key"]              = u.unpack_opaque()
    md["timestamp"]    = float2time(u.unpack_double())
    md["tc_pointer"]              = u.unpack_uhyper()
    md["infohash"]                = u.unpack_fopaque(INFOHASH_SIZE)
    md["size"]                    = u.unpack_uhyper()
    md["torrent_date"] = float2time(u.unpack_double())
    md["tags"]                    = u.unpack_string()
    contents_end = u.get_position()
    md["sig"]                     = u.unpack_opaque()
    u.done()

    if check_sig:
        # Checking signature and PK correctness
        crypto = ECCrypto()
        crypto.is_valid_public_bin(md["public_key"])
        crypto.is_valid_signature(
                crypto.key_from_public_bin(md["public_key"]),
                buf[:contents_end],
                md["sig"])

    return md

    

    







