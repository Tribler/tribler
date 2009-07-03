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
        
        
    def trigger(self, permid, selversion, collect_candidate=None):
        infohash = self.torrent_db.selectTorrentToCollect(permid, collect_candidate)
        #print >> sys.stderr, '*****-----------***** trigger torrent collecting', `infohash`
        if infohash and self.metadata_handler:
            self.metadata_handler.send_metadata_request(permid, infohash, selversion)


