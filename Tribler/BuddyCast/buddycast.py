from time import time
from sha import sha

from Tribler.CacheDB.superpeer import SuperPeer
from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *
from dictlist import DictListQueue
from similarity import simMeasure

DEBUG = False

class BuddyCast:
    __single = None
    
    def __init__(self):
        if BuddyCast.__single:
            raise RuntimeError, "BuddyCast is singleton"
        BuddyCast.__single = self 
        self.rawserver = None
        self.superpeer = SuperPeer()
        self.superpeers_list = self.superpeer.getSuperPeers()
        self.max_bc_len = 10     # max buddy cache length
        self.max_rc_len = 100    # max random peer cache length
        self.max_pl_len = 1000   # max preference list length
        self.max_pcq_len = 2     # max prefxchg_candidate_queue length
        self.max_tb_len = 10     # max amount of taste buddies in prefxchg message
        self.max_rp_len = 10     # max amount of random peers in prefxchg message
        self.buddy_cache = DictListQueue(self.max_bc_len)     # Taste Buddy Cache
        self.random_cache = DictListQueue(self.max_rc_len)    # Random Peer Cache
        self.preference_cache = DictListQueue(self.max_pl_len)
        self.prefxchg_candidate_queue = DictListQueue(self.max_pcq_len)
        self.all_file_cache = FileCacheHandler()
        self.all_peer_cache = PeerCacheHandler()
        self.all_pref_cache = PrefCacheHandler()
        self.my_prefxchg_msg = {}
        self.buddy_preferences = {}
        self.my_ip = ''
        self.my_port = 0
                
    def getInstance(*args, **kw):
        if BuddyCast.__single is None:
            BuddyCast(*args, **kw)
        return BuddyCast.__single
    getInstance = staticmethod(getInstance)
        
    def set_rawserver(self, rawserver):
        self.rawserver = rawserver
        
    def set_errorfunc(self, errorfunc):
        self.errorfunc = errorfunc
        
    def set_myip(self, ip):
        self.my_ip = ip
        
    def set_listen_port(self, port):
        self.my_port = port
        
    def startup(self):
        self.import_my_preferences()
        self.import_taste_buddies()
        self.import_random_peers()
               
    def import_my_preferences(self):
        preferences = self.all_file_cache.getPreferences(show_friendly_time = False)
        self.preference_cache.importN(preferences, ['last_seen', 'torrent_hash'], 'last_seen')
        
    def import_taste_buddies(self):
        buddies = self.all_peer_cache.getPeers(last_file = False, show_friendly_time=False)
        self.buddy_cache.importN(buddies, ['permid', 'ip', 'port', 'last_seen', 'similarity'], 'similarity')
        for buddy in buddies:
            id = buddy['id']
            permid = buddy['permid']
            self.buddy_preferences[permid] = self.all_pref_cache.getPrefListByID(id)    # TODO: get pref by permid
                            
    def import_random_peers(self):
        peers = self.all_peer_cache.getPeers(last_file = False, show_friendly_time=False)
        self.random_cache.importN(peers, ['permid', 'ip', 'port', 'last_seen', 'similarity'], 'similarity')
                            
    def get_my_prefxchg_msg(self, permid, buddy_mode=1, random_mode=1, pref_mode=1):
        """ buddy_mode 1: return similar taste buddies as myself;
            buddy_mode 2: return similar taste buddies as the remote peer
            ==
            buddy_mode 1: return my recently seen random peers
            ==
            pref_mode 1: return my recently used torrents
        """
        
        self.my_prefxchg_msg['ip'] = self.my_ip
        self.my_prefxchg_msg['port'] = self.my_port
        self.my_prefxchg_msg['my_preferences'] = self.get_my_preferences(self.max_pl_len, pref_mode)
        self.my_prefxchg_msg['taste_buddies'] = self.get_taste_buddies(self.max_tb_len, buddy_mode)
        self.my_prefxchg_msg['random_peers'] = self.get_random_peers(self.max_rp_len, random_mode)
        return self.my_prefxchg_msg
                    
    def print_prefxchg_msg(self, prefxchg_msg):
        print "------- my perference_exchange message ---------"
        print "ip:", prefxchg_msg['ip']
        print "port:", prefxchg_msg['port']
        print "my_preferences:"
        for pref in prefxchg_msg['my_preferences']:
            print "\t", sha(pref).hexdigest()
        print "taste_buddies:"
        for buddy in prefxchg_msg['taste_buddies']:
            print "\t permid:", sha(buddy['permid']).hexdigest()
            print "\t ip:", buddy['ip']
            print "\t port:", buddy['port']
            print "\t age:", buddy['age']
            print "\t preferences:"
            for pref in buddy['preferences']:
                print "\t\t", pref
            print
        print "random_peers:"
        for peer in prefxchg_msg['random_peers']:
            print "\t permid:", sha(peer['permid']).hexdigest()
            print "\t ip:", peer['ip']
            print "\t port:", peer['port']
            print "\t age:", peer['age']
            print
                        
    def get_my_preferences(self, num, mode=1):
        preflist = self.preference_cache.getTopN(num)
        my_preferences = []
        for pref in preflist:
            my_preferences.append(pref['torrent_hash'])
        return my_preferences
            
    def get_taste_buddies(self, num, mode=1):
        taste_buddies = []
        for buddy in self.buddy_cache.getTopN(num):
            preferences = self.buddy_preferences[buddy['permid']]
            b = {'permid':buddy['permid'], 'ip':buddy['ip'], 
                 'port':buddy['port'], 'age':int(time()-buddy['last_seen']),
                 'preferences':preferences}
            taste_buddies.append(b)
        return taste_buddies
            
    def get_random_peers(self, num, mode=1):
        random_peers = []
        for peer in self.random_cache.getTopN(num):
            p = {'permid':peer['permid'], 'ip':peer['ip'], 
                 'port':peer['port'], 'age':int(time()-peer['last_seen'])}
            random_peers.append(p)
        return random_peers
            
    def add_new_buddy(self, conn):
        ip = conn.get_ip(True)
        port = conn.get_port(True)
        permid = conn.get_permid()
        peer = {'permid':permid, 'ip':ip, 'port':port, 'last_seen':int(time())}
        if permid and ip:
            self.all_peer_cache.addPeer(peer)
            if port:
                self.add_random_peer(peer)
                                    
    def add_random_peer(self, peer):
        self.random_cache.add(peer)
                    
    def exchange_preference(self, conn):
        if DEBUG:
            print "send preference_exchange to", conn.get_ip(True)
        permid = conn.permid
        pref_msg = self.get_my_prefxchg_msg(permid)
        pref_msg = bencode(pref_msg)
        conn.send_overlay_message(PREFERENCE_EXCHANGE + pref_msg)
                
    def request_preference(self, enc_conn, max_len):
        msg = wrap_message(REQUEST_PREFERENCE, max_len)
        if DEBUG:
            print "Pending to send REQUEST_PREFERENCE to", enc_conn.get_ip(), max_len
        self.send_message(enc_conn, msg)
        
    def send_preference(self, enc_conn, max_len):
        if not isinstance(max_len, int) or max_len < 0:
            return False
        preflist = self.file_cache.getPreferences()    # TODO: sort by rank
        self.do_send_preference(enc_conn, preflist[:max_len])
        return True
    
    def do_send_preference(self, enc_conn, preflist):
        msg = wrap_message(PREFERENCE, preflist)
        if DEBUG:
            print "Pending to send my preference to", enc_conn.get_ip(), preflist
        self.send_message(enc_conn, msg)
        
    def got_preference(self, conn, message):
        try:
            prefxchg_msg = bdecode(message[1:])
        except:
            errorfunc("warning: bad data in prefxchg_msg")
            return False
        if DEBUG:
            print "Got PREFERENCE from ", conn.get_ip()
            print "************* got preference *************"
            self.print_prefxchg_msg(prefxchg_msg)
        if not conn.permid:
            return False
        peer_prefs = prefxchg_msg['my_preferences']
        peer = {'ip':prefxchg_msg['ip'], 'port':prefxchg_msg['port']}
        for pref in peer_prefs:
            self.all_pref_cache.addPreference(peer, pref, 1)
        
        return True
        
    def got_message(self, conn, message):
        t = message[0]
        if t == PREFERENCE_EXCHANGE:
            self.got_preference(conn, message)
        else:
            print "UNKONW OVERLAY MESSAGE", ord(t)
        
        