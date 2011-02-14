from Tribler.Core.dispersy.payload import Payload

class UserMetadataPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, address, alias, comment):
            assert isinstance(address, tuple)
            assert len(address) == 2
            assert isinstance(address[0], str)
            assert isinstance(address[1], int)
            assert isinstance(alias, unicode)
            assert isinstance(comment, unicode)
            super(UserMetadataPayload.Implementation, self).__init__(meta)
            self._address = address
            self._alias = alias
            self._comment = comment

        @property
        def address(self):
            return self._address

        @property
        def alias(self):
            return self._alias

        @property
        def comment(self):
            return self._comment

class CommunityMetadataPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, cid, alias, comment):
            assert isinstance(cid, str)
            assert len(cid) == 20
            assert isinstance(alias, unicode)
            assert isinstance(comment, unicode)
            super(CommunityMetadataPayload.Implementation, self).__init__(meta)
            self._cid = cid
            self._alias = alias
            self._comment = comment

        @property
        def cid(self):
            return self._cid

        @property
        def alias(self):
            return self._alias

        @property
        def comment(self):
            return self._comment
