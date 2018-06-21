import xdrlib
from timeutils import time2float, float2time, EPOCH
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto

INFOHASH_SIZE = 20 # bytes
IPV8_PUBLICKEY_SIZE = 74 # bytes

class MetadataTMP():
    def __init__(self):
        self.type = 0
        self.infohash = str(0x0)*INFOHASH_SIZE
        self.size = 0
        self.date = EPOCH
        self.title = ""
        self.tags = ""

class GossipTMP():
    def __init__(self):
        self.type = 0
        self.public_key = str(0x0)*IPV8_PUBLICKEY_SIZE
        self.tc_pointer = 0
        self.date = EPOCH
        self.content = ""
        self.sig = ""

def serialize_metadata(md):
    p = xdrlib.Packer()

    p.pack_int(md.type)
    p.pack_fopaque(INFOHASH_SIZE, md.infohash)
    p.pack_uhyper(md.size)
    p.pack_double(time2float(md.date))
    p.pack_string(md.tags)

    return p.get_buf()

def deserialize_metadata(buf):
    u = xdrlib.Unpacker(buf)

    md = MetadataTMP()
    md.type = u.unpack_int()
    md.infohash = u.unpack_fopaque(INFOHASH_SIZE)
    md.size = u.unpack_uhyper()
    md.date = float2time(u.unpack_double())
    md.tags = u.unpack_string()
    u.done()
    
    return md


def serialize_gossip(key, gsp):
    p = xdrlib.Packer()

    p.pack_int(gsp.type)
    p.pack_opaque(gsp.public_key)
    p.pack_double(time2float(gsp.date))
    p.pack_uhyper(gsp.tc_pointer) # TrustChain pointer
    p.pack_opaque(gsp.content)

    # Now we sign it
    crypto = ECCrypto()
    sig = crypto.create_signature(key, p.get_buf())
    p.pack_opaque(sig)

    return p.get_buf()

def deserialize_gossip(buf):
    u = xdrlib.Unpacker(buf)
    gsp = GossipTMP()

    gsp.type    = u.unpack_int()
    gsp.public_key  = u.unpack_opaque()
    gsp.date        = float2time(u.unpack_double())
    gsp.tc_pointer  = u.unpack_uhyper()
    gsp.content     = u.unpack_opaque()
    gsp.sig         = u.unpack_opaque()
    u.done()

    # Checking signature and PK correctness
    crypto = ECCrypto()
    crypto.is_valid_public_bin(gsp.public_key)
    crypto.is_valid_signature(
            crypto.key_from_public_bin(gsp.public_key),
            gsp.content, gsp.sig)

    return gsp

    

    







