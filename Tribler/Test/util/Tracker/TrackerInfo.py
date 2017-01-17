

class TrackerInfo(object):
    """
    This class keeps track of info about a tracker. This info is used when a request to a tracker is performed.
    """

    def __init__(self):
        self.infohashes = {}

    def add_info_about_infohash(self, infohash, seeders, leechers, downloaded=0):
        """
        Add information about an infohash to our tracker info.
        """
        self.infohashes[infohash] = {'seeders': seeders, 'leechers': leechers, 'downloaded': downloaded}

    def get_info_about_infohash(self, infohash):
        """
        Returns information about an infohash, None if this infohash is not in our info.
        """
        if infohash not in self.infohashes:
            return None
        return self.infohashes[infohash]

    def has_info_about_infohash(self, infohash):
        """
        Return True if we have information about a specified infohash
        """
        return infohash in self.infohashes
