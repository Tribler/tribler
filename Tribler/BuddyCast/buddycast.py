# Written by Jun Wang, Jie Yang
# see LICENSE.txt for license information

from time import time, sleep
from random import randint, seed

from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *

from Tribler.__init__ import GLOBAL
from Tribler.CacheDB.CacheDBHandler import *
from Tribler.CacheDB.superpeer import SuperPeer
from Tribler.Overlay.permid import show_permid
from dictlist import DictList
from similarity import P2PSim

DEBUG = False
relax_seconds = 30    # 3600*3

num_torrents = 30
num_peers = 20
permid_length = 10
torrent_hash_length = 12


def get_last_seen(age=0):
    return int(time()) - age

class BuddyCast:
    __single = None
    
    def __init__(self):
        if BuddyCast.__single:
            raise RuntimeError, "BuddyCast is singleton"
        BuddyCast.__single = self 
        self.rawserver = None
        # --- database handlers ---
        self.mydb = MyDBHandler()
        self.peers = PeerDBHandler()
        self.torrents = TorrentDBHandler()
        self.myprefs = MyPreferenceDBHandler()
        self.prefs = PreferenceDBHandler()
        self.owners = OwnerDBHandler()
        # --- constants. they should be stored in mydb ---
        self.max_bc_len = 30     # max buddy cache length
        self.max_rc_len = 100    # max random peer cache length
        self.max_pc_len = 100    # max my preference cache length
        
        self.max_pl_len = 10     # max amount of preferences in prefxchg message
        self.max_tb_len = 10     # max amount of taste buddies in prefxchg message
        self.max_rp_len = 10     # max amount of random peers in prefxchg message
        self.max_pcq_len = 3     # max prefxchg_candidate_queue length
        
        self.buddycast_interval = GLOBAL.do_buddycast_interval
        # --- buffers ---
        self.superpeers = []
        self.buddy_cache = DictList(self.max_bc_len)     # Taste Buddy Cache
        self.random_cache = DictList(self.max_rc_len)    # Random Peer Cache
        self.mypref_cache = DictList(self.max_pc_len)
        self.prefxchg_candidate_queue = []
        self.recommended_files = []
        self.contacted_list = {}
        # --- variables ---
        self.my_ip = ''
        self.my_port = 0
        self.my_name = ''
        self.my_prefxchg_msg = {}
        self.registered = False
                
    def getInstance(*args, **kw):
        if BuddyCast.__single is None:
            BuddyCast(*args, **kw)
        return BuddyCast.__single
    getInstance = staticmethod(getInstance)
        
    def register(self, secure_overlay, rawserver, port, errorfunc):    
        if self.registered:
            return
        self.secure_overlay = secure_overlay
        self.rawserver = rawserver
        self.errorfunc = errorfunc
        self.my_name = self.mydb.get('name')
        self.my_ip = self.mydb.get('ip')
        self.my_port = port
        self.mydb.put('port', port)
        self.mydb.sync()
        self.registered = True
        self.startup()
        
    def is_registered(self):
        return self.registered

    def set_myip(self, ip):
        self.my_ip = ip
        self.mydb.put('ip', ip)
        self.mydb.sync()
                
#------------ init ----------------
    def startup(self):
#        if not self.registered:
#            return
        self.loadSuperpeers()
        self.loadPrefxchgData()
        self.num_peers = num_peers
        self.num_torrents = num_torrents
        self.oldnp = self.peers.size()
        self.oldnf = self.myprefs.size()
        self.oldnt = self.torrents.size()
        self.last_recomm = []
        self.run()

    def loadSuperpeers(self):
        self.superpeers = SuperPeer().getSuperPeers()
                
    def loadPrefxchgData(self):
        self.loadMyPreferences()
        self.loadCache()

    def loadMyPreferences(self):
        mypref = self.myprefs.getPreferences()
        if DEBUG:
            print "buddycast: *********** importDictList mypref"
        self.mypref_cache.importDictList(mypref, ['last_seen', 'torrent_hash'], 'last_seen', 'decrease')
        
    def loadCache(self):

        def sort(data, key, order='increase'):
            aux = [(data[i][key], i) for i in range(len(data))]
            aux.sort()
            if order == 'decrease':
                aux.reverse()
            result = [data[i] for junk, i in aux]
            data = result
            
        def separateDictList(dict_list, num, key=None, order='increase'):
            if key:
                sort(dict_list, key, order)
            return dict_list[:num], dict_list[num:]
    
        alpha = 3
        buddies = self.peers.getPeers('has_preference', 1)
        rand_peers = self.peers.getPeers('has_preference', 0)
        # select taste buddies first by last seen, then by similarity
        taste_buddies, rand_peers1 = separateDictList(buddies, self.max_bc_len*alpha, 'last_seen', 'decrease')
        taste_buddies, rand_peers2 = separateDictList(taste_buddies, self.max_bc_len, 'similarity', 'decrease')
        # the left peers join rand peers. right?
        rand_peers.extend(rand_peers1)
        rand_peers.extend(rand_peers2)
        # fill cache
        if DEBUG:
            print "buddycast: ********** importDictList buddy"
        self.buddy_cache.importDictList(taste_buddies, ['permid', 'ip', 'port', 'last_seen', 'similarity'], 'similarity', 'decreaes')
        if DEBUG:
            print "buddycast: *********** importDictList rand"
        self.random_cache.importDictList(rand_peers, ['permid', 'ip', 'port', 'last_seen'], 'last_seen', 'decrease')
        
#------------ run ----------------
    def run(self):
        self.loadPrefxchgCandidates()
        if GLOBAL.do_das_test:
            self.do_das_test()
        else:
            self.rawserver.add_task(self._run, self.buddycast_interval)

    def _run(self):
        if not self.stopBuddycast():
            self.rawserver.add_task(self._run, self.buddycast_interval)
        self.runBuddycast()

    def runBuddycast(self):
        if DEBUG:
            print "buddycast: Start cycle"
        c = self.getPrefxchgCandidate()
        if not c:
            return
        ip, port, permid = c['ip'], c['port'], c['permid']
        if DEBUG:
            print "buddycast: do buddycast with", ip, port, "......",
        port = int(port)
        if port == 0 or ip == self.my_ip or ip == '127.0.0.1' or self.isRelaxing(permid):
            if DEBUG:
                print "buddycast: pass"
        else:
            self.sendPrefxchg(permid)
            if DEBUG:
                print "buddycast: done"
        
    def loadPrefxchgCandidates(self):
        """ load unfinished queue. If bootstrapping, fill it in with superpeers """
    
        self.prefxchg_candidate_queue = self.mydb.getPrefxchgQueue()
        ncand = len(self.prefxchg_candidate_queue)
        if ncand < self.max_pcq_len:
            ncand2add = self.max_pcq_len - ncand
            # do it only once. candidate queue may not be fully filled.
            cand = self.selectPrefxchgCandidates(ncand2add)    
            self.prefxchg_candidate_queue.extend(cand)
        self.dumpPrefxchgCandidate()
            
    def dumpPrefxchgCandidate(self):    # save unused candidates into db for the next run
        self.mydb.setPrefxchgQueue(self.prefxchg_candidate_queue)
        self.mydb.sync()
        
    def stopBuddycast(self):    #TODO: rate limit
        return False

#------------- buddycast core -----------------
    def getPrefxchgCandidate(self):
        if len(self.prefxchg_candidate_queue) > 0:
            c = self.prefxchg_candidate_queue.pop(0)
            pcs = self.selectPrefxchgCandidates(1)    # fill candidate queue
            self.prefxchg_candidate_queue.extend(pcs)
            self.dumpPrefxchgCandidate()
        else:
            c = None
        return c

    def selectPrefxchgCandidates(self, num=1):
        """ preference exchange candidate selection based buddycast algorithm """
        # first validate the two caches
        # if buddy_cache is empty, then select from random cache
        
        candidates = []
        buddy_size = self.buddy_cache.length()
        random_size = self.random_cache.length()
        total_size = buddy_size + random_size
        if buddy_size == 0:    # no buddy, fill by random peer
            candidates = self.random_cache.getRandomItems(num)
        elif num >= total_size:
            candidates.extend(self.buddy_cache.getAll())
            candidates.extend(self.random_cache.getAll())
        else:
            # generate cache curve
            #self.buddy_cache.sortedby('similarity', 'decrease')    #FIXME:
            buddy_sims = self.buddy_cache.getAllValues('similarity')
            min = buddy_sims[buddy_size-1]
            if min == 0:
                self.smooth(buddy_sims)
                min = buddy_sims[buddy_size-1]
            random_sims = [min for i in range(random_size)]
            if DEBUG:
                print "buddycast: @@@ buddy sims", len(buddy_sims), buddy_sims
            buddies = self.buddy_cache.getAllValues('permid')
            if DEBUG:
                print "buddycast: @@@ buddies", buddies
                print 
            buddy_sims.extend(random_sims)
            for i in xrange(1, total_size):
                buddy_sims[i] += buddy_sims[i-1]
            # select candidates based on the curve
            total_sim = buddy_sims[total_size-1]
            sims = [[buddy_sims[i], i] for i in xrange(len(buddy_sims))]
            while sims and len(candidates) < num:
                random_var = randint(0, total_sim)
                idx = self.bisearch(sims, random_var)
                if DEBUG:
                    print "buddycast: @@@ select out", idx, "from", total_size, "and", total_size
                    print "buddycast: ---------------"
                if sims[idx][1] < buddy_size:
                    candidates.append(self.buddy_cache.getItem(idx))
                else:
                    candidates.append(self.random_cache.getItem(idx-buddy_size))
                sims.pop(idx)
        pcs = self.importAllPeers(candidates)
        return pcs

    def importAllPeers(self, peers):
        res = []
        for p in peers:
            res.append(self.pc_filter(p))
        return res
        
    def pc_filter(self, peer):    # prefxchg candidate dict filter
        return {'ip':peer['ip'], 'port':peer['port'], 'permid':peer['permid']}

    def smooth(self, alist):    #a simple smooth method. TODO: better one
        for i in xrange(len(alist)):
            alist[i] += 1
 
    def bisearch(self, data, value):
        low = 0
        high = len(data)
        while low < high:
            mid = (low + high) / 2
            if value == data[mid][0]:
                return mid
            elif value > data[mid][0]:
                low = mid + 1
            else:
                high = mid
        return low

#------------- recommend core -----------------
    def recommendFiles(self, num=10):
        np = self.mypref_cache.length()
        if np == 0:    # if I do not have enough pref, recommend popular files
            self.recommended_files = self.recommend1(num)
        else:
            self.recommended_files = self.recommend2(num)
        
    def recommend1(self, num):    
        """ file popularity based recommendation """
        
        allfiles = []
        my_prefs = self.getMyPrefs()
        for key, value in self.owners.getAllOwners():
            if key not in my_prefs:
                allfiles.append((len(value), key))
        allfiles.sort()
        allfiles.reverse()
        res = []
        for pop, key in allfiles[:num]:
            file = self.torrents.getTorrent(key)
            res.append((pop, file['torrent_hash']))
        return res
    
    def recommend2(self, num):    
        """ user based recommendation """
        
        allfiles = []
        my_prefs = self.getMyPrefs()
        for key, value in self.owners.getAllOwners():
            if key in my_prefs:
                continue
            sim = 0
            for peer in value:
                p = self.peers.getPeer(peer)
                sim += p['similarity']
            allfiles.append((sim, key))
        allfiles.sort()
        allfiles.reverse()
        res = []
        for sim, key in allfiles[:num]:
            file = self.torrents.getTorrent(key)
            res.append((sim, file['torrent_hash']))
        
        return res
    
#------------ send my preference_exchange -----------
    def sendPrefxchg(self, permid):
        pref_msg = self.getMyPrefxchgMsg(permid)
        if DEBUG:
            self.print_prefxchg_msg(pref_msg, permid)
        pref_msg = bencode(pref_msg)
        self.contacted_list[permid] = int(time())
        self.secure_overlay.addTask(permid, PREFERENCE_EXCHANGE + pref_msg)
    
    def getMyPrefxchgMsg(self, permid=None, buddy_mode=1, random_mode=1, pref_mode=1):
        """ buddy_mode 1: return similar taste buddies as myself;
            buddy_mode 2: return similar taste buddies as the remote peer
            ==
            random_mode 1: return my recently seen random peers
            ==
            pref_mode 1: return my recently used torrents
        """
        self.my_prefxchg_msg['ip'] = self.my_ip
        self.my_prefxchg_msg['port'] = self.my_port
        self.my_prefxchg_msg['name'] = self.my_name
        self.loadPrefxchgData()
        self.my_prefxchg_msg['taste buddies'] = self.getTasteBuddies(self.max_tb_len, permid, buddy_mode)
        self.my_prefxchg_msg['random peers'] = self.getRandomPeers(self.max_rp_len, permid, random_mode)
        self.my_prefxchg_msg['preferences'] = self.getMyPreferences(self.max_pl_len, permid, pref_mode)
        return self.my_prefxchg_msg
                    
    def getMyPreferences(self, num, permid=None, mode=1):
        preflist = self.mypref_cache.getTopN(num)
        my_preferences = {}
        if mode == 1:
            for pref in preflist:
                my_preferences[pref['torrent_hash']] = {}
        return my_preferences
            
    def getTasteBuddies(self, num, permid=None, mode=1):
        taste_buddies = []
        if mode == 1:
            buddies = self.buddy_cache.getTopN(num)
            for buddy in buddies:
                preferences = self.prefs.getPreferences(buddy['permid'])
#                if preferences:
#                    preferences = preferences[:self.max_tb_len]
                b = {'permid':buddy['permid'], 'ip':buddy['ip'], 
                     'port':buddy['port'], 'age':int(time()-buddy['last_seen']),
                     'preferences':preferences}
                taste_buddies.append(b)
        return taste_buddies
            
    def getRandomPeers(self, num, permid=None, mode=1):
        random_peers = []
        if mode == 1:
            for peer in self.random_cache.getTopN(num):
                p = {'permid':peer['permid'], 'ip':peer['ip'], 
                     'port':peer['port'], 'age':int(time()-peer['last_seen'])}
                random_peers.append(p)
        return random_peers
        
    def isRelaxing(self, permid):    
        if self.contacted_list.has_key(permid):
            slept = (time() - self.contacted_list[permid])
            if slept < relax_seconds:
                return True
        return False

#--------------- received preference_exchage ---------------
    def gotPrefxchg(self, permid, prefxchg):
        peer = {'permid':permid, 'has_preference':1, 'last_seen':get_last_seen()}
        prefxchg.update(peer)
        try:
            if len(prefxchg['taste buddies']) > 0:
                self.updateTasteBuddies(prefxchg['taste buddies'])
            if len(prefxchg['random peers']) > 0:
                self.updateRandomPeers(prefxchg['random peers'])
        except:
            pass
        self.updateTasteBuddy(prefxchg)
        self.sync_data()
        
    def updateTasteBuddies(self, taste_buddies):
        for buddy in taste_buddies:
            age = 0
            if buddy.has_key('age'):
                age = buddy['age']
            buddy.update({'has_preference':1, 'last_seen':get_last_seen(age)})
            self.updateTasteBuddy(buddy)
        
    def updateTasteBuddy(self, buddy):
        self.prefs.addPreferences(buddy['permid'], buddy['preferences'])
        sim = self.getP2PSimilarity(buddy['permid'])
        self.peers.filter(buddy)
        buddy.update({'similarity':sim})
        self.peers.updatePeer(buddy)
        idx = self.buddy_cache.findItem('permid', buddy['permid'])
        if idx >= 0:
            if DEBUG:
                print "buddycast: >>> update buddy", show_permid(buddy['permid']), buddy['similarity'], "at", idx
            self.buddy_cache.updateItem(idx, buddy)
        else:
            idx, pop_item = self.buddy_cache.addItem(buddy)
            if DEBUG:
                print "buddycast: @@@ add    buddy",show_permid(buddy['permid']), buddy['similarity'], "at", idx
            if pop_item:    # move poped buddy into random cache
                self.random_cache.addItem(pop_item)
        
    def getP2PSimilarity(self, permid):
        peer_prefs = self.prefs.getPreferences(permid).keys()
        my_prefs = self.getMyPrefs()
        sim = P2PSim(peer_prefs, my_prefs)
        return sim    
        
    def updateRandomPeers(self, random_peers):
        for peer in random_peers:
            self.updateRandomPeer(peer)

    def updateRandomPeer(self, peer):
        age = 0
        if peer.has_key('age'):
            age = peer['age']
        peer.update({'last_seen':get_last_seen(age)})
        self.peers.filter(peer)
        self.peers.updatePeer(peer)
        self.random_cache.addItem(peer)
        
    def sync_data(self):
        self.mydb.sync()
        self.peers.sync()
        self.torrents.sync()
        self.myprefs.sync()
        self.prefs.sync()
        self.owners.sync()
        
#------------ messages handler ----------------
    def exchangePreference(self, permid):
        if not self.isRelaxing(permid):
            self.sendPrefxchg(permid)
                
    def gotPrefxchgMsg(self, permid, message):
        try:
            prefxchg_msg = bdecode(message[1:])
        except:
            errorfunc("warning: bad data in prefxchg_msg")
            return False
        if DEBUG:
            print "************* got preference *************"
            self.print_prefxchg_msg(prefxchg_msg, permid)
        self.gotPrefxchg(permid, prefxchg_msg)
        return True
        
    def handleMessage(self,permid,message):
        t = message[0]
        if DEBUG:
            print "buddycast: Got",getMessageName(t)

        if t == PREFERENCE_EXCHANGE:
            self.gotPrefxchgMsg(permid, message)
            self.exchangePreference(permid)


#--- test functions. should be removed when releasing ---#

    def do_das_test(self):
        myname = self.mydb.get('name')
        seed(myname)    # to keep it stable
        node = randint(0, 500)
        seed()
        if myname.startswith("node"):
            try:
                node = int(myname[4:])
            except:
                pass
        self.load_test_pref(node)
        self.rawserver.add_task(self.test_buddy_cast, self.buddycast_interval)
        
    def load_test_pref(self, node):
        filename = 'userpref500.txt'
        opened = True
        try:
            file = open(filename, "r")
        except:
            try:
                filename = "../" + filename
                file = open(filename, "r")
            except:
                opened = False
        preflist = {}
        if not opened:
            preflist = rand_preflist(100)
        else:
            playlist = file.readlines()
            items = playlist[node].strip()
            for item in items.split(' '):
                preflist[item] = {}
        for pref in preflist:
            self.myprefs.addPreference(pref)
        
    def test_buddy_cast(self):
        if not self.stopBuddycast():
            self.rawserver.add_task(self.test_buddy_cast, self.buddycast_interval)
        self.runBuddycast()    #TODO: test on das2
        
    def do_buddy_cast(self):
        c = self.getPrefxchgCandidate()
        if not c:
            return
        ip, port = c['ip'], c['port']
        print "do buddycast with", ip, port
        self.oldnp, self.oldnf, self.oldnt, self.last_recomm = \
            run_buddycast(self, 10, 1, 1, self.oldnp, self.oldnf, self.oldnt, self.last_recomm)
        #print "res --->", self.oldnp, self.oldnf, self.oldnt, self.last_recomm
        if not self.stopBuddycast():
            self.rawserver.add_task(self.do_buddy_cast, self.buddycast_interval)
        #self.connectPeer(ip, port)
    
#---------------- utilities -------------------
    def getMyPrefs(self):
        return self.myprefs.getPreferences('torrent_hash')

    def addMyPreference(self, torrent_hash):
        self.myprefs.addPreference(torrent_hash)
        pref = {'last_seen':int(time()), 'torrent_hash':torrent_hash}
        self.mypref_cache.addItem(pref)
        self.updateAllSim()

    def updateAllSim(self):
        my_prefs = self.getMyPrefs()
        updated_peers = {}
        for torrent_hash in my_prefs:
            peers = self.owners.getOwners(torrent_hash)
            if not peers:
                continue
            for p in peers:
                if p in updated_peers:    # skip 
                    continue
                peer_prefs = self.prefs.getPreferences(p).keys()
                sim = P2PSim(peer_prefs, my_prefs)
                self.peers.updatePeerSim(p, sim)    #FIXME: update buddy cache
                updated_peers[p] = None

    def print_prefxchg_msg(self, prefxchg_msg, permid=None):
        print "------- preference_exchange message ---------"
        print prefxchg_msg
        print "---------------------------------------------"
        print "name", prefxchg_msg['name']
        if permid:
            #print "permid:", permid
            print "permid:", show_permid(permid)
        print "ip:", prefxchg_msg['ip']
        print "port:", prefxchg_msg['port']
        print "preferences:"
        if prefxchg_msg['preferences']:
            for pref in prefxchg_msg['preferences']:
                print "\t", pref, prefxchg_msg['preferences'][pref]
        print "taste buddies:"
        if prefxchg_msg['taste buddies']:
            for buddy in prefxchg_msg['taste buddies']:
                print "\t permid:", show_permid(buddy['permid'])
                #print "\t permid:", buddy['permid']
                print "\t ip:", buddy['ip']
                print "\t port:", buddy['port']
                print "\t age:", buddy['age']
                print "\t preferences:"
                if buddy['preferences']:
                    for pref in buddy['preferences']:
                        print "\t\t", pref, buddy['preferences'][pref]
                print
        print "random peers:"
        if prefxchg_msg['random peers']:
            for peer in prefxchg_msg['random peers']:
                print "\t permid:", show_permid(peer['permid'])
                #print "\t permid:", peer['permid']
                print "\t ip:", peer['ip']
                print "\t port:", peer['port']
                print "\t age:", peer['age']
                print
        
    def show(self):
        print " +++++++++++++++ show +++++++++++++++++ "
        self.showDBs()
        self.showBuffers()
        
    def show2(self):
#        self.myprefs.printList()
#        self.prefs.printList()
#        self.myprefs.printList()
#        self.peers.printList()
        self.owners.printList()
#        print '=============== prefxchg_candidate_queue ===============', len(self.prefxchg_candidate_queue)
#        for cand in self.prefxchg_candidate_queue:
#            print cand
#        print '=============== mypref_cache ===============', len(self.mypref_cache)
#        self.mypref_cache.printList()
        
            
    def showDBs(self):
        self.peers.printList()
        self.torrents.printList()
        self.myprefs.printList()
        self.prefs.printList()
        self.owners.printList()        
        self.mydb.printList()
        
    def showBuffers(self):
        print '=============== super peers ===============', self.superpeers.length()
        for sp in self.superpeers:
            print sp
        print '=============== buddy_cache ===============', self.buddy_cache.length()
        self.buddy_cache.printList()
        print '=============== random_cache ===============', self.random_cache.length()
        self.random_cache.printList()
        print '=============== mypref_cache ===============', self.mypref_cache.length()
        self.mypref_cache.printList()
        print '=============== prefxchg_candidate_queue ===============', self.prefxchg_candidate_queue.length()
        for cand in self.prefxchg_candidate_queue:
            print cand

#-------------- for test ----------------

def rand_pref(num=num_torrents, prefix='torrent'):
    torrent = str(randint(1, num))
    left = torrent_hash_length - len(torrent) - len(prefix)
    torrent = prefix + '_'*left + torrent
    return torrent

def rand_preflist(num=10, nt=num_torrents):
    res = {}
    while len(res) < num:
        prefix = 'torrent' #socket.gethostname()
        x = rand_pref(num=nt, prefix=prefix)
        res[x] = {}
    return res

def rand_ip():
    x1 = int(random()*255) + 1
    x2 = int(random()*255) + 1
    x3 = int(random()*255) + 1
    x4 = int(random()*255) + 1
    return str(x1)+'.'+str(x2)+'.'+str(x3)+'.'+str(x4)

def rand_port():
    return int(random()*65534) + 1
    
def rand_age(max):
    return int(random()*max)

def rand_permid1(len=permid_length):
    res = ''
    for i in xrange(len):
        res += chr(int(random()*256))
    return res
    
def rand_premid2(prefix='peer', num=num_peers):
    permid = str(int(random()*num))
    left = permid_length - len(permid) - len(prefix)
    permid = prefix + '_'*left + permid
    return permid
    
def rand_permid(np=num_peers):
    return rand_premid2(num=np)
    
def rand_buddy(prefnum=10, nt=num_torrents, np=num_peers):
    res = {}
    #res['name'] = rand_name(6)
    res['preferences'] = rand_preflist(prefnum, nt)
    res['permid'] = rand_permid(np)
    res['ip'] = rand_ip()
    res['port'] = rand_port()
    res['age'] = rand_age(3000)
    return res

def rand_peer(perfnum=10, np=num_peers):
    res = {}
    res['permid'] = rand_permid(np)
    res['ip'] = rand_ip()
    res['port'] = rand_port()
    res['age'] = rand_age(3000)
    return res
    
def rand_taste_buddies(num=10, nt=num_torrents, np=num_peers):
    res = []
    for i in xrange(num):
        res.append(rand_buddy(10, nt, np))
    return res
    
def rand_random_peers(num=10, np=num_peers):
    res = []
    for i in xrange(num):
        res.append(rand_peer(10, np))
    return res
    
def rand_name(num=6):
    name = ''
    for i in xrange(num):
        name += chr(ord('a') + int(random()*26))
    return name
    
def get_prefxchg(nt=num_torrents, np=num_peers):
    prefxchg = {'name':rand_name(6),
                'preferences':rand_preflist(10), 
                'ip':rand_ip(),
                'port':rand_port(),
                'taste buddies':rand_taste_buddies(10, nt, np),
                'random peers':rand_random_peers(10, np)
               }
    return prefxchg

def init_myprefs(bc, num=30):
    myprefs = MyPreferenceDBHandler()
    for i in xrange(num):
        torrent_hash = rand_pref()
        #print "randomly add a preference", torrent_hash
        myprefs.addPreference(torrent_hash)
        bc.addMyPreference(torrent_hash)
        
def getRankChange(file, currank, lastranks, num):
    size = len(lastranks)
    if size == 0:
        return '+'+str(num - currank)
    change = None
    for i in range(size):
        sim, f = lastranks[i]
        if f == file:
            oldrank = i
            change = oldrank - currank
            break
    if change == None:
        change = num - currank
    if change > 0:
        return '+' + str(change)
    else:
        return str(change)

def rand_down(files):
    size = len(files)
    ranks = []
    total = 0.0
    for rank, file in files:
        total += rank
        ranks.append(total)
    r = random()*total
    for i in xrange(len(ranks)):
        if r < ranks[i]:
            break
    return i

def do_buddycast(bc):
    c = bc.getPrefxchgCandidate()
    if not c:
        return
    ip, port, permid = c['ip'], c['port'], c['permid']
    print "do buddycast with", ip, port, "\n"

def run_buddycast(bc, num=20, nd=1, times=1, oldnp=0, oldnf=0, oldnt=0, last_recomm=[]):
    
    for i in xrange(times):
        prefxchg = get_prefxchg(10000, bc.num_peers)
        bc.gotPrefxchg(rand_permid(), prefxchg)
        bc.recommendFiles(num)
        
        nf = bc.myprefs.size()
        added2 = nf - oldnf
#        print "=== num of my preferences:", nf, "\tadded new preferences:", added2
        oldnf = nf
        
        np = bc.peers.size()
        if np > bc.num_peers * 0.9:
            bc.num_peers = int(bc.num_peers*1.1)
        added = np - oldnp
#        print "=== num of peers:", np, "\t\tdiscovered new peers:", added
        oldnp = np
        
        nt = bc.torrents.size()
        if nt > bc.num_torrents * 0.9:
            bc.num_torrents = int(bc.num_torrents*1.1)
        added3 = nt - oldnt
#        print "=== num of files:", nt, "\t\tdiscovered new files:", added3
        oldnt = nt
        
#        print "--- recommendated files ---"
#        nr = len(bc.recommended_files)
#        for i in xrange(nr):
#            recom, file = bc.recommended_files[i]
#            print file, '%d'%recom, getRankChange(file, i, last_recomm, nr)
        
#        print "--- download files ---"
        for i in range(nd):
            select = rand_down(bc.recommended_files)
            rank, file = bc.recommended_files.pop(select)
            bc.addMyPreference(file)
#            print "add a preference by recom", file
        
        init_myprefs(bc, 1)
        last_recomm = deepcopy(bc.recommended_files)
#        print
        do_buddycast(bc)
        
    return oldnp, oldnf, oldnt, last_recomm
    
def test_buddycast(times=1):
    bc = BuddyCast.getInstance()
    bc.startup()
    bc.loadPrefxchgCandidates()
    run_buddycast(bc, 10, 1, times)
    
  
if __name__ == "__main__":
    test_buddycast(1)
