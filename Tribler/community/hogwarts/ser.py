import flatbuffers
import MDPack as MD
from timeutils import time2float, float2time
from datetime import datetime

MD_MAX_SIZE = 1000 # Maximal length of serialized metadata entry, in bytes


def serialize_strings_vector(builder, StartVectorFunction, vec):
        offsets = []
        count = len(vec)
        for s in reversed(vec):
            offsets.append(builder.CreateString(s))

        StartVectorFunction(builder, count)
        for offset in offsets:
            builder.PrependUOffsetTRelative(offset)
        vector_offset = builder.EndVector(count)
        return vector_offset

def serialize_ubytes_vector(builder, StartVectorFunction, vec):
        count = len(vec)

        StartVectorFunction(builder, count)
        for s in reversed(vec):
            builder.PrependByte(s)
        vector_offset = builder.EndVector(count)
        return vector_offset

class TorrentMetadataObj():
    
    """
    def __init__(self, infohash=[], size=0, date=datetime.utcnow(), title="", tags=[]):
        if type(infohash) == type([]):
            self.infohash = bytearray(infohash)
        self.size = size
        self.date = date
        self.title = title
        self.tags = tags
    """

    def flat(self):
        # Serialization proceeds in depth-first, last-to-first order.
        # WARNING: The serialization procedure is very sensitive to
        # the order of building of non-scalar fields
        b = flatbuffers.Builder(MD_MAX_SIZE)
        
        # TODO: there should be more efficient methods to insert byte
        # vectors into FlatBuffer. For example, NumPy interface.
        if self.tags:
            tags_offset  = b.CreateString(self.tags)
        if self.parent:
            parent_offset   = serialize_ubytes_vector(b,
                    MD.MDPackStartParentVector, bytearray(self.parent))
        title_offset = b.CreateString(self.title)
        infohash_offset = serialize_ubytes_vector(b,
                MD.MDPackStartInfohashVector, bytearray(self.infohash))

        MD.MDPackStart(b)
        if self.tags:
            MD.MDPackAddTags(b, tags_offset)
        if self.parent:
            MD.MDPackAddParent(b, parent_offset)
        MD.MDPackAddTitle(b, title_offset)
        MD.MDPackAddDate(b, time2float(self.date))
        MD.MDPackAddSize(b, self.size)
        MD.MDPackAddInfohash(b, infohash_offset)
        size = MD.MDPackEnd(b)
        b.Finish(size)

        return b.Output()

    # This esoteric construction is required to call the child class's
    # constructor when we run "fromflat" static(class) method
    @classmethod
    def fromflat(cls, buf, offset=0):
        md = MD.MDPack.GetRootAsMDPack(buf, offset)
        # FIXME: this crazy chain of type conversions is the result of 
        # Python FlatBuffers not supporting the direct loading/unloading
        # from/to "buffer" type. Someone should add it one day.
        # Nonetheless, the overhead is almost nonexistent.
        return cls(
                infohash=buffer(bytearray([md.Infohash(i) for i in range(0, md.InfohashLength())])), 
                parent  =buffer(bytearray([md.Parent(i)   for i in range(0, md.ParentLength())])), 
                size=md.Size(),
                date=float2time(md.Date()),
                title=md.Title(), 
                tags=md.Tags())


        """

#aaa = TorrentMetadataObj(date=datetime.utcnow())
for i in range(0,20):
    aaa.infohash.append(i)
i1 = aaa.infohash
flat = aaa.flat()


e = (TorrentMetadataObj.fromflat((TorrentMetadataObj.fromflat(flat)).flat())).flat()

print e==flat
"""
