import logging


class Helper(object):
    __slots__ = ('_logger', '_cache')

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._cache = {}

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __contains__(self, key):
        return key in self.__slots__

    def __eq__(self, other):
        if other and hasattr(self, 'id') and hasattr(other, 'id'):
            return self.id == other.id
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __getstate__(self):
        statedict = {}
        for key in self.__slots__:
            statedict[key] = getattr(self, key, None)
        return statedict

    def __setstate__(self, statedict):
        for key, value in statedict.iteritems():
            setattr(self, key, value)


class Channel(Helper):
    __slots__ = ('id', 'dispersy_cid', 'name', 'description', 'nr_torrents', 'nr_favorites',
                 'nr_spam', 'my_vote', 'modified', 'my_channel', 'torrents', 'popular_torrents')

    def __init__(self, id, dispersy_cid, name, description, nr_torrents, nr_favorites, nr_spam, my_vote, modified, my_channel):
        Helper.__init__(self)

        self.id = id
        self.dispersy_cid = str(dispersy_cid)

        self.name = name[:40]
        self.description = description[:1024]

        self.nr_torrents = nr_torrents
        self.nr_favorites = nr_favorites or 0
        self.nr_spam = nr_spam or 0
        self.my_vote = my_vote
        self.modified = modified
        self.my_channel = my_channel
        self.torrents = None
        self.popular_torrents = None

    def isDispersy(self):
        return len(self.dispersy_cid) == 20

    def isFavorite(self):
        return self.my_vote == 2

    def isSpam(self):
        return self.my_vote == -1

    def isMyChannel(self):
        return self.my_channel

    def isEmpty(self):
        return self.nr_torrents == 0

    def __eq__(self, other):
        if other:
            if isinstance(other, Channel):
                return self.id == other.id
            if isinstance(other, int):
                return self.id == other
        return False

    def __str__(self):
        return 'Channel name=%s\nid=%d\ndispersy_cid=%s' % (self.name.encode('utf8'), self.id, self.dispersy_cid.encode("HEX"))
