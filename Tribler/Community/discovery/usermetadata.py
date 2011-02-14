from database import DiscoveryDatabase
from Tribler.Core.dispersy.singleton import Parameterized1Singleton

class UserMetadata(Parameterized1Singleton):
    def __init__(self, member):
        if __debug__:
            from Tribler.Core.Dispersy.Member import Member
            assert isinstance(member, Member)
        self._member = member
        self._address = ("", -1)
        self._alias = u""
        self._comment = u""
        self.update()

    def update(self):
        # sync with database
        database = DiscoveryDatabase.get_instance()
        try:
            host, port, self._alias, self._comment = database.execute(u"SELECT host, port, alias, comment FROM user_metadata WHERE user = ? LIMIT 1", (self._member.database_id,)).next()
            self._address = (str(host), port)
            assert isinstance(self._address[0], str)
            assert isinstance(self._address[1], int)
            assert isinstance(self._alias, unicode)
            assert isinstance(self._comment, unicode)

        except StopIteration:
            pass

    @property
    def address(self):
        return self._address

    @property
    def alias(self):
        return self._alias

    @property
    def comment(self):
        return self._comment

    def __str__(self):
        return "<{0.__class__.__name__} address:{o.address[0]}:{0.address[1]} alias:{0.alias} comment:{0.comment}>".format(self)

