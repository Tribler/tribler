# Written by Jie Yang
# see LICENSE.txt for license information

DEBUG = False

class SimpleTorrentCollecting:
    """
        Simplest torrent collecting policy: randomly collect a torrent when received
        a buddycast message
    """
    
    def __init__(self, metadata_handler, data_handler):
        self.metadata_handler = metadata_handler
        self.data_handler = data_handler
        self.torrent_db = data_handler.torrent_db
        self.pref_db = data_handler.pref_db
        self.cache_pool = {}
        
        
    def trigger(self, permid, selversion, collect_candidate=[]):
        assert isinstance(collect_candidate, list)
        if self.metadata_handler:
            for infohash in self.torrent_db.selectTorrentsToCollect(permid, collect_candidate, 50, 50):
                self.metadata_handler.send_metadata_request(permid, infohash, selversion)
