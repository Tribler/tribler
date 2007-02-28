import sys
from Tribler.CacheDB.CacheDBHandler import TorrentDBHandler, PeerDBHandler
from Tribler.utilities import sortList,show_permid_short
from random import randint

DEBUG = False
debug = 1
    
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
            print >>sys.stderr,"tcollect: getJob: pointer is", self.pointer
        if not self._queue[self.pointer] or not self._queue[self.pointer][1] or \
            self.fetcher.hasMetaData(self._queue[self.pointer][0]):    
            task = self.fetcher.getTask(self.num_owners)
            self._queue[self.pointer] = task
            if DEBUG:
                if task is not None:
                    print >>sys.stderr,"tcollect: getJob: task is None"
                else:
                    print >>sys.stderr,"tcollect: getJob: new task",task2string(task)
                if self._queue[self.pointer]:
                    print >>sys.stderr,"tcollect: getJob: has metadata", self.fetcher.hasMetaData(self._queue[self.pointer][0]), owners2string(self._queue[self.pointer][1])
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
            if DEBUG:
                print >> sys.stderr, "tcollect: Torrent collecting starts up"
            self.rawserver.add_task(self.collect, self.collect_interval)
    
    def collect(self):
        self.rawserver.add_task(self.collect, self.collect_interval)
        job = self.job_queue.getJob()
        if job:
            infohash, permid = job
            self.metadata_handler.send_metadata_request(permid, infohash)
            if DEBUG:
                print >>sys.stderr,"tcollect: collect: requested",`infohash`,"from",show_permid_short(permid)
                print >>sys.stderr,"tcollect: collect: showing job queue:"
                for x in self.job_queue._queue:
                    if x is not None:
                        print >>sys.stderr,"tcollect: collect: queued job is ",task2string(x)
                print >>sys.stderr,"tcollect: collect: end-of-queue"
            
                
    def test(self):
        #self.rawserver.add_task(self.test, self.test_interval)
        pass
        
def task2string(task):
    torrenthash = task[0]
    owners = task[1]
    s = 'infohash='+`torrenthash`
    s += owners2string(task[1])
    return s

def owners2string(owners):
    s = ' owners= '
    for permid in owners:  
        s += show_permid_short(permid)+' '
    return s




class SimpleTorrentCollecting:
    """
        Simplest torrent collecting policy: randomly collect a torrent when received
        a buddycast message
    """
    
    def __init__(self, metadata_handler):
        self.torrent_db = TorrentDBHandler()
        self.metadata_handler = metadata_handler
        
    def updatePreferences(self, permid, preferences, selversion=-1):
        torrent = self.selecteTorrentToCollect(preferences)
        if torrent:
            self.metadata_handler.send_metadata_request(permid, torrent, selversion)
        if debug:
            print "tc: **************** select a torrent to collect", `torrent`, len(preferences)
    
    def closeConnection(self, permid):
        pass
    
    def selecteTorrentToCollect(self, preferences):
        preferences = list(preferences)
        candidates = []
        for torrent in preferences:
            if not self.torrent_db.hasMetaData(torrent):    # check if the torrent has been downloaded
                candidates.append(torrent)
        nprefs = len(candidates)
        if nprefs > 0:
            idx = randint(1, nprefs)
            selected = candidates[idx]
            return selected
        else:
            return None
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    