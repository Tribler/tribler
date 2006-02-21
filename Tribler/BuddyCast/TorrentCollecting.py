import sys
from Tribler.CacheDB.CacheDBHandler import TorrentDBHandler, PeerDBHandler
from Tribler.utilities import sortList


DEBUG = False    
    
class TorrentFetcher:
    def __init__(self, size=10, db_dir=''):
        self.size = size
        self.torrent_db = TorrentDBHandler(db_dir=db_dir)
        self.peer_db = PeerDBHandler(db_dir=db_dir)
        self.todo_cache = {}
        self.done_cache = {}
        
    def _reload(self):    # reload some torrents into todo cache
        def incache(infohash):
            return (infohash not in self.todo_cache) and (infohash not in self.done_cache)
            
        empty_torrents = self.torrent_db.getNoMetaTorrents()    #TODO: performance improve - check if db has changed
        empty_torrents = filter(incache, empty_torrents)    # remove cached torrents
        relevance =  self.torrent_db.getTorrentsValue(empty_torrents, ['relevance'])
        len_toadd = self.size - len(self.todo_cache)
        if len_toadd < 0:
            len_toadd = 0
        recom_list = sortList(empty_torrents, relevance)[:len_toadd]
        for t in recom_list:
            owners = self.torrent_db.getOwners(t)
            if owners:
                self.todo_cache[t] = owners
        
    def getTask(self, num_owners=6):    # select a torrent infohash to collect its metadata
        if len(self.todo_cache) == 0:
            self._reload()
        if len(self.todo_cache) == 0:    # no torrent
            return None
        torrent = self.todo_cache.keys()[0]
        all_owners = self.todo_cache.pop(torrent)
        ages = self.peer_db.getPeersValue(all_owners, ['last_seen'])
        owners = sortList(all_owners, ages)[:num_owners]
        self.done_cache[torrent] = None
        return (torrent, owners)
        
    def hasMetaData(self, infohash):
        return self.torrent_db.hasMetaData(infohash)
    

class JobQueue:
    def __init__(self, maxsize, num_owners, db_dir=''):
        self.maxsize = maxsize
        self.num_owners = num_owners
        self._queue = [None]*maxsize
        self.pointer = 0    # check pointer
        self.fetcher = TorrentFetcher(self.maxsize, db_dir)
        
    def load(self):
        while len(self._queue) < self.maxsize:
            task = self.fetcher.getTask(self.num_owners)
            if not task:
                break
            self._queue.append(task)
        
    def getJob(self):
        # load a new task if there is a vacancy or all owners have been used or the job has been done
        if DEBUG:
            print ">>>", self.pointer
        if not self._queue[self.pointer] or not self._queue[self.pointer][1] or \
            self.fetcher.hasMetaData(self._queue[self.pointer][0]):    
            task = self.fetcher.getTask(self.num_owners)
            self._queue[self.pointer] = task
            if DEBUG:
                if task is None:
                    print "** new task", task
                else:
                    print "** new task", task[0], task[1][:3]
                if self._queue[self.pointer]:
                    print "** ", self.fetcher.hasMetaData(self._queue[self.pointer][0]), self._queue[self.pointer][1][:3]
        task = self._queue[self.pointer]
        self.pointer += 1    
        if self.pointer >= self.maxsize:
            self.pointer = 0
        if task:
            infohash, owners = task
            if owners and len(owners) > 0:
                permid = owners.pop(0)
                return infohash, permid

# TODO: implement click and download
class TorrentCollecting:
    __single = None
    
    def __init__(self, db_dir=''):
        if TorrentCollecting.__single:
            raise RuntimeError, "TorrentCollecting is singleton"
        TorrentCollecting.__single = self 
        self.registered = False   
        self.collect_interval = 11    # use prime to avoid conflict
        self.queue_length = 31
        self.num_owners = 6        # max number of owners of a torrent
        self.job_queue = JobQueue(self.queue_length, self.num_owners, db_dir)
        
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
            self.startup()
            
    def startup(self):
        #self.job_queue.load()
        if self.registered:
            print >> sys.stderr, "collect: Torrent collecting starts up"
            self.rawserver.add_task(self.collect, self.collect_interval)
    
    def collect(self):
        self.rawserver.add_task(self.collect, self.collect_interval)
        job = self.job_queue.getJob()
        if job:
            infohash, permid = job
            self.metadata_handler.send_metadata_request(permid, infohash)
            if DEBUG:
                print "got job: ", permid, infohash
                for x in self.job_queue._queue:
                    if x is None:
                        print x
                    else:
                        id, q = x
                        print id, len(q), q[:3]
                print '-------------'
            
                
    def test(self):
        #self.rawserver.add_task(self.test, self.test_interval)
        pass
        
        
        