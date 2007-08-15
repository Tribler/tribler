# Written by Jie Yang
# see LICENSE.txt for license information
"""
    BuddyCast2 epdemic protocol for p2p recommendation and semantic clustering
    
Algorithm in LaTeX format:

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%  algorithm of the active peer   %%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

\begin{figure*}[ht]
\begin{center}
\begin{algorithmic}[1]

\LOOP
\STATE wait($\Delta T$ time units) \COMMENT{15 seconds in current implementation}
\STATE remove any peer from $B_S$ and $B_R$ if its block time was expired.
\STATE keep connection with all peers in $C_T$, $C_R$ and $C_U$
\IF{$idle\_loops > 0$}
    \STATE $idle\_loops \leftarrow idle\_loops - 1$ \COMMENT{skip this loop for rate control}
\ELSE
    \IF{$C_C$ is empty}
        \STATE $C_C \leftarrow$ select 5 peers recently seen from Mega Cache
    \ENDIF
    \STATE $Q \leftarrow$ select a most similar taste buddy or a random online peer from $C_C$
    \STATE connectPeer($Q$)
    \STATE block($Q$, $B_S$, 4hours)
    \STATE remove $Q$ from $C_C$
    \IF{$Q$ is connected successfully}
        \STATE buddycast\_msg\_send $\leftarrow$ \textbf{createBuddycastMsg}()
        \STATE send buddycast\_msg\_send to $Q$
        \STATE receive buddycast\_msg\_recv from $Q$
        \STATE $C_C \leftarrow$ fillPeers(buddycast\_msg\_recv)
        \STATE \textbf{addConnectedPeer}($Q$) \COMMENT{add $Q$ into $C_T$, $C_R$ or $C_U$ according to its similarity}
        \STATE blockPeer($Q$, $B_R$, 4hours)
    \ENDIF

\ENDIF
\ENDLOOP

\end{algorithmic}
\caption{The protocol of an active peer.}
\label{Fig:buddycast_algorithm}
\end{center}
\end{figure*}


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%  algorithm of the passive peer  %%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

\begin{figure*}[ht]
\begin{center}
\begin{algorithmic}[1]

\LOOP
    \STATE receive buddycast\_msg\_recv from $Q$
    \STATE $C_C \leftarrow$ fillPeers(buddycast\_msg\_recv)
    \STATE \textbf{addConnectedPeer}($Q$)
    \STATE blockPeer($Q$, $B_R$, 4hours)
    \STATE buddycast\_msg\_send $\leftarrow$ \textbf{createBuddycastMsg}()
    \STATE send buddycast\_msg\_send to $Q$
    \STATE blockPeer($Q$, $B_S$, 4hours)
    \STATE remove $Q$ from $C_C$
    \STATE $idle\_loops \leftarrow idle\_loops + 1$ \COMMENT{idle for a loop for
    rate control}
\ENDLOOP

\end{algorithmic}
\caption{The protocol of an passive peer.}
\label{Fig:buddycast_algorithm}
\end{center}
\end{figure*}


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%  algorithm of creating a buddycast message  %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

\begin{figure*}[ht]
\begin{center}
function \textbf{createBuddycastMsg}()
\begin{algorithmic}
    \STATE $My\_Preferences \leftarrow$ the most recently 50 preferences of the active peer
    \STATE $Taste\_Buddies \leftarrow$ all peers from $C_T$
    \STATE $Random\_Peers \leftarrow$ all peers from $C_R$
    \STATE $buddycast\_msg\_send \leftarrow$ create an empty message
    \STATE $buddycast\_msg\_send$ attaches the active peer's address and $My\_Preferences$
    \STATE $buddycast\_msg\_send$ attaches addresses of $Taste\_Buddies$
    \STATE $buddycast\_msg\_send$ attaches at most 10 preferences of each peer in $Taste\_Buddies$
    \STATE $buddycast\_msg\_send$ attaches addresses of $Random\_Peers$
\end{algorithmic}
\caption{The function of creating a buddycast message}
\label{Fig:buddycast_createBuddycastMsg}
\end{center}
\end{figure*}


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%  algorithm of adding a peer into C_T or C_R or C_U  %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

\begin{figure*}[ht]
\begin{center}
function \textbf{addConnectedPeer}($Q$)
\begin{algorithmic}
    \IF{$Q$ is connectable}
        \STATE $Sim_Q \leftarrow$ getSimilarity($Q$) \COMMENT{similarity between $Q$ and the active peer}
        \STATE $Min_{Sim} \leftarrow$ similarity of the least similar peer in $C_T$
        \IF{$Sim_Q \geq Min_{Sim}$ \textbf{or} ($C_T$ is not full \textbf{and} $Sim_Q>0$)}
            \STATE $C_T \leftarrow C_T + Q$
            \STATE move the least similar peer to $C_R$ if $C_T$ overloads
        \ELSE
            \STATE $C_R \leftarrow C_R + Q$
            \STATE remove the oldest peer to $C_R$ if $C_R$ overloads
        \ENDIF
    \ELSE
        \STATE $C_U \leftarrow C_U + Q$
    \ENDIF

\end{algorithmic}
\caption{The function of adding a peer into $C_T$ or $C_R$}
\label{Fig:buddycast_addConnectedPeer}
\end{center}
\end{figure*}

"""
"""

BuddyCast 3:
    No preferences for taste buddies; 
    don't accept preferences of taste buddies from incoming message either
    50 recent my prefs + 50 recent collected torrents + 50 ratings
    
Torrent info 
    preferences: Recently downloaded torrents by the user {'seeders','leechers','check time'}
    collected torrents: Recently collected torrents (include Subscribed torrents) 
    #ratings: Recently rated torrents and their ratings (negative rating means this torrent was deleted) 
Taste Buddies 
    permid 
    ip 
    port 
    similarity 
Random Peers 
    permid 
    ip 
    port 
    similarity 

"""

import sys
from random import sample, randint
from time import time, gmtime, strftime
from traceback import print_exc, print_stack
from sets import Set
from array import array
from bisect import insort
from copy import deepcopy
import gc
import socket

from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import BUDDYCAST, KEEP_ALIVE
from Tribler.CacheDB.CacheDBHandler import *
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler
from Tribler.CacheDB.SynDBHandler import SynPeerDBHandler
from Tribler.utilities import *
from Tribler.unicode import dunno2unicode
from Tribler.Dialogs.activities import ACT_MEET, ACT_RECOMMEND
from Tribler.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
from Tribler.Overlay.SecureOverlay import *
from similarity import P2PSim, P2PSimSorted, P2PSimLM
from TorrentCollecting import SimpleTorrentCollecting   #, TiT4TaTTorrentCollecting
from Tribler.Statistics.Logger import OverlayLogger
from threading import Event, currentThread

from bartercast import BarterCastCore

DEBUG = True    # for errors
debug = False    # for status
MAX_BUDDYCAST_LENGTH = 10*1024    # 10 KByte

def now():
    return int(time())

def ctime(t):
    return strftime("%Y-%m-%d.%H:%M:%S", gmtime(t))

def validBuddyCastData(prefxchg, nmyprefs=50, nbuddies=10, npeers=10, nbuddyprefs=10):
    
    # Arno: TODO: make check version dependent
    
    def validPeer(peer):
        validPermid(peer['permid'])
        validIP(peer['ip'])
        validPort(peer['port'])
    
    def validPref(pref, num):
        if not (isinstance(prefxchg, list) or isinstance(prefxchg, dict)):
            raise RuntimeError, "bc: invalid pref type " + str(type(prefxchg))
        if num > 0 and len(pref) > num:
            raise RuntimeError, "bc: length of pref exceeds " + str((len(pref), num))
        for p in pref:
            validInfohash(p)
            
    validPeer(prefxchg)
    if not isinstance(prefxchg['name'], str):
        raise RuntimeError, "bc: invalid name type " + str(type(prefxchg['name']))
    validPref(prefxchg['preferences'], nmyprefs)
    
    if len(prefxchg['taste buddies']) > nbuddies:
        raise RuntimeError, "bc: length of prefxchg['taste buddies'] exceeds " + \
                str(len(prefxchg['taste buddies']))
    for b in prefxchg['taste buddies']:
        validPeer(b)
        #validPref(b['preferences'], nbuddyprefs)    # not used from version 4
        
    if len(prefxchg['random peers']) > npeers:
        raise RuntimeError, "bc: length of random peers " + \
                str(len(prefxchg['random peers']))
    for b in prefxchg['random peers']:
        validPeer(b)
    return True


class BuddyCastFactory:
    __single = None
    
    def __init__(self, db_dir='', superpeer=False, log=''):
        if BuddyCastFactory.__single:
            raise RuntimeError, "BuddyCastFactory is singleton"
        BuddyCastFactory.__single = self 
        self.db_dir = db_dir
        self.registered = False
        self.buddycast_interval = 15    # MOST IMPORTANT PARAMETER
        self.sync_interval = int(20.3*self.buddycast_interval)
        self.superpeer = superpeer
        self.log = log
        self.running = False
        self.data_ready_evt = Event()    # used for buddycast to notify peer view the peer list is ready
        if self.superpeer:
            print "Start as SuperPeer mode"
        
    def getInstance(*args, **kw):
        if BuddyCastFactory.__single is None:
            BuddyCastFactory(*args, **kw)
        return BuddyCastFactory.__single
    getInstance = staticmethod(getInstance)
    
    def register(self, secure_overlay, rawserver, launchmany, port, errorfunc, 
                 start, metadata_handler, torrent_collecting_solution, running):    
        if self.registered:
            return
        self.secure_overlay = secure_overlay
        self.rawserver = rawserver
        self.launchmany = launchmany
        self.errorfunc = errorfunc
        self.running = bool(running)
        
        self.registered = True
        if start:
            self.data_handler = DataHandler(self.rawserver, db_dir=self.db_dir)
            if isValidPort(port):
                self.data_handler.updatePort(port)
                
            self.bartercast_core = BarterCastCore(self.data_handler, secure_overlay, self.log)
                
            self.buddycast_core = BuddyCastCore(secure_overlay, launchmany, 
                   self.data_handler, self.buddycast_interval, self.superpeer,
                   metadata_handler, rawserver, torrent_collecting_solution, self.bartercast_core, self.log
                   )
            self.data_handler.buddycast_core = self.buddycast_core
            self.start_time = now()
            self.startup()
    
    def startup(self):
        if self.registered:
            # Arno, 2007-02-28: BC is now started self.buddycast_interval after client
            # startup. This is assumed to give enough time for UPnP to open the firewall
            # if any. So when you change this time, make sure it allows for UPnP to
            # do its thing, or add explicit coordination between UPnP and BC.
            # See BitTornado/launchmany.py
            self.rawserver.add_task(self.data_handler.postInit, 0)    # avoid flash crawd
            self.rawserver.add_task(self.doBuddyCast, 2)
            self.rawserver.add_task(self.data_handler.updateAllSim, randint(60,5*60))
            self.rawserver.add_task(self.sync, self.sync_interval)
            print >> sys.stdout, "BuddyCast starts up"
            
    def doBuddyCast(self):
        if not self.running:
            return
        buddycast_interval = self.getCurrrentInterval()
        self.rawserver.add_task(self.doBuddyCast, buddycast_interval)
        self.buddycast_core.work()
        
    def pauseBuddyCast(self):
        self.running = False
        
    def restartBuddyCast(self):
        if self.registered and not self.running:
            self.running = True
            self.doBuddyCast()
        
    def getCurrrentInterval(self):
        """
        install [#(peers - superpeers)==0] & start < 2min: interval = 1
        start < 30min: interval = 5
        start > 24hour: interval = 60
        other: interval = 15
        """
        
        past = now() - self.start_time
        if past < 2*60:
            if self.data_handler.npeers == 0:
                interval = 1
            else:
                interval = 5
        elif past < 30*60:
            interval = 5
        elif past > 24*60*60:
            interval = 60
        else:
            interval = 15
        return interval
        
    def sync(self):
        self.rawserver.add_task(self.sync, self.sync_interval)
        self.data_handler.sync()
        
    def handleMessage(self, permid, selversion, message):
        if not self.registered or not self.running:
            return False
        
        t = message[0]
        
        if t == BUDDYCAST:
            return self.gotBuddyCastMessage(message[1:], permid, selversion)
        elif t == KEEP_ALIVE:
            if message[1:] == '':
                return self.gotKeepAliveMessage(permid)
            else:
                return False
                
        elif t == BARTERCAST:
            if DEBUG:
                print >> sys.stderr, "Received bartercast message"
            return self.bartercast_core.gotBarterCastMessage(message[1:], permid, selversion)
            
        else:
            if DEBUG:
                print >> sys.stderr, "bc: wrong message to buddycast", ord(t), "Round", self.buddycast_core.round
            return False
        
    def gotBuddyCastMessage(self, msg, permid, selversion):
        if self.registered and self.running:
            return self.buddycast_core.gotBuddyCastMessage(msg, permid, selversion)
        else:
            return False
    
    def gotKeepAliveMessage(self, permid):
        if self.registered and self.running:
            return self.buddycast_core.gotKeepAliveMessage(permid)
        else:
            return False
    
    def handleConnection(self,exc,permid,selversion,locally_initiated):
        if self.registered:
            if self.running or exc is not None:    # if not running, only close connection
                self.buddycast_core.handleConnection(exc,permid,selversion,locally_initiated)
    
    def addMyPref(self, torrent):
        if self.registered:
            self.data_handler.addMyPref(torrent)
        
    def delMyPref(self, torrent):
        if self.registered:
            self.data_handler.delMyPref(torrent)
    
    def getTasteBuddies(self):
        return self.buddycast_core.getAllTasteBuddies()
    
    
class BuddyCastCore:
    def __init__(self, secure_overlay, launchmany, data_handler, 
                 buddycast_interval, superpeer, 
                 metadata_handler, rawserver, torrent_collecting_solution, bartercast_core, log=''):
        self.secure_overlay = secure_overlay
        self.launchmany = launchmany
        self.data_handler = data_handler
        self.buddycast_interval = buddycast_interval
        self.superpeer = superpeer    # change it for superpeers
        #self.superpeer_set = Set(self.data_handler.getSuperPeers())
        self.log = log
        self.dialback = DialbackMsgHandler.getInstance()

        self.ip = self.data_handler.getMyIp()
        self.port = self.data_handler.getMyPort()
        self.permid = self.data_handler.getMyPermid()
        # Jie: we must trainsfer my name to unicode here before sent out
        # because the receiver might not be able to transfer the name to unicode,
        # but the receiver might be able to display the unicode str correctly
        # in that he installed the character set and therefore unicode can map it
        self.name = dunno2unicode(self.data_handler.getMyName())    # encode it to unicode
        
        # --- parameters ---
        self.timeout = 5*60
        self.block_interval = 4*60*60   # block interval for a peer to buddycast
        self.short_block_interval = 4*60*60    # block interval if failed to connect the peer
        self.num_myprefs = 50       # num of my preferences in buddycast msg 
        self.max_collected_torrents = 50    # num of recently collected torrents (from BuddyCast 3)
        self.num_tbs = 10           # num of taste buddies in buddycast msg 
        self.num_tb_prefs = 10      # num of taset buddy's preferences in buddycast msg 
        self.num_rps = 10           # num of random peers in buddycast msg  
        # time to check connection and send keep alive message
        self.check_connection_round = max(1, 120/self.buddycast_interval)    
        self.max_conn_cand = 100 # max number of connection candidates
        self.max_conn_tb = 10    # max number of connectable taste buddies
        self.max_conn_rp = 10    # max number of connectable random peers
        self.max_conn_up = 10    # max number of unconnectable peers
        self.bootstrap_num = 10   # max number of peers to fill when bootstrapping
        self.bootstrap_interval = 10*60    # 10 min
        self.network_delay = self.buddycast_interval*2    # 30 seconds
        self.check_period = 120    # how many seconds to send keep alive message and check updates
        
        # --- memory ---
        self.send_block_list = {}    #TODO: record the earliest block peer to improve performance
        self.recv_block_list = {}
        self.connections = {}               # permid: overlay_version
        self.connected_taste_buddies = []   # [permid]
        self.connected_random_peers = []    # [permid]
        self.connected_connectable_peers = {}    # permid: connect_time
        self.connected_unconnectable_peers = {}    # permid: connect_time
        self.connection_candidates = {}     # permid: last_seen
        self.sorted_new_candidates = []     # sorted list: the smaller index, the older peer
        
        # --- stats ---
        self.target_type = 0
        self.next_initiate = 0
        self.round = 0     # every call to work() is a round
        self.bootstrapped = 0    # bootstrap once every 1 hours
        self.bootstrap_time = 0  # number of times to bootstrap
        self.total_bootstrapped_time = 0
        self.last_bootstrapped = 0    # bootstrap time of the last time
        self.start_time = now()
        self.last_check_time = 0
        
        # --- dependent modules ---
        self.metadata_handler = metadata_handler
        self.torrent_collecting = None
        if torrent_collecting_solution >= 1:
            self.torrent_collecting = SimpleTorrentCollecting(metadata_handler)
        #elif torrent_collecting_solution == 2:
        #    self.torrent_collecting = TiT4TaTTorrentCollecting(metadata_handler, rawserver)

        # -- misc ---
        self.dnsindb = self.data_handler.get_dns_from_peerdb
        if self.log:
            self.overlay_log = OverlayLogger(self.log)
            
        # Bartercast
        self.bartercast_core = bartercast_core
        self.bartercast_core.buddycast_core = self    
                    
    def get_peer_info(self, target_permid, include_permid=True, may_be_deleted=False):
        if not target_permid:
            return ' None '
        dns = self.dnsindb(target_permid)
        s_pid = show_permid_short(target_permid)
        sim = self.data_handler.getPeerSim(target_permid, may_be_deleted)
        try:
            ip = dns[0]
            port = dns[1]
            if include_permid:
                return ' %s %s:%s %.3f ' % (s_pid, ip, port, sim)
            else:
                return ' %s:%s %.3f' % (ip, port, sim)
        except:
            #print_exc()
            return ' %s ' % dns
        
    def work(self):
        """
            The engineer of buddycast empidemic protocol.
            In every round, it selects a target and initates a buddycast exchange,
            or idels due to replying messages in the last rounds.
        """
        
        try:
            self.round += 1
            self.print_debug_info('Active', 2)
            if self.log:
                nPeer, nPref, nCc, nBs, nBr, nSO, nCo, nCt, nCr, nCu = self.get_stats()
                self.overlay_log('BUCA_STA', self.round, (nPeer,nPref,nCc), (nBs,nBr), (nSO,nCo), (nCt,nCr,nCu))
        
            self.print_debug_info('Active', 3)
            self.updateSendBlockList()
            
            _now = now()
            if _now - self.last_check_time >= self.check_period:
                self.print_debug_info('Active', 4)
                self.keepConnections()
                self.data_handler.checkUpdate()
                gc.collect()
                self.last_check_time = _now
                
            if self.next_initiate > 0:
                # It replied some meesages in the last rounds, so it doesn't initiate Buddycast
                self.print_debug_info('Active', 6)
                self.next_initiate -= 1
            else:
                if len(self.connection_candidates) == 0:
                    self.booted = self._bootstrap(self.bootstrap_num)
                    self.print_debug_info('Active', 9)
        
                # It didn't reply any message in the last rounds, so it can initiate BuddyCast
                if len(self.connection_candidates) > 0:
                    r, target_permid = self.selectTarget()
                    self.print_debug_info('Active', 11, target_permid, r=r)
                    self.startBuddyCast(target_permid)
                
            if debug:
                print
            
        except:
            print_exc()
        
     # -------------- bootstrap -------------- #
    def _bootstrap(self, number):
        """ Select a number of peers from recent online peers which are not
            in send_block_list to fill connection_candidates.
            When to call this function is an issue to study.
        """
        
        _now = now()
        # bootstrapped recently, so wait for a while
        if self.bootstrapped > 1 and _now - self.last_bootstrapped < self.bootstrap_interval:
            self.bootstrap_time = 0    # let it read the most recent peers next time
            return -1
        
        peers = self.data_handler.getAllPeers()
        target_cands = Set(peers) - Set(self.send_block_list)
        recent_peers = self.selectRecentPeers(target_cands, number, 
                                              startfrom=self.bootstrap_time*number)
        
        for p in recent_peers:
            last_seen = self.data_handler.getPeerLastSeen(p)
            self.addConnCandidate(p, last_seen)
            
        self.bootstrap_time += 1
        self.total_bootstrapped_time += 1
        self.last_bootstrapped = _now
        self.bootstrapped = 0    # reset it to allow read more peers if needed
        return 1

    def selectRecentPeers(self, peer_list, number, startfrom=0):
        """ select a number of most recently online peers """
        
        if not peer_list:
            return []
        permids = []
        last_seens = []
        for p in peer_list:
            permids.append(p)
            last_seens.append(self.data_handler.getPeerLastSeen(p))
        npeers = len(permids)
        if npeers == 0:
            return []
        aux = zip(last_seens, permids)
        aux.sort()
        aux.reverse()
        peers = []
        i = 0
        # roll back when startfrom is bigger than npeers
        startfrom = startfrom % npeers    
        endat = startfrom + number
        for _, permid in aux[startfrom:endat]:
            peers.append(permid)
        return peers
            
    def addConnCandidate(self, peer_permid, last_seen):
        """ add a peer to connection_candidates, and only keep a number of
            the most fresh peers inside.
        """
        
        if peer_permid == self.permid or self.isBlocked(peer_permid, self.send_block_list):
            return
        if peer_permid in self.connection_candidates:    # already inside, update last seen
            self.removeConnCandidate(peer_permid)    # remove it and then add it for update
        new_item = (last_seen, peer_permid)
        if len(self.connection_candidates) < self.max_conn_cand:
            self.connection_candidates[peer_permid] = last_seen
            insort(self.sorted_new_candidates, new_item)
        else:    # full, remove the oldest one
            insort(self.sorted_new_candidates, new_item)
            _, out_peer = self.sorted_new_candidates[0]
            self.removeConnCandidate(out_peer)
            
    def isBlocked(self, peer_permid, block_list):
        if peer_permid not in block_list:
            return False
        unblock_time = block_list[peer_permid]
        if now() >= unblock_time - self.network_delay:    # 30 seconds for network delay
            block_list.pop(peer_permid)
            return False
        return True
            
    def removeConnCandidate(self, peer_permid):
        if peer_permid in self.connection_candidates:
            last_seen = self.connection_candidates.pop(peer_permid)
            new_item = (last_seen, peer_permid)
            if new_item in self.sorted_new_candidates:
                self.sorted_new_candidates.remove(new_item)
            else:
                if DEBUG:
                    print >> sys.stderr, "bc: warning - removed peer in Cc, but not in sorted_Cc", \
                    `new_item`, len(self.connection_candidates), len(self.sorted_new_candidates), \
                    "Round", self.round
        
    # -------------- routines in each round -------------- #
    def updateSendBlockList(self):
        """ Remove expired peers in send block list """
        
        _now = now()
        for p in self.send_block_list.keys():    # don't call isBlocked() for performance reason
            if _now >= self.send_block_list[p] - self.network_delay:
                if debug:
                    print "bc: *** unblock peer in send block list" + self.get_peer_info(p,may_be_deleted=True) + \
                        "expiration:", ctime(self.send_block_list[p])
                self.send_block_list.pop(p)
                    
    def keepConnections(self):
        """ Close expired connections, and extend the expiration of 
            peers in connection lists
        """
        
        for peer_permid in self.connections:
            # we don't close connection here, because if no incoming msg,
            # sockethandler will close connection in 5-6 min.
            
            if (peer_permid in self.connected_connectable_peers or \
                 peer_permid in self.connected_unconnectable_peers):   
                self.sendKeepAliveMsg(peer_permid)
                
    def sendKeepAliveMsg(self, peer_permid):
        """ Send keep alive message to a peer, and extend its expiration """
        
        if self.isConnected(peer_permid):
            overlay_protocol_version = self.connections[peer_permid]
            if overlay_protocol_version >= OLPROTO_VER_THIRD:
                # From this version, support KEEP_ALIVE message in secure overlay
                keepalive_msg = ''
                self.secure_overlay.send(peer_permid, KEEP_ALIVE+keepalive_msg, 
                                         self.keepaliveSendCallback)
            if debug:
                print "*** Send keep alive to peer", self.get_peer_info(peer_permid),  \
                    "overlay version", overlay_protocol_version
        
    def isConnected(self, peer_permid):
        return peer_permid in self.connections
    
    def keepaliveSendCallback(self, exc, peer_permid, other=0):        
        if exc is None:
            pass
        else:
            if debug:
                print >> sys.stderr, "bc: error - send keep alive msg", exc, \
                self.get_peer_info(peer_permid), "Round", self.round
            self.closeConnection(peer_permid, 'keepalive:'+str(exc))
        
    def gotKeepAliveMessage(self, peer_permid):
        if self.isConnected(peer_permid):
            if debug:
                print "bc: Got keep alive from", self.get_peer_info(peer_permid)
            return True
        else:
            if DEBUG:
                print >> sys.stderr, "bc: error - got keep alive from a not connected peer. Round", \
                    self.round
            return False
        
    # -------------- initiate buddycast, active thread -------------- #
    # ------ select buddycast target ------ #
    def selectTarget(self):
        """ select a most similar taste buddy or a most likely online random peer 
            from connection candidates list by 50/50 chance to initate buddycast exchange.
        """
        
        def selectTBTarget():
            # Select the most similar taste buddy 
            max_sim = (-1, None)
            for p in self.connection_candidates:
                sim = self.data_handler.getPeerSim(p)
                max_sim = max(max_sim, (sim, p))
            return max_sim[1]
            
        def selectRPTarget():
            # Randomly select a random peer 
            permid = None
            while len(self.connection_candidates) > 0:
                permid = sample(self.connection_candidates, 1)[0]
                if self.isBlocked(permid, self.send_block_list):
                    self.removeConnCandidate(permid)
                    continue
                else:
                    break
                
            return permid
    
        self.target_type = 1 - self.target_type
        if self.target_type == 0:  # select a taste buddy
            target_permid = selectTBTarget()
        else:       # select a random peer
            target_permid = selectRPTarget()
            
        return self.target_type, target_permid
    
    def randomSelectList(self, alist, num):
        """ Randomly select a number of items from a list """
        
        num = min(len(alist), num)
        selected = sample(alist, num)
        return selected
    
    # ------ start buddycast exchange ------ #
    def startBuddyCast(self, target_permid):
        """ Connect to a peer, create a buddycast message and send it """
        
        if not target_permid or target_permid == self.permid:
            return
        
        if not self.isBlocked(target_permid, self.send_block_list):
            self.secure_overlay.connect(target_permid, self.buddycastConnectCallback)
                        
            self.print_debug_info('Active', 12, target_permid)
            if self.log:
                dns = self.dnsindb(target_permid)
                if dns:
                    ip,port = dns
                    self.overlay_log('CONN_TRY', ip, port, show_permid(target_permid))
            
            # always block the target for a while not matter succeeded or not
            self.blockPeer(target_permid, self.send_block_list, self.short_block_interval)
            self.print_debug_info('Active', 13, target_permid)

            # remove it from candidates no matter if it is connectable
            self.removeConnCandidate(target_permid)
            self.print_debug_info('Active', 14, target_permid)

        else:
            if DEBUG:
                print >> sys.stderr, 'buddycast: peer', self.get_peer_info(target_permid), \
                    'is blocked while starting buddycast to it.', "Round", self.round
        
    def buddycastConnectCallback(self, exc, dns, target_permid, selversion):
        if exc is None:
            ## Create message depending on selected protocol version
            try:
                if not self.isConnected(target_permid):
                    if DEBUG:
                        raise RuntimeError, 'buddycast: not connected while calling connect_callback'
                    return
                
                self.print_debug_info('Active', 15, target_permid, selversion)
                        
                self.createAndSendBuddyCastMessage(target_permid, selversion, active=True)
                
            except:
                print_exc()
                print >> sys.stderr, "bc: error in reply buddycast msg",\
                    exc, dns, show_permid_short(target_permid), selversion, "Round", self.round

        else:
            if debug:
                print >> sys.stdout, "bc: warning - connecting to",\
                    show_permid_short(target_permid),exc,dns, ctime(now())
                    
    def createAndSendBuddyCastMessage(self, target_permid, selversion, active):
        
        buddycast_data = self.createBuddyCastMessage(target_permid, selversion)
        try:
            buddycast_msg = bencode(buddycast_data)
        except:
            print_exc()
            print >> sys.stderr, "error buddycast_data:", buddycast_data
            return
            
        if active:
            self.print_debug_info('Active', 16, target_permid)
        else:
            self.print_debug_info('Passive', 6, target_permid)
            
        self.secure_overlay.send(target_permid, BUDDYCAST+buddycast_msg, self.buddycastSendCallback)
        if active:
            self.print_debug_info('Active', 17, target_permid)
        else:
            self.print_debug_info('Passive', 7, target_permid)

        # Bartercast
        if self.bartercast_core != None and active:
            self.bartercast_core.createAndSendBarterCastMessage(target_permid, selversion)

            
        if self.log:
            dns = self.dnsindb(target_permid)
            if dns:
                ip,port = dns
                if active:
                    MSG_ID = 'ACTIVE_BC'
                else:
                    MSG_ID = 'PASSIVE_BC'
                msg = repr(readableBuddyCastMsg(buddycast_data))    # from utilities
                self.overlay_log('SEND_MSG', ip, port, show_permid(target_permid), selversion, MSG_ID, msg)
                
    def createBuddyCastMessage(self, target_permid, selversion):
        """ Create a buddycast message for a target peer on selected protocol version """
        
        target_ip,target_port = self.dnsindb(target_permid)
        if not target_ip or not target_port:
            return {}
        my_pref = self.data_handler.getMyLivePreferences(self.num_myprefs)       #[pref]
        taste_buddies = self.getTasteBuddies(self.num_tbs, self.num_tb_prefs, target_permid, target_ip, target_port, selversion)
        random_peers = self.getRandomPeers(self.num_rps, target_permid, target_ip, target_port, selversion)    #{peer:last_seen}
        buddycast_data = {'ip':self.ip,
                         'port':self.port,
                         'name':self.name,
                         'preferences':my_pref,
                         'taste buddies':taste_buddies, 
                         'random peers':random_peers}
        
        if selversion >= OLPROTO_VER_THIRD:
            # From this version, add 'connectable' entry in buddycast message
            connectable = self.isConnectable()
            buddycast_data['connectable'] = connectable
        
        if selversion >= OLPROTO_VER_FOURTH:
            recent_collect = self.metadata_handler.getRecentlyCollectedTorrents(self.max_collected_torrents)
            buddycast_data['collected torrents'] = recent_collect
        
        if selversion >= OLPROTO_VER_SIXTH:
            npeers = self.data_handler.get_npeers()
            ntorrents = self.data_handler.get_ntorrents()
            nmyprefs = self.data_handler.get_nmyprefs()
            buddycast_data['npeers'] = npeers
            buddycast_data['nfiles'] = ntorrents
            buddycast_data['ndls'] = nmyprefs
            
        return buddycast_data

    def getTasteBuddies(self, ntbs, ntbprefs, target_permid, target_ip, target_port, selversion):
        """ Randomly select a number of peers from connected_taste_buddies. """
        
        if not self.connected_taste_buddies:
            return []
        tb_list = self.connected_taste_buddies[:]
        if target_permid in tb_list:
            tb_list.remove(target_permid)
        peers = self.data_handler.getPeers(tb_list, ['permid', 'ip', 'port', 'similarity'])
        # filter peers with the same ip and port
        peers = filter(lambda p:p['ip']!=target_ip or int(p['port'])!=target_port, peers)
        
        for i in range(len(peers)):
            peers[i]['port'] = int(peers[i]['port'])
            
        # In overlay version 2, buddycast has 'age' field
        if selversion <= OLPROTO_VER_SECOND:
            for i in range(len(peers)):
                peers[i]['age'] = 0
            
        # In overlay version 2 and 3, buddycast doesn't have similarity field, and taste buddy has preferences
        if selversion <= OLPROTO_VER_THIRD:
            for i in range(len(peers)):
                peers[i].pop('similarity')
                peers[i]['preferences'] = self.data_handler.getPeerPrefList(peers[i]['permid'], 
                                                    ntbprefs, live=True, cache=False)

        # From overlay version 4, buddycast includes similarity for peers
        if selversion >= OLPROTO_VER_FOURTH:
            for i in range(len(peers)):
                peers[i]['similarity'] = int(peers[i]['similarity']+0.5)    # bencode doesn't accept float type
        
        return peers
    
    def getRandomPeers(self, nrps, target_permid, target_ip, target_port, selversion):
        """ Randomly select a number of peers from connected_random_peers. """
        
        if not self.connected_random_peers:
            return []
        rp_list = self.connected_random_peers[:]
        if target_permid in rp_list:
            rp_list.remove(target_permid)
        peers = self.data_handler.getPeers(rp_list, ['permid', 'ip', 'port', 'similarity'])
        peers = filter(lambda p:p['ip']!=target_ip or int(p['port'])!=target_port, peers)
        
        for i in range(len(peers)):
            peers[i]['port'] = int(peers[i]['port'])
            
        if selversion <= OLPROTO_VER_SECOND:    
            for i in range(len(peers)):
                peers[i]['age'] = 0
                
        if selversion <= OLPROTO_VER_THIRD:
            for i in range(len(peers)):
                peers[i].pop('similarity')

        if selversion >= OLPROTO_VER_FOURTH:
            for i in range(len(peers)):
                peers[i]['similarity'] = int(peers[i]['similarity']+0.5)
        
        return peers       
    
    def isConnectable(self):
        conn = self.dialback.isConnectable()
        if conn:
            return 1
        else:
            return 0

    def buddycastSendCallback(self, exc, target_permid, other=0):
        if exc is None:
            if debug:
                print "bc: *** msg was sent successfully to peer", \
                    self.get_peer_info(target_permid)
        else:
            if debug:
                print "bc: *** warning - error in sending msg to",\
                        self.get_peer_info(target_permid), exc
            self.closeConnection(target_permid, 'buddycast:'+str(exc))
            
    def blockPeer(self, peer_permid, block_list, block_interval=None):
        """ Add a peer to a block list """
        
        if block_interval is None:
            block_interval = self.block_interval
        unblock_time = now() + block_interval
        block_list[peer_permid] = unblock_time
        
    
    # ------ receive a buddycast message, for both active and passive thread ------ #
    def gotBuddyCastMessage(self, recv_msg, sender_permid, selversion):
        """ Received a buddycast message and handle it. Reply if needed """
        
        if not sender_permid or sender_permid == self.permid:
            print >> sys.stderr, "bc: error - got BuddyCastMsg from a None peer", \
                        sender_permid, recv_msg, "Round", self.round
            return False
        
        if self.isBlocked(sender_permid, self.recv_block_list):
            if DEBUG:
                print >> sys.stderr, "bc: warning - got BuddyCastMsg from a recv blocked peer", \
                        show_permid(sender_permid), "Round", self.round
            return True     # allow the connection to be kept. That peer may have restarted in 4 hours
        
        # Jie: Because buddycast message is implemented as a dictionary, anybody can 
        # insert any content in the message. It isn't secure if someone puts 
        # some fake contents inside and make the message very large. The same 
        # secure issue could happen in other protocols over the secure overlay layer. 
        # Therefore, I'd like to set a limitation of the length of buddycast message. 
        # The receiver should close the connection if the length of the message 
        # exceeds the limitation. According to my experience, the biggest 
        # buddycast message should be around 6~7KBytes. So the reasonable 
        # length limitation might be 10KB for buddycast message. 
        if MAX_BUDDYCAST_LENGTH > 0 and len(recv_msg) > MAX_BUDDYCAST_LENGTH:
            print >> sys.stderr, "bc: warning - got large BuddyCastMsg", len(recv_msg), "Round", self.round
            return False

        active = self.isBlocked(sender_permid, self.send_block_list)
        
        if active:
            self.print_debug_info('Active', 18, sender_permid)
        else:
            self.print_debug_info('Passive', 2, sender_permid)
            
        buddycast_data = {}
        try:
            buddycast_data = bdecode(recv_msg)
            buddycast_data.update({'permid':sender_permid})
            try:    # check buddycast message
                validBuddyCastData(buddycast_data, 0, 
                                   self.num_tbs, self.num_rps, self.num_tb_prefs)    # RCP 2            
            except RuntimeError, msg:
                try:
                    errmsg = str(msg)
                except:
                    errmsg = repr(msg)
                print >> sys.stderr, "bc: warning, got invalide BuddyCastMsg:", errmsg, \
                    "Round", self.round   # ipv6
                return False
           
           
            # update sender's ip and port in buddycast
            dns = self.dnsindb(sender_permid)
            sender_ip = dns[0]
            sender_port = dns[1]
            buddycast_data.update({'ip':sender_ip})
            buddycast_data.update({'port':sender_port})
            
            if self.log:
                if active:
                    MSG_ID = 'ACTIVE_BC'
                else:
                    MSG_ID = 'PASSIVE_BC'
                msg = repr(readableBuddyCastMsg(buddycast_data))    # from utilities
                self.overlay_log('RECV_MSG', sender_ip, sender_port, show_permid(sender_permid), selversion, MSG_ID, msg)
            
            # store discovered peers/preferences/torrents to cache and db
            conn = self.handleBuddyCastMessage(sender_permid, buddycast_data, selversion)
            if active:
                conn = 1
            
            if active:
                self.print_debug_info('Active', 19, sender_permid)
            else:
                self.print_debug_info('Passive', 3, sender_permid)
            
            # update sender and other peers in connection list
            addto = self.addPeerToConnList(sender_permid, conn)
            
            if active:
                self.print_debug_info('Active', 20, sender_permid)
            else:
                self.print_debug_info('Passive', 4, sender_permid)
            
        except:
            print_exc()
            #return True    # don't close connection, maybe my problem in handleBuddyCastMessage
        
        self.blockPeer(sender_permid, self.recv_block_list)
        
        # update torrent collecting module
        #self.data_handler.checkUpdate()
        torrents2down = buddycast_data.get('preferences', [])
        torrents2down += buddycast_data.get('collected torrents', [])    # get sth. from BuddyCast 3
        if self.torrent_collecting and torrents2down:
            self.torrent_collecting.updatePreferences(sender_permid, torrents2down, selversion)
        
        if active:
            self.print_debug_info('Active', 21, sender_permid)
        else:
            self.print_debug_info('Passive', 5, sender_permid)
                
        if not active:
            self.replyBuddyCast(sender_permid, selversion)    

        # show activity
        buf = dunno2unicode('"'+buddycast_data['name']+'"')
        self.launchmany.set_activity(ACT_RECOMMEND, buf)
        self.data_handler.increaseBuddyCastTimes(sender_permid)
        
        if debug:
            print "********************* Got BuddyCast Message from", \
                self.get_peer_info(sender_permid), " Yahoo!!! *********************"
        
        return True
        
    def handleBuddyCastMessage(self, sender_permid, buddycast_data, selversion):
        """ Handle received buddycast message 
            Add peers, torrents and preferences into database and update last seen
            Add fresh peers to candidate list
        """
        
        _now = now()
        conn = buddycast_data.get('connectable', 0)    # 0 - unknown
        tbs = buddycast_data.pop('taste buddies')
        rps = buddycast_data.pop('random peers')
        
        max_tb_sim = 1
        if selversion >= OLPROTO_VER_FOURTH:
            for tb in tbs:
                sim = tb.get('similarity', 0)
                max_tb_sim = max(max_tb_sim, sim)
                
        if selversion >= OLPROTO_VER_SIXTH:
            self.data_handler.updatePeerLevelStats(sender_permid,buddycast_data['npeers'],buddycast_data['nfiles'],buddycast_data['ndls'])
                
        tbs += [buddycast_data]
        for tb in tbs:
            peer_permid = tb['permid']
            age = max(tb.get('age', 0), 0)    # From secure overlay version 3, it doesn't include 'age'
            last_seen = _now - age
            self.data_handler.addPeer(peer_permid, last_seen, tb)    # new peer
            self.data_handler.addPeerPreferences(peer_permid, tb.get('preferences',[]))
            if selversion >= OLPROTO_VER_FOURTH:
                sim = tb.get('similarity', 0)
                if sim > 0:
                    self.data_handler.addRelativeSim(sender_permid, peer_permid, sim, max_tb_sim)
            if peer_permid != sender_permid:
                self.addConnCandidate(peer_permid, last_seen)
        
        for rp in rps:
            peer_permid = rp['permid']
            age = max(rp.get('age', 0), 0)
            last_seen = _now - age
            self.data_handler.addPeer(peer_permid, last_seen, rp)
            if selversion >= OLPROTO_VER_FOURTH:
                sim = rp.get('similarity', 0)
                if sim > 0:
                    self.data_handler.addRelativeSim(sender_permid, peer_permid, sim, max_tb_sim)
            if peer_permid != sender_permid:    # to be safe; shouldn't happen
                self.addConnCandidate(peer_permid, last_seen)
            
        if len(self.connection_candidates) > 10:
            self.bootstrapped += 1
            
        # TODO: return new added peers/torrents/prefs
        return conn
        
    def removeFromConnList(self, peer_permid):
        removed = 0
        if peer_permid in self.connected_connectable_peers:     # Ct
            self.connected_connectable_peers.pop(peer_permid)
            try:
                self.connected_taste_buddies.remove(peer_permid)
            except ValueError:
                self.connected_random_peers.remove(peer_permid)
            removed = 1
        if peer_permid in self.connected_unconnectable_peers:    # Cu
            self.connected_unconnectable_peers.pop(peer_permid)
            removed = 2
        return removed
        
    def addPeerToConnList(self, peer_permid, connectable=0):
        """ Add the peer to Ct, Cr or Cu """
        
        # remove the existing peer from lists so that its status can be updated later
        self.removeFromConnList(peer_permid)    
        
        if not self.isConnected(peer_permid):
            print >> sys.stderr, "bc: cannot add a unconnected peer to conn list", "Round", self.round
            return
        
        _now = now()
        
        if connectable == 1:
            self.addPeerToConnCP(peer_permid, _now)
            addto = '(reachable peer)'
        else:
            self.addPeerToConnUP(peer_permid, _now)
            addto = '(peer deemed unreachable)'
            
        return addto
           
    def updateTBandRPList(self):
        """ Select the top 10 most similar (sim>0) peer to TB and others to RP """
        
        nconnpeers = len(self.connected_connectable_peers)
        if nconnpeers == 0:
            self.connected_taste_buddies = []
            self.connected_random_peers = [] 
            return
        
        tmplist = []
        tbs = []
        rps = []
        for peer in self.connected_connectable_peers:
            sim = self.data_handler.getPeerSim(peer)
            if sim > 0:
                tmplist.append([sim, peer])
            else:
                rps.append(peer)
        tmplist.sort()
        tmplist.reverse()
        
        #ntb = self.max_conn_tb    # 10 tb & 10 rp
        ntb = min((nconnpeers+1)/2, self.max_conn_tb)    # half tb and half rp
        if len(tmplist) > 0:
            for sim,peer in tmplist[:ntb]:
                tbs.append(peer)
        if len(tmplist) > ntb:
            rps = [peer for sim,peer in tmplist[ntb:]] + rps
        
        # remove the oldest peer from both random peer list and connected_connectable_peers
        if len(rps) > self.max_conn_rp:
            tmplist = []
            for peer in rps:
                connect_time = self.connected_connectable_peers[peer]
                tmplist.append([connect_time, peer])
            tmplist.sort()
            tmplist.reverse()
            rps = []
            i = 0
            for last_seen,peer in tmplist:
                if i < self.max_conn_rp:
                    rps.append(peer)
                else:
                    self.connected_connectable_peers.pop(peer)
                i += 1
            
        self.connected_taste_buddies = tbs
        self.connected_random_peers = rps
            
    def addPeerToConnCP(self, peer_permid, conn_time):
        self.connected_connectable_peers[peer_permid] = conn_time
        self.updateTBandRPList()
        
    def addNewPeerToConnList(self, conn_list, max_num, peer_permid, conn_time):
        """ Add a peer to a connection list, and pop the oldest peer out """
        
        if max_num <= 0 or len(conn_list) < max_num:
            conn_list[peer_permid] = conn_time
            return None
        
        else:
            oldest_peer = (conn_time+1, None)
            initial = 'abcdefghijklmnopqrstuvwxyz'
            separator = ':-)'
            for p in conn_list:
                _conn_time = conn_list[p]
                r = randint(0, self.max_conn_tb)
                name = initial[r] + separator + p 
                to_cmp = (_conn_time, name)
                oldest_peer = min(oldest_peer, to_cmp)
                
            if conn_time >= oldest_peer[0]:     # add it
                out_peer = oldest_peer[1].split(separator)[1]
                conn_list.pop(out_peer)            
                conn_list[peer_permid] = conn_time
                return out_peer
            return peer_permid

    def addPeerToConnUP(self, peer_permid, conn_time):
        ups = self.connected_unconnectable_peers
        if peer_permid not in ups:
            out_peer = self.addNewPeerToConnList(ups, 
                                      self.max_conn_up, peer_permid, conn_time)
            if out_peer != peer_permid:
                return True
        return False
            
    # -------------- reply buddycast, passive thread -------------- #
    def replyBuddyCast(self, target_permid, selversion):
        """ Reply a buddycast message """
        
        if not self.isConnected(target_permid):
            print >> sys.stderr, 'buddycast: lost connection while replying buddycast', \
                "Round", self.round
            return
        
        self.createAndSendBuddyCastMessage(target_permid, selversion, active=False)
        
        self.blockPeer(target_permid, self.send_block_list, self.short_block_interval)
        self.print_debug_info('Passive', 8, target_permid)

        self.removeConnCandidate(target_permid)
        self.print_debug_info('Passive', 9, target_permid)

        self.next_initiate += 1        # Be idel in next round
        self.print_debug_info('Passive', 10)
        
        
    # -------------- handle overlay connections from SecureOverlay ---------- #
    def handleConnection(self,exc,permid,selversion,locally_initiated):
        if exc is None and permid != self.permid:    # add a connection
            self.addConnection(permid, selversion, locally_initiated)
        else:
            self.closeConnection(permid, 'overlayswarm:'+str(exc))

        if debug:
            print >> sys.stdout, "bc: handle conn from overlay", exc, \
                self.get_peer_info(permid), "selversion:", selversion, \
                "local_init:", locally_initiated, ctime(now())
        
    def addConnection(self, peer_permid, selversion, locally_initiated):
        _now = now()
        if not self.isConnected(peer_permid):
            self.connections[peer_permid] = selversion # add a new connection
            self.data_handler.addPeer(peer_permid, _now)
            #self.data_handler.setPeerLastSeen(peer_permid, _now)   # done by secure overlay
            # add connection from secure overlay
            addto = self.addPeerToConnList(peer_permid, locally_initiated)
            
            dns = self.get_peer_info(peer_permid, include_permid=False)
            buf = '%s %s'%(dns, addto)
            self.launchmany.set_activity(ACT_MEET, buf)

            torrents2down = self.data_handler.getPeerPrefList(peer_permid, cache=False)
            if self.torrent_collecting and torrents2down:
                self.torrent_collecting.updatePreferences(peer_permid, torrents2down, selversion)
            
            if debug:
                print >> sys.stdout, "bc: add connection", \
                    self.get_peer_info(peer_permid), "to", addto
            if self.log:
                dns = self.dnsindb(peer_permid)
                if dns:
                    ip,port = dns
                    self.overlay_log('CONN_ADD', ip, port, show_permid(peer_permid), selversion)

    def closeConnection(self, peer_permid, reason):
        """ Close connection with a peer, and remove it from connection lists """
        
        if debug:
            print >> sys.stdout, "bc: close connection:", self.get_peer_info(peer_permid, may_be_deleted=True)
        
        self.data_handler.setPeerLastSeen(peer_permid, now())
        if self.isConnected(peer_permid):
            self.connections.pop(peer_permid)
        removed = self.removeFromConnList(peer_permid)
        if removed == 1:
            self.updateTBandRPList()
        
        if self.torrent_collecting:
            self.torrent_collecting.closeConnection(peer_permid)
            
        if self.log:
            dns = self.dnsindb(peer_permid)
            if dns:
                ip,port = dns
                self.overlay_log('CONN_DEL', ip, port, show_permid(peer_permid), reason)

    def peerInUse(self, peer_permid):
        if peer_permid in self.connections or peer_permid in self.connection_candidates:
            return True
        return False

    # -------------- print debug info ---------- #
    def get_stats(self):
        nPeer = len(self.data_handler.peers)
        nPref = nPeer #len(self.data_handler.preferences)
        nCc = len(self.connection_candidates)
        nBs = len(self.send_block_list)
        nBr = len(self.recv_block_list)
        nSO = len(self.secure_overlay.debug_get_live_connections())
        nCo = len(self.connections)
        nCt = len(self.connected_taste_buddies)
        nCr = len(self.connected_random_peers)
        nCu = len(self.connected_unconnectable_peers)
        return nPeer, nPref, nCc, nBs, nBr, nSO, nCo, nCt, nCr, nCu
    
    def print_debug_info(self, thread, step, target_permid=None, selversion=0, r=0, addto=''):
        if not debug:
            return
        print "bc: *****", thread, str(step), "-",
        if thread == 'Active':
            if step == 2:
                print "Working:", now() - self.start_time, \
                    "seconds since start. Round", self.round, "Time:", ctime(now())
                nPeer, nPref, nCc, nBs, nBr, nSO, nCo, nCt, nCr, nCu = self.get_stats()
                print "bc: *** Status: nPeer nPref nCc: %d %d %d  nBs nBr: %d %d  nSO nCo nCt nCr nCu: %d %d %d %d %d" % \
                                      (nPeer,nPref,nCc,           nBs,nBr,        nSO,nCo, nCt,nCr,nCu)
                if nSO != nCo:
                    print "bc: warning - nSo and nCo is inconsistent"
                if nCc > self.max_conn_cand or nCt > self.max_conn_tb or nCr > self.max_conn_rp or nCu > self.max_conn_up:
                    print "bc: warning - nCC or nCt or nCr or nCu overloads"
                _now = now()
                buf = ""
                i = 1
                for p in self.connected_taste_buddies:
                    buf += "bc: %d taste buddies: "%i + self.get_peer_info(p) + str(_now-self.connected_connectable_peers[p]) + " version: " + str(self.connections[p]) + "\n"
                    i += 1
                print buf
                
                buf = ""
                i = 1
                for p in self.connected_random_peers:
                    buf += "bc: %d random peers: "%i + self.get_peer_info(p) + str(_now-self.connected_connectable_peers[p]) + " version: " + str(self.connections[p]) + "\n"
                    i += 1
                print buf
                
                buf = ""
                i = 1
                for p in self.connected_unconnectable_peers:
                    buf += "bc: %d unconnectable peers: "%i + self.get_peer_info(p) + str(_now-self.connected_unconnectable_peers[p]) + " version: " + str(self.connections[p]) + "\n"
                    i += 1
                print buf
                buf = ""
                totalsim = 0
                nsimpeers = 0
                minsim = 1e10
                maxsim = 0
                for p in self.data_handler.peers:
                    sim = self.data_handler.getPeerSim(p)
                    if sim > 0:
                        nsimpeers += 1
                        totalsim += sim
                        minsim = min(sim, minsim)
                        maxsim = max(sim, maxsim)
                        #buf += "bc: * peer: " + self.get_peer_info(p) + "\n"
                if nsimpeers > 0:
                    meansim = totalsim/nsimpeers
                else:
                    meansim = 0
                print "bc: * sim peer: %d %.3f %.3f %.3f %.3f\n" % (nsimpeers, totalsim, meansim, minsim, maxsim)

            elif step == 3:
                print "check blocked peers: Round", self.round
                
            elif step == 4:
                print "keep connections with peers: Round", self.round
                
            elif step == 6:
                print "idle loop:", self.next_initiate
                
            elif step == 9: 
                print "bootstrapping: select", self.bootstrap_num, \
                    "peers recently seen from Mega Cache"
                if self.booted < 0:
                    print "bc: *** bootstrapped recently, so wait for a while"
                elif self.booted == 0:
                    print "bc: *** no peers to bootstrap. Try next time"
                else:
                    print "bc: *** bootstrapped, got", len(self.connection_candidates), \
                      "peers in Cc. Times of bootstrapped", self.total_bootstrapped_time
                    buf = ""
                    for p in self.connection_candidates:
                        buf += "bc: * cand:" + self.get_peer_info(p) + "\n"
                    print buf
            
            elif step == 11:
                buf = "select "
                if r == 0:
                    buf += "a most similar taste buddy"
                else:
                    buf += "a most likely online random peer"
                buf += " from Cc for buddycast out\n"
                
                if target_permid:
                    buf += "bc: *** got target %s sim: %s last_seen: %s" % \
                    (self.get_peer_info(target_permid),
                     self.data_handler.getPeerSim(target_permid),
                     ctime(self.data_handler.getPeerLastSeen(target_permid)))
                else:
                    buf += "bc: *** no target to select. Skip this round"
                print buf

            elif step == 12:
                print "connect a peer to start buddycast", self.get_peer_info(target_permid)
                
            elif step == 13:
                print "block connected peer in send block list", \
                    self.get_peer_info(target_permid), self.send_block_list[target_permid]
                    
            elif step == 14:
                print "remove connected peer from Cc", \
                    self.get_peer_info(target_permid), "removed?", target_permid not in self.connection_candidates

            elif step == 15:
                print "peer is connected", \
                    self.get_peer_info(target_permid), "overlay version", selversion
                
            elif step == 16:
                print "create buddycast to send to", self.get_peer_info(target_permid)
                
            elif step == 17:
                print "send buddycast msg to", self.get_peer_info(target_permid)
                
            elif step == 18:
                print "receive buddycast message from peer %s" % self.get_peer_info(target_permid)
                
            elif step == 19:
                print "store peers from incoming msg to cache and db"
                
            elif step == 20:
                print "add connected peer %s to connection list %s" % (self.get_peer_info(target_permid), addto)
                
            elif step == 21:
                print "block connected peer in recv block list", \
                    self.get_peer_info(target_permid), self.recv_block_list[target_permid]
                
        if thread == 'Passive': 
            if step == 2:
                print "receive buddycast message from peer %s" % self.get_peer_info(target_permid)
                
            elif step == 3:
                print "store peers from incoming msg to cache and db"
                
            elif step == 4:
                print "add connected peer %s to connection list %s" % (self.get_peer_info(target_permid), addto)
        
            elif step == 5:
                print "block connected peer in recv block list", \
                    self.get_peer_info(target_permid), self.recv_block_list[target_permid]
            
            elif step == 6:
                print "create buddycast to reply to", self.get_peer_info(target_permid)
            
            elif step == 7:
                print "reply buddycast msg to", self.get_peer_info(target_permid)
                
            elif step == 8:
                print "block connected peer in send block list", \
                    self.get_peer_info(target_permid), self.send_block_list[target_permid]
        
            elif step == 9:
                print "remove connected peer from Cc", \
                    self.get_peer_info(target_permid), "removed?", target_permid not in self.connection_candidates

            elif step == 10:
                print "add idle loops", self.next_initiate
        sys.stdout.flush()
        sys.stderr.flush()

    def getAllTasteBuddies(self):
        return self.connected_taste_buddies
        
        
class DataHandler:
    def __init__(self, rawserver, db_dir=''):
        self.rawserver = rawserver
        # --- database handlers ---
        self.my_db = MyDBHandler(db_dir=db_dir)
        self.peer_db = SynPeerDBHandler(db_dir=db_dir)
        self.superpeer_db = SuperPeerDBHandler(db_dir=db_dir)
        self.torrent_db = SynTorrentDBHandler(db_dir=db_dir)
        self.mypref_db = MyPreferenceDBHandler(db_dir=db_dir)
        self.pref_db = PreferenceDBHandler(db_dir=db_dir)
        self.friend_db = FriendDBHandler(db_dir=db_dir)
        self.superpeer_db = SuperPeerDBHandler(db_dir=db_dir)
        self.dbs = [self.my_db, self.peer_db, self.superpeer_db,
                    self.torrent_db, self.mypref_db, self.pref_db]
        self.mypreflist = []    # torrent_infohashes
        self.myfriends = Set(self.friend_db.getFriendList())
        self.myprefhash = array('l',[])
        self.peers = {}    # permid: [similarity, last_seen, prefs]    prefs: array('l')
        self.default_peer = [0,0, array('l',[])]
        self.owners = {}    # torrents_of_mine: Set(permid)
        self.permid = self.getMyPermid()
        self.nprefs = 0
        self.total_pref_changed = 0
        # how many peers to load into cache from db
        self.max_num_peers = 2000
        self.max_peer_in_db = 10000
        self.time_sim_weight = 4*60*60  # every 4 hours equals to a point of similarity
        # after added some many (user, item) pairs, update sim of item to item
        self.update_i2i_threshold = 100
        self.npeers = self.peer_db.size() - self.superpeer_db.size()
        self.buddycast_core = None

    def sync(self):
        for db in self.dbs:
            db.sync()
            
    def close(self):
        for db in self.dbs:
            db.close()
    
    def __del__(self):
        #self.close()
        pass

    def getMyName(self, name=''):
        return self.my_db.get('name', name)
        
    def getMyIp(self, ip=''):
        return self.my_db.get('ip', ip)
    
    def getMyPort(self, port=0):
        return self.my_db.get('port', port)
    
    def updatePort(self, port):
        self.my_db.put('port', port)
  
    def getMyPermid(self, permid=''):
        return self.my_db.get('permid', permid)
        
    def getSuperPeers(self):
        return self.superpeer_db.getSuperPeerList()
        
    def postInit(self):
        # build up a cache layer between app and db
        self.updateMyPreferences()
        self.updateAllPeers(self.max_num_peers)
        self.updateAllPref()
        #self.updateAllSim()
        #self.updateAllI2ISim()
        
    def updateAllSim(self):
        # update similarity to all peers to keep consistent
        starttime = time()
        totalsim = 0.0
        for peer in self.peers:
            sim = self.updateSimilarity(peer)
            totalsim += sim
        npeers = len(self.peers)
        if npeers > 0:
            meansim = totalsim/npeers
        else:
            meansim = 0
        if debug:
            print "bc: updated All P2P sim", meansim, npeers, time()-starttime, ctime(now())
        
    def addMyPref(self, torrent):
        torrentdata = self.torrent_db.getTorrent(torrent)
        if torrentdata.get('secret', False):
            if DEBUG:
                print >> sys.stderr, 'Omitting secret download: %s' % torrentdata.get('info', {}).get('name', 'unknown')
            return # do not buddycast secret downloads
        
        if torrent not in self.mypreflist:
            self.mypreflist.append(torrent)
            torrent_hash = hash(torrent)
            insort(self.myprefhash, torrent_hash)
            self.updateOwners(torrent)
            self.rawserver.add_task(self.updateAllSim, 5)
            self.total_pref_changed += self.update_i2i_threshold
            
    def delMyPref(self, torrent):
        if torrent in self.mypreflist:
            self.mypreflist.remove(torrent)
            torrent_hash = hash(torrent)
            self.myprefhash.remove(torrent_hash)
            self.owners.pop(torrent_hash)
            self.rawserver.add_task(self.updateAllSim, 10)
            self.total_pref_changed += self.update_i2i_threshold

    def updateOwners(self, torrent):
        torrent_hash = hash(torrent)
        self.owners[torrent_hash] = Set()
        for peer in self.peers:
            if torrent_hash in self.getPeerPrefList(peer):
                self.owners[torrent_hash].add(peer)
        
    def updateMyPreferences(self):
        self.mypreflist = self.mypref_db.getRecentPrefList()
        for torrent in self.mypreflist:
            torrent_hash = hash(torrent)
            self.owners[torrent_hash] = Set()
        self.myprefhash = self.owners.keys()
        self.myprefhash.sort()
        self.myprefhash = array('l', self.myprefhash)
    
    def updateAllPeers(self, num_peers=None):
        """ Read peers from db and put them in self.peers.
            At most self.max_num_peers recently seen peers can be cached.
        """
        
        all_peerlist = self.peer_db.getPeerList()
        try:
            all_peerlist.remove(self.permid)
        except ValueError:
            pass
        _peer_values = self.getPeers(all_peerlist, ['similarity','last_seen'])
        peer_values = []
        for p in _peer_values:
            peer_values.append([p['similarity'], p['last_seen']])
        if not num_peers or len(all_peerlist) <= num_peers:
            self.peers = dict(zip(all_peerlist, peer_values))   # all peers
        else:
            if len(all_peerlist) > num_peers:
                # get a number of peers first based on sim, then based on last_seen
                cmp_values = [value[0]+value[1]/self.time_sim_weight for value in peer_values]
                tmp_list = zip(cmp_values, peer_values, all_peerlist)
                tmp_list.sort()
                tmp_list.reverse()  # the smaller index, the more important

                # too many peers in DB. delete some peers from DB
                if len(tmp_list) > self.max_peer_in_db:
                    num_peers_2_del = int(len(tmp_list) - self.max_peer_in_db + self.max_peer_in_db*0.02)
                    peers2del = [peer for (_, _, peer) in tmp_list[-1*num_peers_2_del:]]
                    print >> sys.stderr, "**** buddycast delete peers from db", "#peers2del", len(peers2del), "#peers in db", len(tmp_list), "max limit", self.max_peer_in_db
                    for peer in peers2del:
                        self.peer_db.deletePeer(peer, updateFlag=False)     # friends will not be deleted
                
                tmp_list = tmp_list[:num_peers]
                tmp_list = [(peer, peer_value) for (_, peer_value, peer) in tmp_list]
                self.peers = dict(tmp_list)
        # used to notify peer view that peer list is ready
        if DEBUG:
            print >> sys.stderr, "**** buddycast update all peers", "#peers in cache", len(self.peers), "#peers in db", len(all_peerlist), "max limit", num_peers

        #print "******* buddycast thread:", currentThread().getName()
        BuddyCastFactory.getInstance().data_ready_evt.set()    
        return self.peers
    
    def getPeers(self, peer_list, keys):
        return self.peer_db.getPeers(peer_list, keys)
    
    def updateAllPref(self):
        """ Read preferences of peers in self.peers to write into preferences """
        
        self.nprefs = 0
        for peer_permid in self.peers:
            self.nprefs += self.updatePeerPref(peer_permid)
        self.update_i2i_threshold = max(100, self.nprefs*0.01)
                
    def updatePeerPref(self, peer_permid):
        peerprefs = []
        for p in self.pref_db.getPrefList(peer_permid):
            peerprefs.append(hash(p))
        peerprefs.sort()
        peerprefs = array('l', peerprefs)
            
        if len(self.peers[peer_permid]) > 2:
            self.peers[peer_permid][2] = peerprefs
        elif len(self.peers[peer_permid]) == 2:
            self.peers[peer_permid].append(peerprefs)
            
        for torrent_hash in self.owners:
            if torrent_hash in peerprefs:
                self.owners[torrent_hash].add(peer_permid)
        return len(peerprefs)
        
    def getAllPeers(self, num_peers=None):
        """ Get a number of peers from self.peers """
        
        if not self.peers or num_peers is not None:
            self.updateAllPeers(num_peers)
        return self.peers
    
    def getPeerPrefList(self, permid, num=0, live=False, cache=True):
        """ Get a number of peer's preference list. Get all if num==0.
            If live==True, dead torrents won't include
        """
        
        if cache:
            value = self.peers.get(permid, self.default_peer)
            if len(value) > 2:
                preflist = value[2]    # array('l', torrent_hash)
            else:
                self.updatePeerPref(permid)
                value = self.peers.get(permid, self.default_peer)
                preflist = value[2]
        else:
            preflist = self.pref_db.getPrefList(permid)    # [infohash]
        if live:    # remove dead torrents
            preflist = self.torrent_db.getLiveTorrents(preflist)
        if num == 0 or num > len(preflist):
            return preflist
        else:
            prefs = sample(preflist, num)    # randomly select 10 prefs to avoid starvation
            return prefs
    
    def getMyLivePreferences(self, num):
        """ Get a number of my preferences. Get all if num==0 """
        
        mypreflist = self.torrent_db.getLiveTorrents(self.mypreflist)
        if num > 0 and len(mypreflist) > num:
            return mypreflist[:num]
        else:
            return mypreflist
    
    def getPeerLastSeen(self, peer_permid):
        if peer_permid not in self.peers:
            return 0
        return self.peers[peer_permid][1]
    
    def getPeerSim(self, peer_permid, may_be_deleted=False, raw=False):
        if peer_permid not in self.peers:
            if not may_be_deleted:
                print_stack()
                print >> sys.stderr, "bc: try to get a peer sim but it isn't in cache", \
                    show_permid_short(peer_permid), ctime(now())
            return 0
        if not raw:    
            # negative value means it is calculated from other peers, not itself. See addRelativeSim()
            return abs(self.peers[peer_permid][0])
        else:
            return self.peers[peer_permid][0]
    
    def setPeerLastSeen(self, peer_permid, last_seen):
        old_last_seen = self.getPeerLastSeen(peer_permid)
        new_last_seen = max(old_last_seen, last_seen)
        if peer_permid in self.peers:    # could have been deleted if self.peers was full
            self.peers[peer_permid][1] = new_last_seen
        self.peer_db.updatePeer(peer_permid, 'last_seen', new_last_seen)
                
    def setPeerSim(self, peer_permid, sim):
        self.peers[peer_permid][0] = sim
        self.peer_db.updatePeer(peer_permid, 'similarity', sim, updateFlag=False)

    def _addPeer(self, peer_permid, last_seen):
        """ add a peer to cache """
        # Secure Overlay should have added this peer to database.
        
        if not self.peers.has_key(peer_permid):
            #sim = self.peer_db.getPeerSim(peer_permid)
            self.peers[peer_permid] = [last_seen, 0]    # last_seen, similarity, pref
        
        if len(self.peers[peer_permid]) == 2:
            self.total_pref_changed += self.updatePeerPref(peer_permid)
            self.updateSimilarity(peer_permid)
        

    def addPeer(self, peer_permid, last_seen, peer_data=None):  
        """ add a peer from buddycast message to both cache and db """
        
        if peer_permid != self.permid:
            self._addPeer(peer_permid, last_seen)    
            if peer_data is not None:
                self._addPeerToDB(peer_permid, last_seen, peer_data)

    def removePeers(self, num):
        tmplist = []
        for peer in self.peers:
            if self.buddycast_core.peerInUse(peer):
                continue
            sim = self.getPeerSim(peer)
            last_seen = self.getPeerLastSeen(peer)
            nprefs = len(self.getPeerPrefList(peer))
            comp = sim + nprefs + last_seen/self.time_sim_weight
            value = [comp, peer]
            tmplist.append(value)
        tmplist.sort()
        for _,peer in tmplist[:num]:
            if self.peers.has_key(peer):
                self.peers.pop(peer)
                if peer not in self.myfriends:
                    self.peer_db.hidePeer(peer)
                
    def addPeerPreferences(self, peer_permid, prefs):
        """ add a peer's preferences to both cache and db """
        
        if peer_permid == self.permid:
            return 0
        
        changed = 0
        for torrent in prefs:
            # add to DB
            torrent_hash = hash(torrent)
            if torrent_hash not in self.getPeerPrefList(peer_permid):
                insort(self.peers[peer_permid][2], torrent_hash)
                # Jie: an important change since 4.0: don't add it to torrent_db to avoid unlimited size of torrent_db
                # a record is added to the db only when added a torrent file
                #self.torrent_db.addTorrent(torrent, updateFlag=False)  
                self.pref_db.addPreference(peer_permid, torrent)
                changed += 1
                
        if changed:
            self.total_pref_changed += changed
            self.updateSimilarity(peer_permid)
            
    def checkUpdate(self):
        if self.total_pref_changed >= self.update_i2i_threshold:
            self.updateAllI2ISim()
            
        npeers = len(self.peers)
        if npeers > self.max_num_peers*1.05:    # remove peers when exceeded 5%
            self.removePeers(npeers - self.max_num_peers)
            
    def updateSimilarity(self, peer_permid):
        """ update a peer's similarity """
        
        sim = self.computeP2PSimilarity(peer_permid)
        #print "***** update Similarity", sim
        self.setPeerSim(peer_permid, sim)
        return sim
        
    def getP2PSimilarityOld(self, peer_permid):
        """ calculate the similarity
            PeerSim = int(1000*len(pref1&pref2)/(len(pref1)*len(pref2))**0.5)
        """
        
        pref1 = self.myprefhash
        pref2 = self.getPeerPrefList(peer_permid)
        sim = P2PSimSorted(pref1, pref2)
        return sim
    
    def computeP2PSimilarity(self, peer_permid):
        peer_pref = self.getPeerPrefList(peer_permid)
        sim = P2PSimLM(peer_permid, self.myprefhash, peer_pref, self.owners, self.nprefs, mu=1.0)
        return sim
    
    def updateAllI2ISim(self, ret=False):
        # A temporary user to item similarity
        # TODO: incrementally update
        starttime = time()
        torrent_sim = {}    # [sim, pop]
        npref = 0
        for peer in self.peers:
            preflist = self.getPeerPrefList(peer, cache=True)
            peer_sim = self.getPeerSim(peer)
            for torrent in preflist:
                if torrent not in torrent_sim:
                    torrent_sim[torrent] = 0
                torrent_sim[torrent] += peer_sim + 1
                npref += 1
        self.nprefs = npref
        self.update_i2i_threshold = max(100, self.nprefs*0.01)
        
        maxsim = 0
        minsim = 10**9
        totalsim = 0
        ngoodtorrents = 0
        for infohash in self.torrent_db.getAllTorrents():
            torrent = hash(infohash)
            if torrent in torrent_sim:
                sim = torrent_sim[torrent]
                self.torrent_db.updateTorrentRelevance(infohash, sim, updateFlag=False)
                if debug:
                    maxsim = max(maxsim, sim)
                    minsim = min(minsim, sim)
                    totalsim += sim
                    if sim > 0:
                        ngoodtorrents += 1
        
        self.total_pref_changed = 0
        
        if debug:
            npeer = len(self.peers)
            if npeer > 0:
                meansim = 1.0*totalsim/npeer
            else:
                meansim = 0
            print "bc: updated All I2I sim", len(torrent_sim), npref, npeer, \
                "sim:", maxsim, meansim, minsim, ngoodtorrents, "time:", time()-starttime, ctime(now())
            
        if ret:
            return torrent_sim    # for test suit
        else:
            del torrent_sim
        
    def _addPeerToDB(self, peer_permid, last_seen, peer_data):
        
        new_peer_data = {}
        try:
            new_peer_data['permid'] = peer_data['permid']
            new_peer_data['ip'] = socket.gethostbyname(peer_data['ip'])
            new_peer_data['port'] = peer_data['port']
            new_peer_data['last_seen'] = last_seen
            if peer_data.has_key('name'):
                new_peer_data['name'] = dunno2unicode(peer_data['name'])    # store in db as unicode

            exist = self.peer_db.hasPeer(peer_permid)
            self.peer_db.addPeer(peer_permid, new_peer_data, update_dns=True, updateFlag=(not exist))
            
        except KeyError:
            print_exc()
            print >> sys.stderr, "bc: _addPeerToDB has KeyError"
        except socket.gaierror:
            print >> sys.stderr, "bc: _addPeerToDB cannot find host by name", peer_data['ip']
        except:
            print_exc()

    def increaseBuddyCastTimes(self, peer_permid):
        self.peer_db.updateTimes(peer_permid, 'buddycast_times', 1)
        self.peer_db.updatePeer(peer_permid, 'last_buddycast_time', now())

    def get_dns_from_peerdb(self,permid):
        dns = (None, None)
        peer = self.peer_db.getPeer(permid)
        if peer:
            ip = self.to_real_ip(peer['ip'])
            dns = (ip, int(peer['port']))
        return dns

    def to_real_ip(self,hostname_or_ip):
        """ If it's a hostname convert it to IP address first """
        ip = None
        try:
            ip = gethostbyname(hostname_or_ip)
        except:
            pass
        return ip
    
    def addRelativeSim(self, sender_permid, peer_permid, sim, max_sim):
        # Given Sim(I, A) and Sim(A, B), predict Sim(I, B)
        # Sim(I, B) = Sim(I, A)*Sim(A, B)/Max(Sim(A,B)) for all B
        old_sim = self.getPeerSim(peer_permid, raw=True)
        if old_sim > 0:    # its similarity has been calculated based on its preferences
            return
        old_sim = abs(old_sim)
        sender_sim = self.getPeerSim(sender_permid)
        new_sim = sender_sim*sim/max_sim
        if old_sim == 0:
            peer_sim = new_sim    
        else:
            peer_sim = (new_sim + old_sim)/2
        peer_sim = -1*peer_sim
        # using negative value to indicate this sim comes from others
        self.peers[peer_permid][0] = peer_sim
        
    def get_npeers(self):
        return self.peer_db.size()
    
    def get_ntorrents(self):
        return self.torrent_db.size()
    
    def get_nmyprefs(self):
        return self.mypref_db.size()
    
    def updatePeerLevelStats(self,permid,npeers,ntorrents,nprefs):
        d = {'npeers':npeers,'ntorrents':ntorrents,'nprefs':nprefs}
        for k,v in d:
            self.peer_db.updatePeer(permid,k,v)
            