from database import DiscoveryDatabase
from Tribler.Core.dispersy.singleton import Parameterized1Singleton

class CommunityMetadata(Parameterized1Singleton):
    def __init__(self, cid):
        assert isinstance(cid, str)
        assert len(cid) == 20
        self._cid = cid
        self._alias = u""
        self._comment = u""
        self.update()

    def update(self):
        # sync with database
        database = DiscoveryDatabase.get_instance()
        try:
            self._alias, self._comment = database.execute(u"SELECT alias, comment FROM community_metadata WHERE cid = ? LIMIT 1", (buffer(self._cid),)).next()
            assert isinstance(self._alias, unicode)
            assert isinstance(self._comment, unicode)

        except StopIteration:
            pass

    @property
    def cid(self):
        return self._cid

    @property
    def alias(self):
        return self._alias

    @property
    def comment(self):
        return self._comment

    def __str__(self):
        return "<{0.__class__.__name__} alias:{0.alias} comment:{0.comment}>".format(self)

