# JIE: DO I NEED TO REWRITE ALL THE DATABASE RELATED CODES?

# Written by Jie Yang
# see LICENSE.txt for license information

__fool_epydoc = 481
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
from random import sample, randint, shuffle
from time import time, gmtime, strftime
from traceback import print_exc, print_stack
from sets import Set
from array import array
from bisect import insort
from copy import deepcopy
import gc
import socket

from Tribler.Core.simpledefs import BCCOLPOLICY_SIMPLE
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.BitTornado.BT1.MessageID import BUDDYCAST, BARTERCAST, KEEP_ALIVE
from Tribler.Core.Utilities.utilities import show_permid_short, show_permid,validPermid,validIP,validPort,validInfohash,readableBuddyCastMsg, hostname_or_ip2ip
from Tribler.Core.Utilities.unicode import dunno2unicode
from Tribler.Core.simpledefs import NTFY_ACT_MEET, NTFY_ACT_RECOMMEND
from Tribler.Core.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FIRST, OLPROTO_VER_SECOND, OLPROTO_VER_THIRD, OLPROTO_VER_FOURTH, OLPROTO_VER_FIFTH, OLPROTO_VER_SIXTH, OLPROTO_VER_CURRENT, OLPROTO_VER_LOWEST
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin
from similarity import P2PSim, P2PSimSorted, P2PSimLM
from TorrentCollecting import SimpleTorrentCollecting   #, TiT4TaTTorrentCollecting
from Tribler.Core.Statistics.Logger import OverlayLogger

from threading import Event, currentThread

from bartercast import BarterCastCore

DEBUG = False   # for errors
debug = False   # for status

MAX_BUDDYCAST_LENGTH = 10*1024    # 10 KByte
REMOTE_SEARCH_PEER_NTORRENTS_THRESHOLD = 100    # speedup finding >=4.1 peers in this version

# uesed for datahandler.peers
PEER_SIM_POS = 0
PEER_LASTSEEN_POS = 1
PEER_PREF_POS = 2

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
    if not (isinstance(prefxchg['name'], str) or isinstance(prefxchg['name'], unicode)):
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
    
    def __init__(self, superpeer=False, log=''):
        if BuddyCastFactory.__single:
            raise RuntimeError, "BuddyCastFactory is singleton"
        BuddyCastFactory.__single = self 
        self.registered = False
        self.buddycast_core = None
        self.buddycast_interval = 15    # MOST IMPORTANT PARAMETER
        self.superpeer = superpeer
        self.log = log
        self.running = False
        self.data_handler = None
        self.started = False    # did call do_buddycast() at least once 
        self.max_peers = 2500   # was 2500
        if self.superpeer:
            print "Start as SuperPeer mode"
        
    def getInstance(*args, **kw):
        if BuddyCastFactory.__single is None:
            BuddyCastFactory(*args, **kw)
        return BuddyCastFactory.__single
    getInstance = staticmethod(getInstance)
    
    def register(self, overlay_bridge, launchmany, errorfunc, 
                 metadata_handler, torrent_collecting_solution, running,
                 max_peers=2500):
        if self.registered:
            return
        self.overlay_bridge = overlay_bridge
        self.launchmany = launchmany
        self.metadata_handler = metadata_handler
        self.torrent_collecting_solution = torrent_collecting_solution
        self.errorfunc = errorfunc
        
        # BuddyCast is always started, but only active when this var is set.
        self.running = bool(running)
        self.max_peers = max_peers
        
        self.registered = True

    def register2(self):
        # Arno: only start using overlay thread when normal init is finished to
        # prevent concurrencty on singletons
        if self.registered:
            if debug:
                print >> sys.stderr, "bc: Register BuddyCast", currentThread().getName()
            self.overlay_bridge.add_task(self.olthread_register, 0)

    def olthread_register(self, start=True):
    	if debug:
	        print >> sys.stderr, "bc: OlThread Register", currentThread().getName()
	        
        self.data_handler = DataHandler(self.launchmany, self.overlay_bridge, max_num_peers=self.max_peers) 
        
        # ARNOCOMMENT: get rid of this dnsindb / get_dns_from_peerdb abuse off SecureOverlay
        self.bartercast_core = BarterCastCore(self.data_handler, self.overlay_bridge, self.log, self.launchmany.secure_overlay.get_dns_from_peerdb)
            
        self.buddycast_core = BuddyCastCore(self.overlay_bridge, self.launchmany, 
               self.data_handler, self.buddycast_interval, self.superpeer,
               self.metadata_handler, self.torrent_collecting_solution, self.bartercast_core, self.log)
        
        self.data_handler.register_buddycast_core(self.buddycast_core)
        
        if start:
            self.start_time = now()
            # Arno, 2007-02-28: BC is now started self.buddycast_interval after client
            # startup. This is assumed to give enough time for UPnP to open the firewall
            # if any. So when you change this time, make sure it allows for UPnP to
            # do its thing, or add explicit coordination between UPnP and BC.
            # See BitTornado/launchmany.py
            self.overlay_bridge.add_task(self.data_handler.postInit, 1)
            self.overlay_bridge.add_task(self.doBuddyCast, 2)
            self.overlay_bridge.add_task(self.data_handler.initRemoteSearchPeers, 5)
            
            print >> sys.stderr, "BuddyCast starts up", currentThread().getName()
        
    def doBuddyCast(self):
        if not self.running:
            return
        
        if debug:
            print >>sys.stderr,"bc: doBuddyCast!", currentThread().getName()
        
        # Reschedule ourselves for next round
        buddycast_interval = self.getCurrrentInterval()
        self.overlay_bridge.add_task(self.doBuddyCast, buddycast_interval)
        if not self.started:
            self.started = True
            
        # Do our thang.
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
        
        #return 3    ### DEBUG, remove it before release!!
        
        past = now() - self.start_time
        if past < 2*60:
            if self.data_handler.get_npeers() < 20:
                interval = 2
            else:
                interval = 5
        elif past < 30*60:
            interval = 5
        elif past > 24*60*60:
            interval = 60
        else:
            interval = 15
        return interval
        
        
    def handleMessage(self, permid, selversion, message):
        
        if not self.registered or not self.running:
            if DEBUG:
                print >> sys.stderr, "bc: handleMessage got message, but we're not enabled or running"
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
                print >> sys.stderr, "bc: Received bartercast message"
            if self.bartercast_core != None:
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
        
        if DEBUG:
            print >> sys.stderr, "bc: handleConnection",exc,show_permid_short(permid),selversion,locally_initiated,currentThread().getName()

        if not self.registered:
            return
            
        if DEBUG:
            nconn = 0
            conns = self.buddycast_core.connections
            print >> sys.stderr, "\nbc: conn in buddycast", len(conns)
            for peer_permid in conns:
                _permid = show_permid_short(peer_permid)
                nconn += 1
                print >> sys.stderr, "bc: ", nconn, _permid, conns[peer_permid]
                
        if self.running or exc is not None:    # if not running, only close connection
            self.buddycast_core.handleConnection(exc,permid,selversion,locally_initiated)
    
    def addMyPref(self, torrent):
        """ Called by OverlayThread (as should be everything) """
        if self.registered:
            self.data_handler.addMyPref(torrent)
        
    def delMyPref(self, torrent):
        if self.registered:
            self.data_handler.delMyPref(torrent)
    
    
class BuddyCastCore:
    def __init__(self, overlay_bridge, launchmany, data_handler, 
                 buddycast_interval, superpeer, 
                 metadata_handler, torrent_collecting_solution, bartercast_core, log=None):
        self.overlay_bridge = overlay_bridge
        self.launchmany = launchmany
        self.data_handler = data_handler
        self.buddycast_interval = buddycast_interval
        self.superpeer = superpeer
        #print_stack()
        #print >> sys.stderr, 'debug buddycast'
        #superpeer    # change it for superpeers
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
        #self.timeout = 5*60
        self.block_interval = 4*60*60   # block interval for a peer to buddycast
        self.short_block_interval = 4*60*60    # block interval if failed to connect the peer
        self.num_myprefs = 50       # num of my preferences in buddycast msg 
        self.max_collected_torrents = 50    # num of recently collected torrents (from BuddyCast 3)
        self.num_tbs = 10           # num of taste buddies in buddycast msg 
        self.num_tb_prefs = 10      # num of taset buddy's preferences in buddycast msg 
        self.num_rps = 10           # num of random peers in buddycast msg  
        # time to check connection and send keep alive message
        #self.check_connection_round = max(1, 120/self.buddycast_interval)    
        self.max_conn_cand = 100 # max number of connection candidates
        self.max_conn_tb = 10    # max number of connectable taste buddies
        self.max_conn_rp = 10    # max number of connectable random peers
        self.max_conn_up = 10    # max number of unconnectable peers
        self.bootstrap_num = 10   # max number of peers to fill when bootstrapping
        self.bootstrap_interval = 5*60    # 5 min
        self.network_delay = self.buddycast_interval*2    # 30 seconds
        self.check_period = 120    # how many seconds to send keep alive message and check updates
        self.num_search_cand = 10 # max number of remote search peer candidates
        self.num_remote_peers_in_msg = 2 # number of remote search peers in msg
        
        # --- memory ---
        self.send_block_list = {}           # permid:unlock_time 
        self.recv_block_list = {}
        self.connections = {}               # permid: overlay_version
        self.connected_taste_buddies = []   # [permid]
        self.connected_random_peers = []    # [permid]
        self.connected_connectable_peers = {}    # permid: {'connect_time', 'ip', 'port', 'similarity', 'oversion', 'num_torrents'} 
        self.connected_unconnectable_peers = {}    # permid: connect_time
        self.connection_candidates = {}     # permid: last_seen
        self.remote_search_peer_candidates = []    # [last_seen,permid], sorted, the first one in the list is the oldest one
        
        # --- stats ---
        self.target_type = 0
        self.next_initiate = 0
        self.round = 0     # every call to work() is a round
        self.bootstrapped = False    # bootstrap once every 1 hours
        self.bootstrap_time = 0  # number of times to bootstrap
        self.total_bootstrapped_time = 0
        self.last_bootstrapped = now()    # bootstrap time of the last time
        self.start_time = now()
        self.last_check_time = 0
        
        # --- dependent modules ---
        self.metadata_handler = metadata_handler
        self.torrent_collecting = None
        if torrent_collecting_solution == BCCOLPOLICY_SIMPLE:
            self.torrent_collecting = SimpleTorrentCollecting(metadata_handler, data_handler)

        # -- misc ---
        self.dnsindb = launchmany.secure_overlay.get_dns_from_peerdb
        if self.log:
            self.overlay_log = OverlayLogger.getInstance(self.log)
            
        # Bartercast
        self.bartercast_core = bartercast_core
        #self.bartercast_core.buddycast_core = self    
        
        if self.superpeer:
            from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
            self.db_task_thread = TimedTaskQueue()  # used to delegate db tasks because superpeer has to repsonse very fast
                            
    def get_peer_info(self, target_permid, include_permid=True):
        if not target_permid:
            return ' None '
        dns = self.dnsindb(target_permid)
        if not dns:
            return ' None '
        try:
            ip = dns[0]
            port = dns[1]
            sim = self.data_handler.getPeerSim(target_permid)
            if include_permid:
                s_pid = show_permid_short(target_permid)
                return ' %s %s:%s %.3f ' % (s_pid, ip, port, sim)
            else:
                return ' %s:%s %.3f' % (ip, port, sim)
        except:
            return ' ' + repr(dns) + ' '
        
    def work(self):
        """
            The engineer of buddycast empidemic protocol.
            In every round, it selects a target and initates a buddycast exchange,
            or idels due to replying messages in the last rounds.
        """
        
        try:
            self.round += 1
            if DEBUG:
                print >> sys.stderr, 'bc: ************ working buddycast', currentThread().getName()
            self.print_debug_info('Active', 2)
            if self.log:
                nPeer, nPref, nCc, nBs, nBr, nSO, nCo, nCt, nCr, nCu = self.get_stats()
                self.overlay_log('BUCA_STA', self.round, (nPeer,nPref,nCc), (nBs,nBr), (nSO,nCo), (nCt,nCr,nCu))
        
            self.print_debug_info('Active', 3)
            #print >> sys.stderr, 'bc: ************ working buddycast 2'
            self.updateSendBlockList()
            
            _now = now()
            if _now - self.last_check_time >= self.check_period:
                self.print_debug_info('Active', 4)
                self.keepConnections()
                #self.data_handler.checkUpdate()
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
        if self.bootstrapped and _now - self.last_bootstrapped < self.bootstrap_interval:
            self.bootstrap_time = 0    # let it read the most recent peers next time
            return -1
        
        #ARNODB: self.data_handler.peers is a map from peer_id to something, i.e., not
        # permid. send_block_list is a list of permids
        send_block_list_ids = []
        for permid in self.send_block_list:
            peer_id = self.data_handler.getPeerID(permid)
            send_block_list_ids.append(peer_id)
        
        target_cands_ids = Set(self.data_handler.peers) - Set(send_block_list_ids)
        recent_peers_ids = self.selectRecentPeers(target_cands_ids, number, 
                                              startfrom=self.bootstrap_time*number)
        
        for peer_id in recent_peers_ids:
            last_seen = self.data_handler.getPeerIDLastSeen(peer_id)
            self.addConnCandidate(self.data_handler.getPeerPermid(peer_id), last_seen)
        self.limitConnCandidate()
        
        self.bootstrap_time += 1
        self.total_bootstrapped_time += 1
        self.last_bootstrapped = _now
        if len(self.connection_candidates) < self.bootstrap_num:
            self.bootstrapped = True    # don't reboot until self.bootstrap_interval later
        else:  
            self.bootstrapped = False    # reset it to allow read more peers if needed
        return 1

    def selectRecentPeers(self, cand_ids, number, startfrom=0):
        """ select a number of most recently online peers
        @return a list of peer_ids
        """
        
        if not cand_ids:
            return []
        peerids = []
        last_seens = []
        for peer_id in cand_ids:
            peerids.append(peer_id)
            last_seens.append(self.data_handler.getPeerIDLastSeen(peer_id))
        npeers = len(peerids)
        if npeers == 0:
            return []
        aux = zip(last_seens, peerids)
        aux.sort()
        aux.reverse()
        peers = []
        i = 0
        
        # roll back when startfrom is bigger than npeers
        startfrom = startfrom % npeers    
        endat = startfrom + number
        for _, peerid in aux[startfrom:endat]:
            peers.append(peerid)
        return peers
            
    def addConnCandidate(self, peer_permid, last_seen):
        """ add a peer to connection_candidates, and only keep a number of
            the most fresh peers inside.
        """
        
        if self.isBlocked(peer_permid, self.send_block_list) or peer_permid == self.permid:
            return
        self.connection_candidates[peer_permid] = last_seen
        
    def limitConnCandidate(self):
        if len(self.connection_candidates) > self.max_conn_cand:
            tmp_list = zip(self.connection_candidates.values(),self.connection_candidates.keys())
            tmp_list.sort()
            while len(self.connection_candidates) > self.max_conn_cand:
                ls,peer_permid = tmp_list.pop(0)
                self.removeConnCandidate(peer_permid)
        
    def removeConnCandidate(self, peer_permid):
        if peer_permid in self.connection_candidates:
            self.connection_candidates.pop(peer_permid)
        
    # -------------- routines in each round -------------- #
    def updateSendBlockList(self):
        """ Remove expired peers in send block list """
        
        _now = now()
        for p in self.send_block_list.keys():    # don't call isBlocked() for performance reason
            if _now >= self.send_block_list[p] - self.network_delay:
                if debug:
                    print "bc: *** unblock peer in send block list" + self.get_peer_info(p) + \
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
                self.overlay_bridge.send(peer_permid, KEEP_ALIVE+keepalive_msg, 
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
            for permid in self.connection_candidates:
                peer_id = self.data_handler.getPeerID(permid)
                if peer_id:
                    sim = self.data_handler.getPeerSim(permid)
                    max_sim = max(max_sim, (sim, permid))
            selected_permid = max_sim[1]
            if selected_permid is None:
                return None
            else:
                return selected_permid
            
        def selectRPTarget():
            # Randomly select a random peer 
            selected_permid = None
            while len(self.connection_candidates) > 0:
                selected_permid = sample(self.connection_candidates, 1)[0]
                selected_peer_id = self.data_handler.getPeerID(selected_permid)
                if selected_peer_id is None:
                    self.removeConnCandidate(selected_permid)
                    selected_permid = None
                elif selected_peer_id:
                    break
                
            return selected_permid
    
        self.target_type = 1 - self.target_type
        if self.target_type == 0:  # select a taste buddy
            target_permid = selectTBTarget()
        else:       # select a random peer
            target_permid = selectRPTarget()

        return self.target_type, target_permid
    
    # ------ start buddycast exchange ------ #
    def startBuddyCast(self, target_permid):
        """ Connect to a peer, create a buddycast message and send it """
        
        if not target_permid or target_permid == self.permid:
            return
        
        if not self.isBlocked(target_permid, self.send_block_list):
            if debug:
                print >> sys.stderr, 'bc: connect a peer', show_permid_short(target_permid), currentThread().getName()
            self.overlay_bridge.connect(target_permid, self.buddycastConnectCallback)
                        
            self.print_debug_info('Active', 12, target_permid)
            if self.log:
                dns = self.dnsindb(target_permid)
                if dns:
                    ip,port = dns
                    self.overlay_log('CONN_TRY', ip, port, show_permid(target_permid))
            
            # always block the target for a while not matter succeeded or not
            #self.blockPeer(target_permid, self.send_block_list, self.short_block_interval)
            self.print_debug_info('Active', 13, target_permid)

            # remove it from candidates no matter if it has been connected
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
                    if debug:
                        raise RuntimeError, 'buddycast: not connected while calling connect_callback'
                    return
                
                self.print_debug_info('Active', 15, target_permid, selversion)
                        
                self.createAndSendBuddyCastMessage(target_permid, selversion, active=True)

            except:
                print_exc()
                print >> sys.stderr, "bc: error in reply buddycast msg",\
                    exc, dns, show_permid_short(target_permid), selversion, "Round", self.round, 

        else:
            if debug:
                print >> sys.stderr, "bc: warning - connecting to",\
                    show_permid_short(target_permid),exc,dns, ctime(now())
                    
    def createAndSendBuddyCastMessage(self, target_permid, selversion, active):
        
        buddycast_data = self.createBuddyCastMessage(target_permid, selversion)
        if debug:
            print >> sys.stderr, "bc: createAndSendBuddyCastMessage", len(buddycast_data), currentThread().getName()
        try:
            buddycast_data['permid'] = self.permid
            validBuddyCastData(buddycast_data, self.num_myprefs, 
                                   self.num_tbs, self.num_rps, self.num_tb_prefs)
            buddycast_data.pop('permid')
            buddycast_msg = bencode(buddycast_data)
        except:
            print_exc()
            print >> sys.stderr, "error buddycast_data:", buddycast_data
            return
            
        if active:
            self.print_debug_info('Active', 16, target_permid)
        else:
            self.print_debug_info('Passive', 6, target_permid)
            
        self.overlay_bridge.send(target_permid, BUDDYCAST+buddycast_msg, self.buddycastSendCallback)
        self.blockPeer(target_permid, self.send_block_list, self.short_block_interval)
        self.removeConnCandidate(target_permid)        
        
        if debug:
            print >> sys.stderr, '****************--------------'*2
            print >> sys.stderr, 'send buddycast message to', show_permid_short(target_permid), len(buddycast_msg)
        
        if active:
            self.print_debug_info('Active', 17, target_permid)
        else:
            self.print_debug_info('Passive', 7, target_permid)

        # Bartercast
        if self.bartercast_core != None and active:
            self.bartercast_core.createAndSendBarterCastMessage(target_permid, selversion, active)

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

        peers = []
        for permid in tb_list:    
            # keys = ('ip', 'port', 'oversion', 'num_torrents')
            peer = deepcopy(self.connected_connectable_peers[permid])
            if peer['ip'] == target_ip and peer['port'] == target_port:
                continue
            peer['similarity'] = self.data_handler.getPeerSim(permid)
            peer['permid'] = permid
            peers.append(peer)
        
#        peers = self.data_handler.getPeers(tb_list, ['permid', 'ip', 'port', 'similarity', 'oversion', 'num_torrents'])
#        # filter peers with the same ip and port
#        peers = filter(lambda p:p['ip']!=target_ip or int(p['port'])!=target_port, peers)
#        
#        for i in range(len(peers)):
#            peers[i]['port'] = int(peers[i]['port'])
            
        # In overlay version 2, buddycast has 'age' field
        if selversion <= OLPROTO_VER_SECOND:
            for i in range(len(peers)):
                peers[i]['age'] = 0
            
        # In overlay version 2 and 3, buddycast doesn't have similarity field, and taste buddy has preferences
        if selversion <= OLPROTO_VER_THIRD:
            for i in range(len(peers)):
                peers[i].pop('similarity')
                peers[i]['preferences'] = []    # don't support from now on
        
        # From overlay version 4, buddycast includes similarity for peers
        if selversion >= OLPROTO_VER_FOURTH:
            for i in range(len(peers)):
                peers[i]['similarity'] = int(peers[i]['similarity']+0.5)    # bencode doesn't accept float type
        
        # Every peer >= 6 in message attachs nfiles and oversion for remote search from version 6
        for i in range(len(peers)):
            oversion = peers[i].pop('oversion')
            nfiles = peers[i].pop('num_torrents')
            if selversion >= OLPROTO_VER_SIXTH and oversion >= OLPROTO_VER_SIXTH and nfiles >= REMOTE_SEARCH_PEER_NTORRENTS_THRESHOLD:
                peers[i]['oversion'] = oversion
                # ascribe it to the inconsistent name of the same concept in msg and db
                peers[i]['nfiles'] = nfiles
        
        return peers
    
    def getRandomPeers(self, nrps, target_permid, target_ip, target_port, selversion):
        """ Randomly select a number of peers from connected_random_peers. """
        
        if not self.connected_random_peers:
            return []
        rp_list = self.connected_random_peers[:]
        
        # From version 6, two (might be offline) remote-search-peers must be included in msg
        if selversion >= OLPROTO_VER_SIXTH:
            remote_search_peers = self.getRemoteSearchPeers(self.num_remote_peers_in_msg)
            rp_list += remote_search_peers
            if len(rp_list) > nrps:
                rp_list = sample(rp_list, nrps)
            
        if target_permid in rp_list:
            rp_list.remove(target_permid)
        
        peers = []
        if DEBUG:
            print >> sys.stderr, 'bc: ******** rplist nconn', len(rp_list), len(self.connected_connectable_peers)
        #print >> sys.stderr, rp_list, self.connected_connectable_peers
        for permid in rp_list:    
            # keys = ('ip', 'port', 'oversion', 'num_torrents')
            #print >> sys.stderr, '**************', `self.connected_connectable_peers`, `rp_list`
            # TODO: Fix this bug: not consisitent
            if permid not in self.connected_connectable_peers:
                continue
            peer = deepcopy(self.connected_connectable_peers[permid])
            if peer['ip'] == target_ip and peer['port'] == target_port:
                continue
            peer['similarity'] = self.data_handler.getPeerSim(permid)
            peer['permid'] = permid
            peers.append(peer)
            
#        peers = self.data_handler.getPeers(rp_list, ['permid', 'ip', 'port', 'similarity', 'oversion', 'num_torrents'])
#        peers = filter(lambda p:p['ip']!=target_ip or int(p['port'])!=target_port, peers)
#        
#        for i in range(len(peers)):
#            peers[i]['port'] = int(peers[i]['port'])
            
        if selversion <= OLPROTO_VER_SECOND:    
            for i in range(len(peers)):
                peers[i]['age'] = 0
                
        # random peer also attachs similarity from 4
        if selversion <= OLPROTO_VER_THIRD:
            for i in range(len(peers)):
                peers[i].pop('similarity')

        if selversion >= OLPROTO_VER_FOURTH:
            for i in range(len(peers)):
                old_sim = peers[i]['similarity']
                if old_sim is None:
                    old_sim = 0.0
                peers[i]['similarity'] = int(old_sim+0.5)
        
        # Every peer >= 6 in message attachs nfiles and oversion for remote search from version 6
        for i in range(len(peers)):
            oversion = peers[i].pop('oversion')
            nfiles = peers[i].pop('num_torrents')
            # only include remote-search-peers
            if selversion >= OLPROTO_VER_SIXTH and oversion >= OLPROTO_VER_SIXTH and nfiles >= REMOTE_SEARCH_PEER_NTORRENTS_THRESHOLD:
                peers[i]['oversion'] = oversion
                # ascribe it to the inconsistent name of the same concept in msg and db
                peers[i]['nfiles'] = nfiles
  
        return peers       
    
    def isConnectable(self):
        return bool(self.dialback.isConnectable())

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
        
        peer_id = peer_permid # ARNODB: confusing!
        if block_interval is None:
            block_interval = self.block_interval
        unblock_time = now() + block_interval
        block_list[peer_id] = unblock_time
        
    def isBlocked(self, peer_permid, block_list):
        peer_id = peer_permid
        if peer_id not in block_list:
            return False
        unblock_time = block_list[peer_id]
        if now() >= unblock_time - self.network_delay:    # 30 seconds for network delay
            block_list.pop(peer_id)
            return False
        return True
            
    # ------ receive a buddycast message, for both active and passive thread ------ #
    def gotBuddyCastMessage(self, recv_msg, sender_permid, selversion):
        """ Received a buddycast message and handle it. Reply if needed """
        
        if debug:
            print >> sys.stderr, "bc: got and handle buddycast msg", currentThread().getName()
        
        if not sender_permid or sender_permid == self.permid:
            print >> sys.stderr, "bc: error - got BuddyCastMsg from a None peer", \
                        sender_permid, recv_msg, "Round", self.round
            return False
        
        blocked = self.isBlocked(sender_permid, self.recv_block_list)
        if blocked:
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
                if DEBUG:
                    print >> sys.stderr, "bc: warning, got invalid BuddyCastMsg:", errmsg, \
                    "Round", self.round   # ipv6
                return False
           
           
            # update sender's ip and port in buddycast
            dns = self.dnsindb(sender_permid)
            if dns != None:
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
            conn = buddycast_data.get('connectable', 0)    # 0 - unknown
            self.handleBuddyCastMessage(sender_permid, buddycast_data, selversion)
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
            
        except Exception, msg:
            print_exc()
            raise Exception, msg
            return True    # don't close connection, maybe my problem in handleBuddyCastMessage
        
        self.blockPeer(sender_permid, self.recv_block_list)
        
        # update torrent collecting module
        #self.data_handler.checkUpdate()
        collected_infohashes = buddycast_data.get('collected torrents', [])
        if self.torrent_collecting and not self.superpeer:
            collected_infohashes += buddycast_data.get('preferences', [])
            self.torrent_collecting.trigger(sender_permid, selversion, collected_infohashes)
        
        if active:
            self.print_debug_info('Active', 21, sender_permid)
        else:
            self.print_debug_info('Passive', 5, sender_permid)
                
        if not active:
            self.replyBuddyCast(sender_permid, selversion)    

        # show activity
        buf = dunno2unicode('"'+buddycast_data['name']+'"')
        self.launchmany.set_activity(NTFY_ACT_RECOMMEND, buf)
        
        if DEBUG:
            print >> sys.stderr, '*****************************************************************************************************'
            print >> sys.stderr, "*  bc: Got BuddyCast Message from",self.get_peer_info(sender_permid),active
            print >> sys.stderr, '******************************** Yahoo! *************************************************************'
        
        return True
        
    def handleBuddyCastMessage(self, sender_permid, buddycast_data, selversion):
        """ Handle received buddycast message 
            Add peers, torrents and preferences into database and update last seen
            Add fresh peers to candidate list
            All database updates caused by buddycast msg should be handled here 
        """
        
        _now = now()
        
        cache_db_data = {'peer':{},'infohash':Set(),'pref':[]}  # peer, updates / pref, pairs
        cache_peer_data = {}
        
        tbs = buddycast_data.pop('taste buddies')
        rps = buddycast_data.pop('random peers')
        buddycast_data['oversion'] = selversion
        
        max_tb_sim = 1
                
        # include sender itself
        bc_data = [buddycast_data] + tbs + rps 
        for peer in bc_data:
            peer_permid = peer['permid']
            if peer_permid == self.permid:
                continue 
            age = max(peer.get('age', 0), 0)    # From secure overlay version 3, it doesn't include 'age'
            last_seen = _now - age
            old_last_seen = self.data_handler.getPeerLastSeen(peer_permid)
            last_seen = min(max(old_last_seen, last_seen), _now)
            oversion = peer.get('oversion', 0)
            nfiles = peer.get('nfiles', 0)
            self.addRemoteSearchPeer(peer_permid, oversion, nfiles, last_seen)
            
            cache_peer_data[peer_permid] = {}
            cache_peer_data[peer_permid]['last_seen'] = last_seen
            #self.data_handler._addPeerToCache(peer_permid, last_seen)
            #if selversion >= OLPROTO_VER_FOURTH:
            sim = peer.get('similarity', 0)
            max_tb_sim = max(max_tb_sim, sim)
            if sim > 0:
                cache_peer_data[peer_permid]['sim'] = sim
                #self.data_handler.addRelativeSim(sender_permid, peer_permid, sim, max_tb_sim)
            
            if peer_permid != sender_permid:
                self.addConnCandidate(peer_permid, last_seen)

            new_peer_data = {}
            #new_peer_data['permid'] = peer['permid']
            new_peer_data['ip'] = hostname_or_ip2ip(peer['ip']) 
            new_peer_data['port'] = peer['port']
            new_peer_data['last_seen'] = last_seen
            if peer.has_key('name'):
                new_peer_data['name'] = dunno2unicode(peer['name'])    # store in db as unicode
            cache_db_data['peer'][peer_permid] = new_peer_data
            #self.data_handler.addPeer(peer_permid, last_seen, new_peer_data, commit=True)    # new peer

        self.limitConnCandidate()
        if len(self.connection_candidates) > self.bootstrap_num:
            self.bootstrapped = True
        
        # database stuff
        if selversion >= OLPROTO_VER_SIXTH:
            stats = {'num_peers':buddycast_data['npeers'],'num_torrents':buddycast_data['nfiles'],'num_prefs':buddycast_data['ndls']}
            cache_db_data['peer'][sender_permid].update(stats)
       
        cache_db_data['peer'][sender_permid]['last_buddycast'] = _now
        
        infohashes = Set(buddycast_data.get('collected torrents', []))
        prefs = Set(buddycast_data.get('preferences', []))  # only accept sender's preference, to avoid pollution
        infohashes = infohashes.union(prefs)
                
        cache_db_data['infohash'] = infohashes
        #self.data_handler.addInfohashes(infohashes, commit=True)
        if prefs:
            cache_db_data['pref'] = prefs
            #self.data_handler.addPeerPreferences(sender_permid, prefs)
        #self.data_handler.increaseBuddyCastTimes(sender_permid, commit=True)
        
        if self.superpeer:
            self.db_task_thread.add_task(lambda :
                        self.data_handler.handleBCData(cache_db_data, cache_peer_data, sender_permid, max_tb_sim))
        else:
            self.data_handler.handleBCData(cache_db_data, cache_peer_data, sender_permid, max_tb_sim)
        
    def removeFromConnList(self, peer_permid):
        removed = 0
        if peer_permid in self.connected_connectable_peers:     # Ct
            self.connected_connectable_peers.pop(peer_permid)
            try:
                self.connected_taste_buddies.remove(peer_permid)
            except ValueError:
                pass
            try:
                self.connected_random_peers.remove(peer_permid)
            except ValueError:
                pass
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
            #print >> sys.stderr, "bc: cannot add a unconnected peer to conn list", "Round", self.round
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
        for permid in self.connected_connectable_peers:
            sim = self.data_handler.getPeerSim(permid)
            if sim > 0:
                tmplist.append([sim, permid])
            else:
                rps.append(permid)
        tmplist.sort()
        tmplist.reverse()
        
        #ntb = self.max_conn_tb    # 10 tb & 10 rp
        ntb = min((nconnpeers+1)/2, self.max_conn_tb)    # half tb and half rp
        if len(tmplist) > 0:
            for sim,permid in tmplist[:ntb]:
                tbs.append(permid)
        ntb = len(tbs)
        if len(tmplist) > ntb:
            rps = [permid for sim,permid in tmplist[ntb:]] + rps
        
        # remove the oldest peer from both random peer list and connected_connectable_peers
        if len(rps) > self.max_conn_rp:
            tmplist = []
            for permid in rps:
                connect_time = self.connected_connectable_peers[permid]['connect_time']
                tmplist.append([connect_time, permid])
            tmplist.sort()
            tmplist.reverse()
            rps = []
            i = 0
            for last_seen,permid in tmplist:
                if i < self.max_conn_rp:
                    rps.append(permid)
                else:
                    self.connected_connectable_peers.pop(permid)
                i += 1
            
        self.connected_taste_buddies = tbs
        self.connected_random_peers = rps
        
        for p in self.connected_taste_buddies:
            assert p in self.connected_connectable_peers
        for p in self.connected_random_peers:
            assert p in self.connected_connectable_peers
        assert len(self.connected_taste_buddies) + len(self.connected_random_peers) <= len(self.connected_connectable_peers)
        
            
    def addPeerToConnCP(self, peer_permid, conn_time):
        keys = ('ip', 'port', 'oversion', 'num_torrents')
        res = self.data_handler.getPeer(peer_permid, keys)
        peer = dict(zip(keys,res))
        peer['connect_time'] = conn_time
        self.connected_connectable_peers[peer_permid] = peer
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
        
        #print >> sys.stderr, '*************** replay buddycast message', show_permid_short(target_permid), self.isConnected(target_permid)
        
        if not self.isConnected(target_permid):
            #print >> sys.stderr, 'buddycast: lost connection while replying buddycast', \
            #    "Round", self.round
            return
        
        self.createAndSendBuddyCastMessage(target_permid, selversion, active=False)
        
        self.print_debug_info('Passive', 8, target_permid)
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
            print >> sys.stderr, "bc: handle conn from overlay", exc, \
                self.get_peer_info(permid), "selversion:", selversion, \
                "local_init:", locally_initiated, ctime(now())
        
    def addConnection(self, peer_permid, selversion, locally_initiated):
        # add connection to connection list
        _now = now()
        if DEBUG:
            print >> sys.stderr, "bc: addConnection", self.isConnected(peer_permid)
        if not self.isConnected(peer_permid):
            # SecureOverlay has already added the peer to db
            self.connections[peer_permid] = selversion # add a new connection
            addto = self.addPeerToConnList(peer_permid, locally_initiated)
            
            dns = self.get_peer_info(peer_permid, include_permid=False)
            buf = '%s %s'%(dns, addto)
            self.launchmany.set_activity(NTFY_ACT_MEET, buf)    # notify user interface

            if self.torrent_collecting and not self.superpeer:
                self.torrent_collecting.trigger(peer_permid, selversion)

            if debug:
                print >> sys.stderr, "bc: add connection", \
                    self.get_peer_info(peer_permid), "to", addto
            if self.log:
                dns = self.dnsindb(peer_permid)
                if dns:
                    ip,port = dns
                    self.overlay_log('CONN_ADD', ip, port, show_permid(peer_permid), selversion)

    def closeConnection(self, peer_permid, reason):
        """ Close connection with a peer, and remove it from connection lists """
        
        if debug:
            print >> sys.stderr, "bc: close connection:", self.get_peer_info(peer_permid)
        
        if self.isConnected(peer_permid):
            self.connections.pop(peer_permid)
        removed = self.removeFromConnList(peer_permid)
        if removed == 1:
            self.updateTBandRPList()
        
        if self.log:
            dns = self.dnsindb(peer_permid)
            if dns:
                ip,port = dns
                self.overlay_log('CONN_DEL', ip, port, show_permid(peer_permid), reason)

    # -------------- print debug info ---------- #
    def get_stats(self):
        nPeer = len(self.data_handler.peers)
        nPref = nPeer #len(self.data_handler.preferences)
        nCc = len(self.connection_candidates)
        nBs = len(self.send_block_list)
        nBr = len(self.recv_block_list)
        nSO = -1 # TEMP ARNO len(self.overlay_bridge.debug_get_live_connections())
        nCo = len(self.connections)
        nCt = len(self.connected_taste_buddies)
        nCr = len(self.connected_random_peers)
        nCu = len(self.connected_unconnectable_peers)
        return nPeer, nPref, nCc, nBs, nBr, nSO, nCo, nCt, nCr, nCu
    
    def print_debug_info(self, thread, step, target_permid=None, selversion=0, r=0, addto=''):
        if not debug:
            return
        if DEBUG:
            print "bc: *****", thread, str(step), "-",
        if thread == 'Active':
            if step == 2:
                print >> sys.stderr, "Working:", now() - self.start_time, \
                    "seconds since start. Round", self.round, "Time:", ctime(now())
                nPeer, nPref, nCc, nBs, nBr, nSO, nCo, nCt, nCr, nCu = self.get_stats()
                print >> sys.stderr, "bc: *** Status: nPeer nPref nCc: %d %d %d  nBs nBr: %d %d  nSO nCo nCt nCr nCu: %d %d %d %d %d" % \
                                      (nPeer,nPref,nCc,           nBs,nBr,        nSO,nCo, nCt,nCr,nCu)
                if nSO != nCo:
                    print >> sys.stderr, "bc: warning - nSo and nCo is inconsistent"
                if nCc > self.max_conn_cand or nCt > self.max_conn_tb or nCr > self.max_conn_rp or nCu > self.max_conn_up:
                    print >> sys.stderr, "bc: warning - nCC or nCt or nCr or nCu overloads"
                _now = now()
                buf = ""
                i = 1
                for p in self.connected_taste_buddies:
                    buf += "bc: %d taste buddies: "%i + self.get_peer_info(p) + str(_now-self.connected_connectable_peers[p]['connect_time']) + " version: " + str(self.connections[p]) + "\n"
                    i += 1
                print >> sys.stderr, buf
                
                buf = ""
                i = 1
                for p in self.connected_random_peers:
                    buf += "bc: %d random peers: "%i + self.get_peer_info(p) + str(_now-self.connected_connectable_peers[p]['connect_time']) + " version: " + str(self.connections[p]) + "\n"
                    i += 1
                print >> sys.stderr, buf
                
                buf = ""
                i = 1
                for p in self.connected_unconnectable_peers:
                    buf += "bc: %d unconnectable peers: "%i + self.get_peer_info(p) + str(_now-self.connected_unconnectable_peers[p]) + " version: " + str(self.connections[p]) + "\n"
                    i += 1
                print >> sys.stderr, buf
                buf = ""
                totalsim = 0
                nsimpeers = 0
                minsim = 1e10
                maxsim = 0
                sims = []
                for p in self.data_handler.peers:
                    sim = self.data_handler.peers[p][PEER_SIM_POS]
                    if sim > 0:
                        sims.append(sim)
                if sims:
                    minsim = min(sims)
                    maxsim = max(sims)
                    nsimpeers = len(sims)
                    totalsim = sum(sims)
                    if nsimpeers > 0:
                        meansim = totalsim/nsimpeers
                    else:
                        meansim = 0
                    print >> sys.stderr, "bc: * sim peer: %d %.3f %.3f %.3f %.3f\n" % (nsimpeers, totalsim, meansim, minsim, maxsim)

            elif step == 3:
                print >> sys.stderr, "check blocked peers: Round", self.round
                
            elif step == 4:
                print >> sys.stderr, "keep connections with peers: Round", self.round
                
            elif step == 6:
                print >> sys.stderr, "idle loop:", self.next_initiate
                
            elif step == 9: 
                print >> sys.stderr, "bootstrapping: select", self.bootstrap_num, \
                    "peers recently seen from Mega Cache"
                if self.booted < 0:
                    print >> sys.stderr, "bc: *** bootstrapped recently, so wait for a while"
                elif self.booted == 0:
                    print >> sys.stderr, "bc: *** no peers to bootstrap. Try next time"
                else:
                    print >> sys.stderr, "bc: *** bootstrapped, got", len(self.connection_candidates), \
                      "peers in Cc. Times of bootstrapped", self.total_bootstrapped_time
                    buf = ""
                    for p in self.connection_candidates:
                        buf += "bc: * cand:" + str(p) + "\n"
                    buf += "\nbc: Remote Search Peer Candidates:\n"
                    for p in self.remote_search_peer_candidates:
                        buf += "bc: * remote: %d "%p[0] + self.get_peer_info(p[1]) + "\n"
                    print >> sys.stderr, buf
            
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
                print >> sys.stderr, buf

            elif step == 12:
                print >> sys.stderr, "connect a peer to start buddycast", self.get_peer_info(target_permid)
                
            elif step == 13:
                print >> sys.stderr, "block connected peer in send block list", \
                    self.get_peer_info(target_permid)#, self.send_block_list[target_permid]
                    
            elif step == 14:
                print >> sys.stderr, "remove connected peer from Cc", \
                    self.get_peer_info(target_permid)#, "removed?", target_permid not in self.connection_candidates

            elif step == 15:
                print >> sys.stderr, "peer is connected", \
                    self.get_peer_info(target_permid), "overlay version", selversion, currentThread().getName()
                
            elif step == 16:
                print >> sys.stderr, "create buddycast to send to", self.get_peer_info(target_permid)
                
            elif step == 17:
                print >> sys.stderr, "send buddycast msg to", self.get_peer_info(target_permid)
                
            elif step == 18:
                print >> sys.stderr, "receive buddycast message from peer %s" % self.get_peer_info(target_permid)
                
            elif step == 19:
                print >> sys.stderr, "store peers from incoming msg to cache and db"
                
            elif step == 20:
                print >> sys.stderr, "add connected peer %s to connection list %s" % (self.get_peer_info(target_permid), addto)
                
            elif step == 21:
                print >> sys.stderr, "block connected peer in recv block list", \
                    self.get_peer_info(target_permid), self.recv_block_list[target_permid]
                
        if thread == 'Passive': 
            if step == 2:
                print >> sys.stderr,  "receive buddycast message from peer %s" % self.get_peer_info(target_permid)
                
            elif step == 3:
                print >> sys.stderr, "store peers from incoming msg to cache and db"
                
            elif step == 4:
                print >> sys.stderr, "add connected peer %s to connection list %s" % (self.get_peer_info(target_permid), addto)
        
            elif step == 5:
                print >> sys.stderr, "block connected peer in recv block list", \
                    self.get_peer_info(target_permid), self.recv_block_list[target_permid]
            
            elif step == 6:
                print >> sys.stderr, "create buddycast to reply to", self.get_peer_info(target_permid)
            
            elif step == 7:
                print >> sys.stderr, "reply buddycast msg to", self.get_peer_info(target_permid)
                
            elif step == 8:
                print >> sys.stderr, "block connected peer in send block list", \
                    self.get_peer_info(target_permid), self.send_block_list[target_permid]
        
            elif step == 9:
                print >> sys.stderr, "remove connected peer from Cc", \
                    self.get_peer_info(target_permid)#, "removed?", target_permid not in self.connection_candidates

            elif step == 10:
                print >> sys.stderr, "add idle loops", self.next_initiate
        sys.stdout.flush()
        sys.stderr.flush()
        if DEBUG:
            print >> sys.stderr, "bc: *****", thread, str(step), "-",

    def getAllTasteBuddies(self):
        return self.connected_taste_buddies
        
    def addRemoteSearchPeer(self, permid, oversion, ntorrents, last_seen):
        if oversion >= OLPROTO_VER_SIXTH and ntorrents >= REMOTE_SEARCH_PEER_NTORRENTS_THRESHOLD:
            insort(self.remote_search_peer_candidates, [last_seen,permid])
            if len(self.remote_search_peer_candidates) > self.num_search_cand:
                self.remote_search_peer_candidates.pop(0)
                
    def getRemoteSearchPeers(self, npeers):
        if len(self.remote_search_peer_candidates) > npeers:
            _peers = sample(self.remote_search_peer_candidates, npeers)    # randomly select
        else:
            _peers = self.remote_search_peer_candidates
        peers = [permid for last_seen,permid in _peers]
        return peers
        
        
class DataHandler:
    def __init__(self, launchmany, overlay_bridge, max_num_peers=2500):
        self.launchmany = launchmany
        self.overlay_bridge = overlay_bridge
        self.config = self.launchmany.session.sessconfig # should be safe at startup
        # --- database handlers ---
        self.peer_db = launchmany.peer_db
        self.superpeer_db = launchmany.superpeer_db
        self.torrent_db = launchmany.torrent_db
        self.mypref_db = launchmany.mypref_db
        self.pref_db = launchmany.pref_db
        self.friend_db = launchmany.friend_db
        self.myfriends = Set() # FIXME: implement friends
        self.myprefs = []    # torrent ids
        self.peers = {}    # peer_id: [similarity, last_seen, prefs(array('l',[torrent_id])] 
        self.default_peer = [0, 0, None]
        self.owners = {}    # torrent_ids_of_mine: Set(peer_id)
        self.permid = self.getMyPermid()
        self.nprefs = 0
        self.ntorrents = 0
        self.last_check_ntorrents = 0
        #self.total_pref_changed = 0
        # how many peers to load into cache from db
        #self.max_peer_in_db = max_num_peers
        self.max_num_peers = min(max(max_num_peers, 100), 2500)    # at least 100, at most 2500
        #self.time_sim_weight = 4*60*60  # every 4 hours equals to a point of similarity
        # after added some many (user, item) pairs, update sim of item to item
        #self.update_i2i_threshold = 100
        #self.npeers = self.peer_db.size() - self.superpeer_db.size()
        self.old_peer_num = 0
        self.buddycast_core = None
        self.all_peer_list = None
        self.num_peers_ui = None
        self.num_torrents_ui = None
        self.cached_updates = {'peer':{},'torrent':{}}
            
    def commit(self):
        self.peer_db.commit()

    def register_buddycast_core(self, buddycast_core):
        self.buddycast_core = buddycast_core
    
    def getMyName(self, name=''):
        return self.config.get('nickname', name)
        
    def getMyIp(self, ip=''):
        return self.launchmany.get_ext_ip()
    
    def getMyPort(self, port=0):
        return self.launchmany.listen_port
    
    def getMyPermid(self, permid=''):
        return self.launchmany.session.get_permid()
  
    def getPeerID(self, permid):
        if isinstance(permid, int) and permid > 0:
            return permid
        else:
            return self.peer_db.getPeerID(permid)
    
    def getTorrentID(self, infohash):
        if isinstance(infohash, int) and infohash > 0:
            return infohash
        else:
            return self.peer_db.getPeerID(permid)
    
    def getPeerPermid(self, peer_id):
        return self.peer_db.getPermid(peer_id)
    
    def updatePort(self, port):
        self.my_db.put('port', port)
  
    def postInit(self, delay=4, batch=50, update_interval=10, npeers=None, updatesim=True):
        # build up a cache layer between app and db
        if npeers is None:
            npeers = self.max_num_peers
        self.updateMyPreferences()
        self.loadAllPeers(npeers)
        if updatesim:
            self.updateAllSim(delay, batch, update_interval)

    def updateMyPreferences(self, num_pref=None):
        # get most recent preferences, and sort by torrent id
        res = self.mypref_db.getAll('torrent_id', order_by='creation_time desc', limit=num_pref)
        self.myprefs = [p[0] for p in res]
        
        for torrent_id in self.myprefs:
            self.updateOwners(torrent_id)
            
    def updateOwners(self, torrent_id):
        res = self.pref_db.getAll('peer_id', where='torrent_id=%d'%torrent_id)
        self.owners[torrent_id] = Set([p[0] for p in res])
                
    def loadAllPeers(self, num_peers=None):
        """ Read peers from db and put them in self.peers.
            At most num_peers (=self.max_num_peers) recently seen peers can be cached.
            
        """
        peer_values = self.peer_db.getAll(['peer_id','similarity','last_seen'], order_by='last_connected desc', limit=num_peers)
        self.peers = dict(zip([p[0] for p in peer_values], [[p[1],p[2],array('l', [])] for p in peer_values])) 

        user_item_pairs = self.pref_db.getRecentPeersPrefs('last_connected',num_peers)
        self.nprefs = len(user_item_pairs)

        for pid,tid in user_item_pairs:
            self.peers[pid][PEER_PREF_POS].append(tid)

        #print >> sys.stderr, '**************** loadAllPeers', len(self.peers)

#        for pid in self.peers:
#            self.peers[pid][PEER_PREF_POS].sort()    # keep in order

    def updateAllSim(self, delay=4, batch=50, update_interval=10):
        self._updateAllPeerSim(delay, batch, update_interval)    # 0.156 second
        self._updateAllItemRel(delay, batch, update_interval)    # 0.875 second
        # Tuning batch (without index relevance)
        
        # batch = 25:                             0.00 0.22 0.58
        # batch = 50: min/avg/max execution time: 0.09 0.29 0.63 second 
        # batch = 100:                            0.16 0.47 0.95
        # update_interval=10
        # 50000 updates take: 50000 / 50 * (10+0.3) / 3600 = 3 hours
        # cpu load: 0.3/10 = 3%
        
        # With index relevance:
        # batch = 50: min/avg/max execution time: 0.08 0.62 1.39 second
        # batch = 25:                             0.00 0.41 1.67
        # update_interval=5, batch=25
        # 50000 updates take: 50000 / 25 * (5+0.4) / 3600 = 3 hours
        # cpu load: 0.4/5 = 8%
        
    def cacheSimUpdates(self, update_table, updates, delay, batch, update_interval):
        self.cached_updates[update_table].update(updates)
        self.overlay_bridge.add_task(lambda:self.checkSimUpdates(batch, update_interval), delay, 'checkSimUpdates')
        
    def checkSimUpdates(self, batch, update_interval):
        last_update = 0
        if self.cached_updates['peer']:
            updates = []
            update_peers = self.cached_updates['peer']
            keys = update_peers.keys()
            shuffle(keys)   # to avoid always update the same items when cacheSimUpdates is called frequently
            for key in keys[:batch]:
                updates.append((update_peers.pop(key), key))
            self.overlay_bridge.add_task(lambda:self.peer_db.updatePeerSims(updates), last_update + update_interval, 'updatePeerSims')
            last_update += update_interval 
            
        if self.cached_updates['torrent']:
            updates = []
            update_peers = self.cached_updates['torrent'] 
            keys = update_peers.keys()
            shuffle(keys)   
            for key in keys[:batch]:
                updates.append((update_peers.pop(key), key))
            self.overlay_bridge.add_task(lambda:self.torrent_db.updateTorrentRelevances(updates), last_update + update_interval, 'updateTorrentRelevances')
            last_update += update_interval
            
        if self.cached_updates['peer'] or self.cached_updates['torrent']:
            self.overlay_bridge.add_task(lambda:self.checkSimUpdates(batch, update_interval), last_update+0.001, 'checkSimUpdates')
        
    def _updateAllPeerSim(self, delay, batch, update_interval):
        # update similarity to all peers to keep consistent

        if self.old_peer_num == len(self.peers):    # if no new peers, don't update
            return
        starttime = time()
        self.nprefs = 0    # total nprefs must be updated before compute similarity
        for peer_id in self.peers:
            self.nprefs += len(self.peers[peer_id][PEER_PREF_POS])
            
        updates = {}
        for peer_id in self.peers:
            oldsim = self.peers[peer_id][PEER_SIM_POS]
            if not self.peers[peer_id][PEER_PREF_POS]:
                continue
            self.updateSimilarity(peer_id, False)
            sim = self.peers[peer_id][PEER_SIM_POS]
            if abs(sim - oldsim) > oldsim*0.05:
                updates[peer_id] = sim

        #print >> sys.stderr, '****************** update peer sim', len(updates), len(self.peers)        
        if updates:
            self.cacheSimUpdates('peer', updates, delay, batch, update_interval)
                        
    def _updateAllItemRel(self, delay, batch, update_interval):
        # update all item's relevance
        # Relevance of I = Sum(Sim(Users who have I)) + Poplarity(I)
        # warning: this function may take 5 seconds to commit to the database
        if len(self.peers) == 0:
            return
        tids = {}
        nsimpeers = 0
        for peer_id in self.peers:
            if self.peers[peer_id][PEER_PREF_POS]:
                sim = self.peers[peer_id][PEER_SIM_POS]
                if sim > 0:
                    nsimpeers += 1
                    prefs = self.peers[peer_id][PEER_PREF_POS]
                    for tid in prefs:
                        if tid not in tids:
                            tids[tid] = [0,0]
                        tids[tid][0] += sim
                        tids[tid][1] += 1

        if len(tids) == 1:
            return
        
        res = self.torrent_db.getTorrentRelevances(tids)
        if res:
            old_rels = dict(res)
        else:
            old_rels = {}
        #print >> sys.stderr, '********* update all item rel', len(old_rels), len(tids) #, old_rels[:10]
        
        for tid in tids.keys():
            tids[tid] = tids[tid][0]/tids[tid][1] + tids[tid][1]
            old_rel = old_rels.get(tid, None)
            if old_rel != None and abs(old_rel - tids[tid]) <= old_rel*0.05:
                tids.pop(tid)   # don't update db
            
        #print >> sys.stderr, '**************--- update all item rel', len(tids), len(old_rels) #, len(self.peers), nsimpeers, tids.items()[:10]  # 37307 2500
        if tids:
            self.cacheSimUpdates('torrent', tids, delay, batch, update_interval)

    def addMyPref(self, infohash):
        infohash_str=bin2str(infohash)
        torrentdata = self.torrent_db.getOne(('secret', 'torrent_id'), infohash=infohash_str)
        if not torrentdata:
            return
        
        secret = torrentdata[0]
        torrent_id = torrentdata[1]
        if secret:
            if DEBUG:
                print >> sys.stderr, 'Omitting secret download: %s' % torrentdata.get('info', {}).get('name', 'unknown')
            return # do not buddycast secret downloads
        
        if torrent_id not in self.myprefs:
            insort(self.myprefs, torrent_id)
            self.updateOwners(torrent_id)
            self.old_peer_num = 0
            self.updateAllSim() # time-consuming
            #self.total_pref_changed += self.update_i2i_threshold
            
    def delMyPref(self, infohash):
        """ Arno: unused at the moment """
        torrent_id = self.torrent_db.getTorrentID(infohash)
        if torrent_id in self.myprefs:
            self.myprefs.remove(torrent_id)
            self.owners.pop(torrent_id)
            self.old_peer_num = 0
            self.updateAllSim()
            #self.total_pref_changed += self.update_i2i_threshold

    def initRemoteSearchPeers(self, num_peers=10):
        peer_values = self.peer_db.getAll(['permid','oversion','num_torrents','last_seen'], order_by='last_seen desc', limit=num_peers)
        for p in peer_values:
            p = list(p)
            p[0] = str2bin(p[0])
            self.buddycast_core.addRemoteSearchPeer(*tuple(p))
        pass
    
#===============================================================================
#    def getAllPeerPermids(self, cached_peers=True):
#        """ Get a number of peers from self.peers """
# 
#        if cached_peers:    # use the cached peers
#            peerids = self.peers.keys()
#            permids = self.peer_db.getPeerList(peerids)
#        else:
#            permids = self.peer_db.getPeerList()
#        return permids
#===============================================================================
    
#    def remove_overhead_peers(self, peers2del):
#        for peer in peers2del:
#            self.peer_db.deletePeer(peer, updateFlag=False)     # friends will not be deleted
    
#    def getPeers(self, peer_list, keys):
#        return self.peer_db.getPeers(peer_list, keys)
        
    def updatePeerPref(self, peer_permid, cur_prefs):
        peer_id = self.getPeerID(peer_permid)
        cur_prefs_array = array('l', cur_prefs)
        self.peers[peer_id][PEER_PREF_POS] = cur_prefs_array
            
        overlap = Set(self.owners).intersection(Set(self.peers[peer_id][PEER_PREF_POS]))
        if len(overlap) > 0:
            for torrent_id in overlap:
                self.owners[torrent_id].add(peer_id)
    
    def getMyLivePreferences(self, num=0):
        """ Get a number of my preferences. Get all if num==0 """
        
        return self.mypref_db.getRecentLivePrefList(num)
        
    def getPeerSim(self, peer_permid, read_db=False, raw=False):
        if read_db:
            sim = self.peer_db.getPeerSim(peer_permid)
        else:            
            peer_id = self.getPeerID(peer_permid)
            if peer_id is None or peer_id not in self.peers:
                sim = 0
            else:
                sim = self.peers[peer_id][PEER_SIM_POS]
        if sim is None:
            sim = 0
        if not raw:    
            # negative value means it is calculated from other peers, 
            # not itself. See addRelativeSim()
            return abs(sim)
        else:
            return sim
        
    def getPeerLastSeen(self, peer_permid):
        peer_id = self.getPeerID(peer_permid)
        return self.getPeerIDLastSeen(peer_id)
        
    def getPeerIDLastSeen(self, peer_id):
        if not peer_id or peer_id not in self.peers:
            return 0
        #print >> sys.stderr, '***** getPeerLastSeen', self.peers[pefer_permid], `peer_permid`
        return self.peers[peer_id][PEER_LASTSEEN_POS]
    
    def getPeerPrefList(self, peer_permid):
        """ Get a number of peer's preference list. Get all if num==0.
            If live==True, dead torrents won't include
        """
        peer_id = self.getPeerID(peer_permid)
        if peer_id not in self.peers:
            return self.pref_db.getPrefList(peer_permid)
        else:
            return self.peers[peer_id][PEER_PREF_POS]
    
#    def addPeer(self, peer_permid, last_seen, peer_data=None, commit=True):  
#        """ add a peer from buddycast message to both cache and db """
#        
#        if peer_permid != self.permid:
#            if peer_data is not None:
#                self._addPeerToDB(peer_permid, last_seen, peer_data, commit=commit)
#            self._addPeerToCache(peer_permid, last_seen)    

    def _addPeerToCache(self, peer_permid, last_seen):
        """ add a peer to cache """
        # Secure Overlay should have added this peer to database.
        if peer_permid == self.permid:
            return
        peer_id = self.getPeerID(peer_permid)
        assert peer_id != None, `peer_permid`
        if peer_id not in self.peers:
            sim = self.peer_db.getPeerSim(peer_permid)
            peerprefs = self.pref_db.getPrefList(peer_permid)    # [torrent_id]
            self.peers[peer_id] = [last_seen, sim, array('l', peerprefs)]    # last_seen, similarity, pref
        else:
            self.peers[peer_id][PEER_LASTSEEN_POS] = last_seen
                    
    def _addPeerToDB(self, peer_permid, peer_data, commit=True):
        
        if peer_permid == self.permid:
            return
        new_peer_data = {}
        try:
            new_peer_data['permid'] = peer_data['permid']
            new_peer_data['ip'] = hostname_or_ip2ip(peer_data['ip'])
            new_peer_data['port'] = peer_data['port']
            new_peer_data['last_seen'] = peer_data['last_seen']
            if peer_data.has_key('name'):
                new_peer_data['name'] = dunno2unicode(peer_data['name'])    # store in db as unicode

            self.peer_db.addPeer(peer_permid, new_peer_data, update_dns=True, commit=commit)
            
        except KeyError:
            print_exc()
            print >> sys.stderr, "bc: _addPeerToDB has KeyError"
        except socket.gaierror:
            print >> sys.stderr, "bc: _addPeerToDB cannot find host by name", peer_data['ip']
        except:
            print_exc()
            
    def addInfohashes(self, infohash_list, commit=True):
        for infohash in infohash_list:
            self.torrent_db.addInfohash(infohash, commit=False)    # it the infohash already exists, it will skip it
        if commit:
            self.torrent_db.commit()
                
    def addPeerPreferences(self, peer_permid, prefs, commit=True):
        """ add a peer's preferences to both cache and db """
        
        if peer_permid == self.permid:
            return 0
        
        cur_prefs = self.getPeerPrefList(peer_permid)
        if not cur_prefs:
            cur_prefs = []
        prefs2add = []
        for infohash in prefs:
            torrent_id = self.torrent_db.getTorrentID(infohash)
            if not torrent_id:
                print >> sys.stderr, "buddycast: DB Warning: infohash", bin2str(infohash), "should have been inserted into db, but was not found"
                continue
            if torrent_id not in cur_prefs:
                prefs2add.append(torrent_id)
                cur_prefs.append(torrent_id)
        if len(prefs2add) > 0:
            self.pref_db.addPreferences(peer_permid, prefs2add, is_torrent_id=True, commit=commit)
            self.updatePeerPref(peer_permid, cur_prefs)
            self.nprefs += len(prefs2add)
            peer_id = self.getPeerID(peer_permid)
            self.updateSimilarity(peer_id, commit=commit)
            
    def updateSimilarity(self, peer_id, update_db=True, commit=True):
        """ update a peer's similarity """
        
        if len(self.myprefs) == 0:
            return
        sim = self.LMP2PSimilarity(peer_id)
        self.peers[peer_id][PEER_SIM_POS] = sim
        if update_db and sim>0:
            self.peer_db.updatePeerSims([(sim,peer_id)], commit=commit)

    def LMP2PSimilarity(self, peer_id):
        peer_pref = self.peers[peer_id][PEER_PREF_POS]
        sim = P2PSimLM(peer_id, self.myprefs, peer_pref, self.owners, self.nprefs, mu=1.0)
        return sim
    
#    def increaseBuddyCastTimes(self, peer_permid, commit=True):
#        self.peer_db.updateTimes(peer_permid, 'buddycast_times', 1, commit=False)
#        self.peer_db.updatePeer(peer_permid, commit=commit, last_buddycast=now())

    def getPeer(self, permid, keys=None):
        return self.peer_db.getPeer(permid, keys)

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
        peer_id = self.getPeerID(peer_permid)
        self.peers[peer_id][PEER_SIM_POS] = peer_sim
        
    def get_npeers(self):
        if self.num_peers_ui is None:
            return len(self.peers)    # changed to this according to Maarten's suggestion
        else:
            return self.num_peers_ui

    def get_ntorrents(self):
        if self.num_torrents_ui is None:
            _now = now()
            if _now - self.last_check_ntorrents > 5*60:
                self.ntorrents = self.torrent_db.getNumberCollectedTorrents()
                self.last_check_ntorrents = _now
            return self.ntorrents
        else:
            return self.num_torrents_ui
        
    def get_nmyprefs(self):
        return len(self.myprefs)
    
#    def updatePeerLevelStats(self,permid,npeers,ntorrents,nprefs,commit=True):
#        d = {'num_peers':npeers,'num_torrents':ntorrents,'num_prefs':nprefs}
#        self.peer_db.updatePeer(permid, commit=commit, **d)
        
#    def getAllPeerList(self):
#        return self.all_peer_list
#    
#    def removeAllPeerList(self):
#        self.all_peer_list = None
#        
#    def setNumPeersFromUI(self, num):
#        self.num_peers_ui = num
#        
#    def setNumTorrentsFromUI(self, num):    # not thread safe
#        self.num_torrents_ui = num
    
    def handleBCData(self, cache_db_data, cache_peer_data, sender_permid, max_tb_sim):
        #self.data_handler.addPeer(peer_permid, last_seen, new_peer_data, commit=True)    # new peer
        #self.data_handler.increaseBuddyCastTimes(sender_permid, commit=True)
        #self.data_handler.addInfohashes(infohashes, commit=True)
        
        #self.data_handler._addPeerToCache(peer_permid, last_seen)
        #self.data_handler.addRelativeSim(sender_permid, peer_permid, sim, max_tb_sim)
        
        #self.data_handler.addPeerPreferences(sender_permid, prefs)

        #print >>sys.stderr,"bc: handleBCData:",`cache_db_data`

        ADD_PEER = 1
        UPDATE_PEER = 2
        ADD_INFOHASH = 3
        
        peer_data = cache_db_data['peer']
        db_writes = []
        for permid in peer_data:
            new_peer = peer_data[permid]
            old_peer = self.peer_db.getPeer(permid)
            if not old_peer:
                if permid == sender_permid:
                    new_peer['buddycast_times'] = 1
                db_writes.append((ADD_PEER, permid, new_peer))
            else:
                #print old_peer
                old_last_seen = old_peer['last_seen']
                new_last_seen = new_peer['last_seen']
                if permid == sender_permid:
                    if not old_peer['buddycast_times']:
                        new_peer['buddycast_times'] = 1
                    else:
                        new_peer['buddycast_times'] =  + 1
                if not old_last_seen or new_last_seen > old_last_seen + 4*60*60:
                    # don't update if it was updated in 4 hours
                    for k in new_peer.keys():
                        if old_peer[k] == new_peer[k]:
                            new_peer.pop(k)
                if new_peer:
                    db_writes.append((UPDATE_PEER, permid, new_peer))
                
        for infohash in cache_db_data['infohash']:
            tid = self.torrent_db.getTorrentID(infohash)
            if tid is None:
                db_writes.append((ADD_INFOHASH, infohash))

        for item in db_writes:
            if item[0] == ADD_PEER:
                permid = item[1]
                new_peer = item[2]
                # Arno, 2008-09-17: Don't use IP data from BC message, network info gets precedence
                updateDNS = (permid != sender_permid)
                self.peer_db.addPeer(permid, new_peer, update_dns=updateDNS, commit=False)
            elif item[0] == UPDATE_PEER:
                permid = item[1]
                new_peer = item[2]
                # Arno, 2008-09-17: Don't use IP data from BC message, network info gets precedence
                updateDNS = (permid != sender_permid)
                if not updateDNS:
                    if 'ip' in new_peer:
                        del new_peer['ip']
                    if 'port' in new_peer:
                        del new_peer['port']
                self.peer_db.updatePeer(permid, commit=False, **new_peer)
            elif item[0] == ADD_INFOHASH:
                infohash = item[1]
                self.torrent_db.addInfohash(infohash, commit=False)
                
        #self.torrent_db._db.show_sql(1)
        self.torrent_db.commit()
        #self.torrent_db._db.show_sql(0)
                
        for item in db_writes:
            if item[0] == ADD_PEER or item[0] == UPDATE_PEER:
                permid = item[1]
                new_peer = item[2]
                last_seen = new_peer['last_seen']
                self._addPeerToCache(permid, last_seen)
        
        for permid in peer_data:
            if 'sim' in peer_data[permid]:
                sim = peer_data[permid]['sim']
                self.addRelativeSim(sender_permid, permid, sim, max_tb_sim)
                
        if cache_db_data['pref']:
            self.addPeerPreferences(sender_permid, cache_db_data['pref'], commit=False)
            
        #self.torrent_db._db.show_sql(1)
        self.torrent_db.commit()
        #self.torrent_db._db.show_sql(0)
                
            #print hash(k), peer_data[k]
        #cache_db_data['infohash']
        #cache_db_data['pref']
        
