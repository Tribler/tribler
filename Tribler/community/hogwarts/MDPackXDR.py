import xdrlib
from timeutils import time2float, float2time, EPOCH

class MetadataTMP():
    def __init__(self):
        self.type = 0
        self.infohash = str(0x0)*20
        self.size = 0
        self.date = EPOCH
        self.title = ""
        self.tags = ""
        


        


def serialize_metadata(md):
    p = xdrlib.Packer()

    p.pack_int(md.type)
    p.pack_fopaque(20, md.infohash)
    p.pack_uhyper(md.size)
    p.pack_double(time2float(md.date))
    p.pack_string(md.tags)

    return p.get_buf()


def deserialize_metadata(buf):
    u = xdrlib.Unpacker(buf)

    md = MetadataTMP()
    md.type = u.unpack_int()
    md.infohash = u.unpack_fopaque(20)
    md.size = u.unpack_uhyper()
    md.date = float2time(u.unpack_double())
    md.tags = u.unpack_string()
    u.done()
    
    return md


