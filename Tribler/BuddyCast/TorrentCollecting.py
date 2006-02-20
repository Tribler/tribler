

class JobQueue:
    def __init__(self, maxsize):
        pass

# TODO: implement click and download
class TorrentCollecting:
    __single = None
    
    def __init__(self, db_dir=''):
        if TorrentCollecting.__single:
            raise RuntimeError, "TorrentCollecting is singleton"
        TorrentCollecting.__single = self 
        self.registered = False   
        self.collect_interval = 4    # use prime to avoid conflict
        self.queue_length = 10
        self._queue = JobQueue(self.queue_length)     
        
    def getInstance(*args, **kw):
        if TorrentCollecting.__single is None:
            TorrentCollecting(*args, **kw)
        return TorrentCollecting.__single
    getInstance = staticmethod(getInstance)
    
    def register(self, secure_overlay, rawserver, metadata_handler):
        if not self.registered:
            self.secure_overlay = secure_overlay
            self.rawserver = rawserver
            self.metadata_handler = metadata_handler
            self.registered = True
        
    def startup(self):
        if self.registered:
            self.rawserver.add_task(self.collect, self.collect_interval)
    
    def collect(self):
        print "collect torrent"