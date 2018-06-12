import flatbuffers
import TorrentMetadata as MD
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
    
    def __init__(self, infohash=[], size=0, date=datetime.utcnow(), title="", tags=[]):
        if type(infohash) == type([]):
            self.infohash = bytearray(infohash)
        self.size = size
        self.date = date
        self.title = title
        self.tags = tags

    def flat(self):
        # Serialization proceeds in depth-first, last-to-first order.
        # WARNING: The serialization procedure is very sensitive to
        # the order of building of non-scalar fields
        b = flatbuffers.Builder(MD_MAX_SIZE)
        
        # TODO: there should be more efficient methods to copy byte
        # vectors to FlatBuffer. For example, NumPy interface.
        tags_offset = serialize_strings_vector(b, 
                MD.TorrentMetadataStartTagsVector, self.tags)

        title_offset = b.CreateString(self.title)
        infohash_offset = serialize_ubytes_vector(b,
                MD.TorrentMetadataStartInfohashVector, self.infohash)

        MD.TorrentMetadataStart(b)
        MD.TorrentMetadataAddTags(b, tags_offset)
        MD.TorrentMetadataAddTitle(b, title_offset)
        MD.TorrentMetadataAddDate(b, time2float(self.date))
        MD.TorrentMetadataAddSize(b, self.size)
        MD.TorrentMetadataAddInfohash(b, infohash_offset)
        size = MD.TorrentMetadataEnd(b)
        b.Finish(size)

        return b.Output()

    @classmethod
    def fromflat(cls, buf, offset=0):
        md = MD.TorrentMetadata.GetRootAsTorrentMetadata(buf, offset)
        return TorrentMetadataObj(
                infohash=[md.Infohash(i) for i in range(0, md.InfohashLength())], 
                size=md.Size(), date=float2time(md.Date()), title=md.Title(), 
                tags=[md.Tags(i) for i in range(0, md.TagsLength())])


aaa = TorrentMetadataObj(date=datetime.utcnow())
for i in range(0,20):
    aaa.infohash.append(i)
i1 = aaa.infohash
flat = aaa.flat()


e = (TorrentMetadataObj.fromflat((TorrentMetadataObj.fromflat(flat)).flat())).flat()

print e==flat
