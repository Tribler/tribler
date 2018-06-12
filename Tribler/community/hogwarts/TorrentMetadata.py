# automatically generated by the FlatBuffers compiler, do not modify

# namespace: 

import flatbuffers

class TorrentMetadata(object):
    __slots__ = ['_tab']

    @classmethod
    def GetRootAsTorrentMetadata(cls, buf, offset):
        n = flatbuffers.encode.Get(flatbuffers.packer.uoffset, buf, offset)
        x = TorrentMetadata()
        x.Init(buf, n + offset)
        return x

    # TorrentMetadata
    def Init(self, buf, pos):
        self._tab = flatbuffers.table.Table(buf, pos)

    # TorrentMetadata
    def Infohash(self, j):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(4))
        if o != 0:
            a = self._tab.Vector(o)
            return self._tab.Get(flatbuffers.number_types.Uint8Flags, a + flatbuffers.number_types.UOffsetTFlags.py_type(j * 1))
        return 0

    # TorrentMetadata
    def InfohashAsNumpy(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(4))
        if o != 0:
            return self._tab.GetVectorAsNumpy(flatbuffers.number_types.Uint8Flags, o)
        return 0

    # TorrentMetadata
    def InfohashLength(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(4))
        if o != 0:
            return self._tab.VectorLen(o)
        return 0

    # TorrentMetadata
    def Size(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(6))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Uint64Flags, o + self._tab.Pos)
        return 0

    # TorrentMetadata
    def Date(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(8))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Float64Flags, o + self._tab.Pos)
        return 0.0

    # TorrentMetadata
    def Title(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(10))
        if o != 0:
            return self._tab.String(o + self._tab.Pos)
        return None

    # TorrentMetadata
    def Tags(self, j):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(12))
        if o != 0:
            a = self._tab.Vector(o)
            return self._tab.String(a + flatbuffers.number_types.UOffsetTFlags.py_type(j * 4))
        return ""

    # TorrentMetadata
    def TagsLength(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(12))
        if o != 0:
            return self._tab.VectorLen(o)
        return 0

def TorrentMetadataStart(builder): builder.StartObject(5)
def TorrentMetadataAddInfohash(builder, infohash): builder.PrependUOffsetTRelativeSlot(0, flatbuffers.number_types.UOffsetTFlags.py_type(infohash), 0)
def TorrentMetadataStartInfohashVector(builder, numElems): return builder.StartVector(1, numElems, 1)
def TorrentMetadataAddSize(builder, size): builder.PrependUint64Slot(1, size, 0)
def TorrentMetadataAddDate(builder, date): builder.PrependFloat64Slot(2, date, 0.0)
def TorrentMetadataAddTitle(builder, title): builder.PrependUOffsetTRelativeSlot(3, flatbuffers.number_types.UOffsetTFlags.py_type(title), 0)
def TorrentMetadataAddTags(builder, tags): builder.PrependUOffsetTRelativeSlot(4, flatbuffers.number_types.UOffsetTFlags.py_type(tags), 0)
def TorrentMetadataStartTagsVector(builder, numElems): return builder.StartVector(4, numElems, 4)
def TorrentMetadataEnd(builder): return builder.EndObject()
