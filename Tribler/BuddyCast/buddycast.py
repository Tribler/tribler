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
    \STATE $Q \leftarrow$ select a most similar taste buddy or a most likely online random peer from $C_C$
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

import sys
from random import sample, randint
from time import time, gmtime, strftime
from traceback import print_exc
from sets import Set
#from threading import RLock
from bisect import insort
from copy import deepcopy
import gc
import socket

from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import BUDDYCAST, KEEP_ALIVE
from Tribler.CacheDB.CacheDBHandler import *
from Tribler.utilities import *
from Tribler.unicode import dunno2unicode
from Tribler.Dialogs.activities import ACT_MEET, ACT_RECOMMEND
from Tribler.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
from Tribler.Overlay.SecureOverlay import OLPROTO_VER_CURRENT
from similarity import P2PSim
from TorrentCollecting import SimpleTorrentCollecting
#from Tribler.Statistics.Logger import OverlayLogger

DEBUG = False
debug = False
MAX_BUDDYCAST_LENGTH = 10*1024    # 10 KByte

def now():
    return int(time())

def ctime(t):
    return strftime("%Y-%m-%d.%H:%M:%S", gmtime(t))

def validBuddyCastData(prefxchg, nmyprefs=50, nbuddies=10, npeers=10, nbuddyprefs=10):
    
    def validPeer(peer):
        validPermid(peer['permid'])
        validIP(peer['ip'])
        validPort(peer['port'])
    
    def validPref(pref, num):
        if not (isinstance(prefxchg, list) or isinstance(prefxchg, dict)):
            raise Exception, "bc: invalid pref type " + str(type(prefxchg))
        if len(pref) > num:
            raise Exception, "bc: length of pref exceeds " + str((len(pref), num))
        for p in pref:
            validInfohash(p)
            
    validPeer(prefxchg)
    if not isinstance(prefxchg['name'], str):
        raise Exception, "bc: invalid name type " + str(type(prefxchg['name']))
    validPref(prefxchg['preferences'], nmyprefs)
    
    if len(prefxchg['taste buddies']) > nbuddies:
        raise Exception, "bc: length of prefxchg['taste buddies'] exceeds " + \
                str(len(prefxchg['taste buddies']))
    for b in prefxchg['taste buddies']:
        validPeer(b)
        validPref(b['preferences'], nbuddyprefs)
        
    if len(prefxchg['random peers']) > npeers:
        raise Exception, "bc: length of random peers " + \
                str(len(prefxchg['random peers']))
    for b in prefxchg['random peers']:
        validPeer(b)
    return True

class BuddyCastFactory:
    __single = None
    
    def __init__(self, db_dir='', superpeer=False):
        if BuddyCastFactory.__single:
            raise RuntimeError, "BuddyCastFactory is singleton"
        BuddyCastFactory.__single = self 
        self.db_dir = db_dir
        self.registered = False
        self.buddycast_interval = 15    # MOST IMPORTANT PARAMETER
        self.sync_interval = 20*self.buddycast_interval
        self.superpeer = superpeer
        if self.superpeer:
            print "Start as SuperPeer mode"
        
    def getInstance(*args, **kw):
        if BuddyCastFactory.__single is None:
            BuddyCastFactory(*args, **kw)
        return BuddyCastFactory.__single
    getInstance = staticmethod(getInstance)
    
    def register(self, secure_overlay, rawserver, launchmany, port, errorfunc, 
                 start, metadata_handler, torrent_collecting_solution):    
        if self.registered:
            return
        self.secure_overlay = secure_overlay
        self.rawserver = rawserver
        self.launchmany = launchmany
        self.errorfunc = errorfunc
        
        self.registered = True
        if start:
            self.data_handler = DataHandler(db_dir=self.db_dir)
            if isValidPort(port):
                self.data_handler.updatePort(port)
            self.buddycast_core = BuddyCastCore(secure_overlay, launchmany, 
                   self.data_handler, self.buddycast_interval, self.superpeer,
                   metadata_handler, torrent_collecting_solution
                   )
            self.startup()
    
    def startup(self):
        if self.registered:
            self.rawserver.add_task(self.data_handler.postInit, int(self.buddycast_interval/2))
            self.rawserver.add_task(self.data_handler.updateAllSim, 1811)
            # Arno, 2007-02-28: BC is now started self.buddycast_interval after client
            # startup. This is assumed to give enough time for UPnP to open the firewall
            # if any. So when you change this time, make sure it allows for UPnP to
            # do its thing, or add explicit coordination between UPnP and BC.
            # See BitTornado/launchmany.py
            self.rawserver.add_task(self.doBuddyCast, self.buddycast_interval)
            self.rawserver.add_task(self.sync, self.sync_interval)
            print >> sys.stdout, "BuddyCast starts up"
            
    def doBuddyCast(self):
        self.rawserver.add_task(self.doBuddyCast, self.buddycast_interval)
        self.buddycast_core.work()
        
    def sync(self):
        self.rawserver.add_task(self.sync, self.sync_interval)
        self.data_handler.sync()
        
    def handleMessage(self, permid, selversion, message):
        t = message[0]
        
        if t == BUDDYCAST:
            return self.gotBuddyCastMessage(message[1:], permid, selversion)
        elif t == KEEP_ALIVE:
            if message[1:] == '':
                return self.gotKeepAliveMessage(permid)
            else:
                return False
        else:
            if DEBUG:
                print >> sys.stderr, "bc: wrong message to buddycast", ord(t), "Round", self.round
            return False
        
    def gotBuddyCastMessage(self, msg, permid, selversion):
        return self.buddycast_core.gotBuddyCastMessage(msg, permid, selversion)
    
    def gotKeepAliveMessage(self, permid):
        return self.buddycast_core.gotKeepAliveMessage(permid)
    
    def handleConnection(self,exc,permid,selversion,locally_initiated):
        self.buddycast_core.handleConnection(exc,permid,selversion,locally_initiated)
    
    def addMyPref(self, torrent):
        if self.registered:
            self.data_handler.addMyPref(torrent)
        
    
class BuddyCastCore:
    def __init__(self, secure_overlay, launchmany, data_handler, 
                 buddycast_interval, superpeer, 
                 metadata_handler, torrent_collecting_solution):
        self.secure_overlay = secure_overlay
        self.so_version = OLPROTO_VER_CURRENT
        self.launchmany = launchmany
        self.data_handler = data_handler
        self.buddycast_interval = buddycast_interval
        self.superpeer = superpeer    # change it for superpeers
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
        self.num_tbs = 10           # num of taste buddies in buddycast msg 
        self.num_tb_prefs = 10      # num of taset buddy's preferences in buddycast msg 
        self.num_rps = 10           # num of random peers in buddycast msg  
        # time to check connection and send keep alive message
        self.check_connection_round = max(1, 120/self.buddycast_interval)    
        self.max_conn_cand = 100 # max number of connection candidates
        self.max_conn_tb = 10    # max number of connectable taste buddies
        self.max_conn_rp = 10    # max number of connectable random peers
        self.max_conn_up = 10    # max number of unconnectable peers
        self.bootstrap_num = 5   # max number of peers to fill when bootstrapping
        self.bootstrap_interval = 10*60    # 10 min
        self.network_delay = self.buddycast_interval*2    # 30 seconds
        
        # --- memory ---
        self.send_block_list = {}    #TODO: record the earliest block peer to improve performance
        self.recv_block_list = {}
        self.connections = {}               # permid: time_to_expire, all connected peers
        self.connected_taste_buddies = {}   # permid: connect_time 
        self.connected_random_peers = {}    # permid: connect_time
        self.connected_unconnectable_peers = {}    # permid: connect_time
        self.connection_candidates = {}     # permid: last_seen
        self.sorted_new_candidates = []     # sorted list: the smaller index, the older peer
        
        # --- stats ---
        self.next_initiate = 0
        self.round = 0     # every call to work() is a round
        self.bootstrapped = 0    # bootstrap once every 1 hours
        self.bootstrap_time = 0  # number of times to bootstrap
        self.total_bootstrapped_time = 0
        self.last_bootstrapped = 0    # bootstrap time of the last time
        self.start_time = now()
        
        # --- dependent modules ---
        self.torrent_collecting = None
        if torrent_collecting_solution == 1:
            self.torrent_collecting = SimpleTorrentCollecting(metadata_handler)

        # -- misc ---
        self.dnsindb = self.data_handler.get_dns_from_peerdb
        
                    
    def get_peer_info(self, target_permid, include_permid=True):
        if not target_permid:
            return ' None '
        dns = self.dnsindb(target_permid)
        s_pid = show_permid_short(target_permid)
        try:
            ip = dns[0]
            port = dns[1]
            if include_permid:
                return ' %s %s:%s ' % (s_pid, ip, port)
            else:
                return ' %s:%s ' % (ip, port)
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
        
            self.print_debug_info('Active', 3)
            self.updateSendBlockList()
            
            if self.round % self.check_connection_round == 0:
                self.print_debug_info('Active', 4)
                self.keepConnections()
                self.data_handler.checkUpdateItemSim()
                gc.collect()
                
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
        if len(peers) <= len(self.send_block_list):
            return 0
        all_peer_set = Set(peers)
        block_peer_set = Set(self.send_block_list)
        target_cands = all_peer_set - block_peer_set
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
            
            if (peer_permid in self.connected_taste_buddies or \
                 peer_permid in self.connected_random_peers or \
                 peer_permid in self.connected_unconnectable_peers):   
                self.sendKeepAliveMsg(peer_permid)
                
    def sendKeepAliveMsg(self, peer_permid):
        """ Send keep alive message to a peer, and extend its expiration """
        
        if self.isConnected(peer_permid):
            overlay_protocol_version = self.connections[peer_permid]
            if overlay_protocol_version == self.so_version:
                # From this version, support KEEP_ALIVE message in secure overlay
                keepalive_msg = ''
                self.secure_overlay.send(peer_permid, KEEP_ALIVE+keepalive_msg, 
                                         self.keepaliveSendCallback)
            if debug:
                print "*** Send keep alive to peer", self.get_peer_info(peer_permid),  \
                    "overlay version", overlay_protocol_version
        
    def isConnected(self, peer_permid):
        return peer_permid in self.connections
    
    def keepaliveSendCallback(self, exc, peer_permid):        
        if exc is None:
            if debug:
                print "bc: got keep alive msg from", self.get_peer_info(peer_permid)
        else:
            self.closeConnection(peer_permid)
            if DEBUG:
                print >> sys.stderr, "bc: error - send keep alive msg", exc, \
                self.get_peer_info(peer_permid), "Round", self.round
        
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
            target = (None, None)
            while len(self.sorted_new_candidates) > 0:
                target = self.sorted_new_candidates[-1]
                permid = target[1]
                if permid not in self.connection_candidates or \
                    self.isBlocked(permid, self.send_block_list):
                    self.sorted_new_candidates.pop(-1)
                    continue
                else:
                    break
                
            return target[1]
    
        r = randint(0,1)
        r = 1
        if r == 0:  # select a taste buddy
            target_permid = selectTBTarget()
        else:       # select a random peer
            target_permid = selectRPTarget()
            
        return r, target_permid
    
    def randomSelectList(self, alist, num):
        """ Randomly select a number of items from a list """
        
        num = min(len(alist), num)
        selected = sample(alist, num)
        return selected
    
    # ------ start buddycast exchange ------ #
    def startBuddyCast(self, target_permid):
        """ Connect to a peer, create a buddycast message and send it """
        
        if not target_permid:
            return
        
        if not self.isBlocked(target_permid, self.send_block_list):
            self.secure_overlay.connect(target_permid, self.buddycastConnectCallback)
#            if GLOBAL.overlay_log:
#                dns = self.dnsindb(target_permid)
#                write_overlay_log('CONN_TRY', target_permid, dns)
                        
            self.print_debug_info('Active', 12, target_permid)
            
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
                    raise RuntimeError, 'buddycast: not connected while calling connect_callback'
                
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
        buddycast_msg = bencode(buddycast_data)
        if active:
            self.print_debug_info('Active', 16, target_permid)
        else:
            self.print_debug_info('Passive', 6, target_permid)
            
        self.secure_overlay.send(target_permid, BUDDYCAST+buddycast_msg, self.buddycastSendCallback)
        if active:
            self.print_debug_info('Active', 17, target_permid)
        else:
            self.print_debug_info('Passive', 7, target_permid)

    def createBuddyCastMessage(self, target_permid, selversion):
        """ Create a buddycast message for a target peer on selected protocol version """
        
        my_pref = self.data_handler.getMyPreferences(self.num_myprefs)       #[pref]
        taste_buddies = self.getTasteBuddies(self.num_tbs, self.num_tb_prefs, target_permid, selversion)
        random_peers = self.getRandomPeers(self.num_rps, target_permid, selversion)    #{peer:last_seen}
        buddycast_data = {'ip':self.ip,
                         'port':self.port,
                         'name':self.name,
                         'preferences':my_pref,
                         'taste buddies':taste_buddies, 
                         'random peers':random_peers}
        if selversion == self.so_version:
            # From this version, add 'connectable' entry in buddycast message
            connectable = self.isConnectable()
            buddycast_data['connectable'] = connectable
        
        return buddycast_data

    def getTasteBuddies(self, ntbs, ntbprefs, target_permid, selversion):
        """ Randomly select a number of peers from connected_taste_buddies. """
        
        if not self.connected_taste_buddies:
            return []
        tb_list = self.connected_taste_buddies.keys()
        if target_permid in tb_list:
            tb_list.remove(target_permid)
        peers = self.data_handler.getPeers(tb_list, ['permid', 'ip', 'port'])
        for i in xrange(len(peers)):
            # In overlay version 2, buddycast must include 'age'
            if selversion < self.so_version:
                peers[i]['age'] = 0
            peer_permid = peers[i]['permid']
            peers[i]['preferences'] = self.data_handler.getPeerPrefList(peer_permid, 
                                                    ntbprefs, live=True)
        return peers
    
    def getRandomPeers(self, nrps, target_permid, selversion):
        """ Randomly select a number of peers from connected_random_peers. """
        
        if not self.connected_random_peers:
            return []
        rp_list = self.connected_random_peers.keys()
        if target_permid in rp_list:
            rp_list.remove(target_permid)
        peers = self.data_handler.getPeers(rp_list, ['permid', 'ip', 'port'])
        # In overlay version 2, buddycast must include 'age'
        if selversion < self.so_version:    
            for i in range(len(peers)):
                peers[i]['age'] = 0
        return peers       
    
    def isConnectable(self):
        conn = self.dialback.isConnectable()
        if conn:
            return 1
        else:
            return 0

    def buddycastSendCallback(self, exc, target_permid):
        if exc is None:
            if debug:
                print "bc: *** msg was sent successfully to peer", \
                    self.get_peer_info(target_permid)
        else:
            self.closeConnection(target_permid)
            if debug:
                print "bc: *** warning - error in sending msg to",\
                        self.get_peer_info(target_permid), exc
            
    def blockPeer(self, peer_permid, block_list, block_interval=None):
        """ Add a peer to a block list """
        
        if block_interval is None:
            block_interval = self.block_interval
        unblock_time = now() + block_interval
        block_list[peer_permid] = unblock_time
        
    
    # ------ receive a buddycast message, for both active and passive thread ------ #
    def gotBuddyCastMessage(self, recv_msg, sender_permid, selversion):
        """ Received a buddycast message and handle it. Reply if needed """
        
        if not sender_permid:
            print >> sys.stderr, "bc: error - got BuddyCastMsg from a None peer", \
                        sender_permid, recv_msg, "Round", self.round
            return False
        
        if self.isBlocked(sender_permid, self.recv_block_list):
            if DEBUG:
                print >> sys.stderr, "bc: warning - got BuddyCastMsg from a recv blocked peer", \
                        show_permid(sender_permid), "Round", self.round
            return False
        
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
            print >> sys.stderr, "bc: warning - got large BuddyCastMsg", len(t), "Round", self.round
            return False

        active = self.isBlocked(sender_permid, self.send_block_list)
        
        if active:
            self.print_debug_info('Active', 18, sender_permid)
        else:
            self.print_debug_info('Passive', 2, sender_permid)
        
        try:
            buddycast_data = bdecode(recv_msg)
            buddycast_data.update({'permid':sender_permid})
            try:    # check buddycast message
                validBuddyCastData(buddycast_data, self.num_myprefs, 
                                   self.num_tbs, self.num_rps, self.num_tb_prefs)    # RCP 2            
            except RuntimeError, msg:
                print >> sys.stderr, "bc: warning - got invalide BuddyCastMsg", `msg`, \
                    "Round", self.round   # ipv6
                return False
           
            # update sender's ip and port in buddycast
            dns = self.dnsindb(sender_permid)
            sender_ip = dns[0]
            sender_port = dns[1]
            buddycast_data.update({'ip':sender_ip})
            buddycast_data.update({'port':sender_port})
            # store discovered peers/preferences/torrents to cache and db
            conn = self.handleBuddyCastMessage(sender_permid, buddycast_data, selversion)
            
            if active:
                self.print_debug_info('Active', 19, sender_permid)
            else:
                self.print_debug_info('Passive', 3, sender_permid)
            
            # add sender to a connection list and keep connection with it
            addto = self.addPeerToConnList(sender_permid, conn)
            
            if active:
                self.print_debug_info('Active', 20, sender_permid)
            else:
                self.print_debug_info('Passive', 4, sender_permid)
            
        except:
            print_exc()
            return False
        
        self.blockPeer(sender_permid, self.recv_block_list)
        
        # update torrent collecting module
        self.data_handler.checkUpdateItemSim()
        sender_prefs = self.data_handler.getPeerPrefList(sender_permid)
        if self.torrent_collecting:
            self.torrent_collecting.updatePreferences(sender_permid, sender_prefs, selversion)
        
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
        
        tbs += [buddycast_data]    # add the sender to tbs
        for tb in tbs:
            peer_permid = tb['permid']
            age = max(tb.get('age', 0), 0)    # From secure overlay version 3, it doesn't include 'age'
            last_seen = _now - age
            self.data_handler.addPeer(peer_permid, last_seen, tb)    # new peer
            self.data_handler.setPeerLastSeen(peer_permid, last_seen)
            self.data_handler.addPeerPreferences(peer_permid, tb['preferences'])
            if peer_permid != sender_permid:
                self.addConnCandidate(peer_permid, last_seen)
        
        for rp in rps:
            peer_permid = rp['permid']
            age = max(rp.get('age', 0), 0)
            last_seen = _now - age
            self.data_handler.addPeer(peer_permid, last_seen, rp)
            self.data_handler.setPeerLastSeen(peer_permid, last_seen)
            if peer_permid != sender_permid:    # to be safe; shouldn't happen
                self.addConnCandidate(peer_permid, last_seen)
            
        if len(self.connection_candidates) > 10:
            self.bootstrapped += 1
            
        # TODO: return new added peers/torrents/prefs
        return conn
        
    def addPeerToConnList(self, peer_permid, connectable=0):
        """ Add the peer to Ct, Cr or Cu """
        
        if not self.isConnected(peer_permid):
            print >> sys.stderr, "bc: cannot add a unconnected peer to conn list", "Round", self.round
            return
        
        # remove the existing peer from lists so that its status can be updated later
        if peer_permid in self.connected_taste_buddies:     # Ct
            self.connected_taste_buddies.pop(peer_permid)
        if peer_permid in self.connected_random_peers:    # Cr    
            self.connected_random_peers.pop(peer_permid)
        if peer_permid in self.connected_unconnectable_peers:    # Cu
            self.connected_unconnectable_peers.pop(peer_permid)
        
        _now = now()
        
        if connectable == 1:
            added = self.addPeerToConnTB(peer_permid, _now)
            if not added:
                if self.addPeerToConnRP(peer_permid, _now):
                    addto = '(randomly)'
            else:
                addto = '(taste buddy)'
        else:
            if self.addPeerToConnUP(peer_permid, _now):
                addto = '(peer deemed unreachable)'
            
        return addto
            
    def addPeerToConnTB(self, peer_permid, conn_time):
        """ Add a peer to connected_taste_buddies if its similarity is high enough 
            and remove a least similar and oldest one. 
            Return False if failed so that it has chance to join Cr.
        """
        
        tbs = self.connected_taste_buddies
        if peer_permid in tbs:
            return True
        sim = self.data_handler.getPeerSim(peer_permid)
        if sim >= 0:    # allow random peers be taste buddies to enhance exploration
            if len(tbs) < self.max_conn_tb:
                tbs[peer_permid] = conn_time
                return True
            else:
                # Find the least similar peer. 
                # If two peers have the same similarity, find the older one.
                min_sim_peer = (10**9, now(), None)
                initial = 'abcdefghijklmnopqrstuvwxyz'
                # using :-) as a separator to avoid the permid being splitted
                separator = ':-)'
                for p in tbs:
                    _sim = self.data_handler.getPeerSim(p)
                    _conn_time = tbs[p]
                    r = randint(0, self.max_conn_tb)
                    # to randomly select a peer if the first two in to_cmp are the same
                    name = initial[r] + separator + p     
                    to_cmp = (_sim, _conn_time, name)
                    min_sim_peer = min(min_sim_peer, to_cmp)
                # add it if its sim is high enough, and pop a peer to Cr
                if sim >= min_sim_peer[0]:    # add it
                    out_conn_time = min_sim_peer[1]
                    out_peer = min_sim_peer[2].split(separator)[1]
                    tbs.pop(out_peer)
                    self.addPeerToConnRP(out_peer, out_conn_time)
                    tbs[peer_permid] = conn_time
                    return True
                    
        return False
                    
    def addPeerToConnRP(self, peer_permid, conn_time):
        """ Add a peer to connected_random_peers; close connection to the poped peer """
        
        rps = self.connected_random_peers
        if peer_permid not in rps:
            out_peer = self.addNewPeerToConnList(rps, 
                                      self.max_conn_rp, peer_permid, conn_time)
            if out_peer != peer_permid:
                return True
        return False
                
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
        if debug:
            print >> sys.stdout, "bc: handle conn from overlay", exc, \
                self.get_peer_info(permid), "selversion:", selversion, \
                "local_init:", locally_initiated, ctime(now())

        if exc is None:    # add a connection
            self.addConnection(permid, selversion, locally_initiated)
        else:
            self.closeConnection(permid)
        
    def addConnection(self, peer_permid, selversion, locally_initiated):
        _now = now()
        if not self.isConnected(peer_permid):
            self.connections[peer_permid] = selversion # add a new connection
            self.data_handler._addPeer(peer_permid, _now)
            # add connection from secure overlay
            addto = self.addPeerToConnList(peer_permid, locally_initiated)
            dns = self.get_peer_info(peer_permid, include_permid=False)
            buf = '%s %s'%(dns, addto)
            self.launchmany.set_activity(ACT_MEET, buf)
            if debug:
                print >> sys.stdout, "bc: add connection", \
                    self.get_peer_info(peer_permid), "to", addto

    def closeConnection(self, peer_permid):
        """ Close connection with a peer, and remove it from connection lists """
        
        if debug:
            print >> sys.stdout, "bc: close connection:", self.get_peer_info(peer_permid)
        
        if self.isConnected(peer_permid):
            if peer_permid in self.connected_taste_buddies:
                self.connected_taste_buddies.pop(peer_permid)
            elif peer_permid in self.connected_random_peers:
                self.connected_random_peers.pop(peer_permid)
            elif peer_permid in self.connected_unconnectable_peers:
                self.connected_unconnectable_peers.pop(peer_permid)
                
            self.data_handler.setPeerLastSeen(peer_permid, now())
            self.connections.pop(peer_permid)
        
        if self.torrent_collecting:
            self.torrent_collecting.closeConnection(peer_permid)
            
    # -------------- print debug info ---------- #
    def print_debug_info(self, thread, step, target_permid=None, selversion=0, r=0, addto=''):
        if not debug:
            return
        print "bc: *****", thread, str(step), "-",
        if thread == 'Active':
            if step == 2:
                print "Working:", now() - self.start_time, \
                    "seconds since start. Round", self.round, "Time:", ctime(now())
                nPeer = len(self.data_handler.peers)
                nPref = len(self.data_handler.preferences)
                nCc = len(self.connection_candidates)
                nBs = len(self.send_block_list)
                nBr = len(self.recv_block_list)
                nSO = len(self.secure_overlay.debug_get_live_connections())
                nCo = len(self.connections)
                nCt = len(self.connected_taste_buddies)
                nCr = len(self.connected_random_peers)
                nCu = len(self.connected_unconnectable_peers)
                print "bc: *** Status: nPeer nPref nCc: %d %d %d  nBs nBr: %d %d  nSO nCo nCt nCr nCu: %d %d %d %d %d" % \
                                      (nPeer,nPref,nCc,           nBs,nBr,        nSO,nCo,nCt,nCr,nCu)
                if nSO != nCo:
                    print "bc: warning - nSo and nCo is inconsistent"
                if nCc > self.max_conn_cand or nCt > self.max_conn_tb or nCr > self.max_conn_rp or nCu > self.max_conn_up:
                    print "bc: warning - nCC or nCt or nCr or nCu overloads"
                buf = ""
                for p in self.connections:
                    buf += "bc: * conn: " + self.get_peer_info(p) + "version: " + str(self.connections[p]) + "\n"
                print buf
                
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

        
class DataHandler:
    def __init__(self, db_dir=''):
        # --- database handlers ---
        self.my_db = MyDBHandler(db_dir=db_dir)
        self.peer_db = PeerDBHandler(db_dir=db_dir)
        self.superpeer_db = SuperPeerDBHandler(db_dir=db_dir)
        self.torrent_db = TorrentDBHandler(db_dir=db_dir)
        self.mypref_db = MyPreferenceDBHandler(db_dir=db_dir)
        self.pref_db = PreferenceDBHandler(db_dir=db_dir)
        self.friend_db = FriendDBHandler(db_dir=db_dir)
        self.dbs = [self.my_db, self.peer_db, self.superpeer_db,
                    self.torrent_db, self.mypref_db, self.pref_db]
        self.mypreflist = []    # torrent_infohashes
        self.peers = {}    # permid: [last_seen, similarity]
        self.preferences = {}       # peer_id: Set(torrent)
        self.permid = self.getMyPermid()
        self.total_pref_changed = 0
        # how many peers to load into cache from db
        self.max_num_peers = 2000       
        # after added some many (user, item) pairs, update sim of item to item
        self.update_i2i_threshold = 50  

    def sync(self):
        for db in self.dbs:
            db.sync()
            
    def close(self):
        for db in self.dbs:
            db.close()
    
    def __del__(self):
        self.close()

    def getMyName(self, name=''):
        return self.my_db.get('name', name)
        
    def getMyIp(self, ip=''):
        return self.my_db.get('ip', ip)
    
    def getMyPort(self, port=0):
        return self.my_db.get('port', port)
    
    def getMyPermid(self, permid=''):
        return self.my_db.get('permid', permid)
        
    def postInit(self):
        # build up a cache layer between app and db
        self.updateMyPreferences()
        self.updateAllPeers()
        self.updateAllPref()
        #self.updateAllI2ISim()
        
    def updateAllSim(self):
        # update similarity to all peers to keep consistent
        for peer in self.preferences:
            self.updateSimilarity(peer)
        
    def addMyPref(self, torrent):
        self.updateMyPreferences()
        if torrent not in self.mypreflist:
            self.mypreflist.append(torrent)
        for peer in self.preferences:
            pref = self.preferences[peer]
            if peer in pref:
                self.updateSimilarity(peer)
        self.total_pref_changed += self.update_i2i_threshold
        
    def updateMyPreferences(self):
        self.mypreflist = self.mypref_db.getRecentPrefList()
    
    def updateAllPeers(self, num_peers=None):
        """ Read peers from db and put them in self.peers.
            At most self.max_num_peers recently seen peers can be cached.
        """
        
        all_peerlist = self.peer_db.getPeerList()
        _peer_values = self.getPeers(all_peerlist, ['last_seen', 'similarity'])
        peer_values = []
        for p in _peer_values:
            peer_values.append([p['last_seen'], p['similarity']])
        if num_peers == 0:
            self.peers = dict(zip(all_peerlist, peer_values))
        else:
            if num_peers is None:
                num_peers = self.max_num_peers
            if num_peers == 0 or len(all_peerlist) < num_peers:
                self.peers = dict(zip(all_peerlist, peer_values))
            else:
                tmp_list = zip(peer_values, all_peerlist)
                tmp_list.sort()
                tmp_list.reverse()
                tmp_list = tmp_list[:num_peers]
                tmp_list = [(peer, peer_value) for (peer_value, peer) in tmp_list]
                self.peers = dict(tmp_list)
        return self.peers
    
    def getPeers(self, peer_list, keys):
        return self.peer_db.getPeers(peer_list, keys)
    
    def updateAllPref(self):
        """ Read preferences of peers in self.peers to write into self.preferences """
        
        for peer_permid in self.peers:
            # whole pref for sim calculation
            self.preferences[peer_permid] = Set(self.getPeerPrefList(peer_permid, cache=False))
        
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
            preflist = list(self.preferences.get(permid, []))
        else:
            preflist = self.pref_db.getPrefList(permid)
        if live:    # remove dead torrents
            preflist = self.torrent_db.getLiveTorrents(preflist)
        if num == 0 or num > len(preflist):
            return preflist
        else:
            prefs = sample(preflist, num)    # randomly select 10 prefs to avoid starvation
            return prefs
    
    def updatePort(self, port):
        self.my_db.put('port', port)
  
    def getMyPreferences(self, num=0):
        """ Get a number of my preferences. Get all if num==0 """
        
        if num > len(self.mypreflist):
            return self.mypreflist[:num]
        else:
            return self.mypreflist
    
    def getPeerLastSeen(self, peer_permid):
        if peer_permid not in self.peers:
            return 0
        return self.peers[peer_permid][0]
    
    def getPeerSim(self, peer_permid):
        if peer_permid not in self.peers:
            return -1
        return self.peers[peer_permid][1]
    
    def setPeerLastSeen(self, peer_permid, last_seen):
        old_last_seen = self.getPeerLastSeen(peer_permid)
        new_last_seen = max(old_last_seen, last_seen)
        self.peers[peer_permid][0] = new_last_seen
        self.peer_db.updatePeer(peer_permid, 'last_seen', new_last_seen)
                
    def setPeerSim(self, peer_permid, sim):
        self.peers[peer_permid][1] = sim
        self.peer_db.updatePeer(peer_permid, 'similarity', sim)

    def _addPeer(self, peer_permid, last_seen):
        """ add a peer to cache """
        # Secure Overlay should have added this peer to database.
        
        if not self.peers.has_key(peer_permid):
            self.peers[peer_permid] = [last_seen, 0]    # last_seen, similarity
        else:
            self.setPeerLastSeen(peer_permid, last_seen)

    def addPeer(self, peer_permid, last_seen, peer_data):  
        """ add a peer from buddycast message to both cache and db """
        
        if peer_permid != self.permid:
            self._addPeer(peer_permid, last_seen)    
            if peer_data is not None:
                self._addPeerToDB(peer_permid, last_seen, peer_data)
                
    def addPeerPreferences(self, peer_permid, prefs):
        """ add a peer's preferences to both cache and db """
        
        if peer_permid == self.permid:
            return 0
        
        changed = 0
        for torrent in prefs:
            # add to DB
            if not self.preferences.has_key(peer_permid) or \
                torrent not in self.preferences[peer_permid]:
                changed += 1
            self.pref_db.addPreference(peer_permid, torrent)
            self.torrent_db.addTorrent(torrent)
            
        if changed:
            self.preferences[peer_permid] = Set(self.getPeerPrefList(peer_permid, cache=False))
            self.updateSimilarity(peer_permid)
            self.total_pref_changed += changed
        return changed
            
    def checkUpdateItemSim(self):
        if self.total_pref_changed >= self.update_i2i_threshold:
            self.updateAllI2ISim()
            self.total_pref_changed = 0
    
    def updateSimilarity(self, peer_permid):
        """ update a peer's similarity """
        
        sim = self.computeSimilarity(peer_permid)
        self.setPeerSim(peer_permid, sim)
        
    def computeSimilarity(self, peer_permid):
        """ calculate the similarity
            PeerSim = int(1000*len(pref1&pref2)/(len(pref1)*len(pref2))**0.5)
        """
        
        pref1 = Set(self.mypreflist)
        pref2 = self.preferences.get(peer_permid, Set())
        sim = P2PSim(pref1, pref2)
        return sim
        
    def updateAllI2ISim(self, ret=False):
        # A temporary user to item similarity
        # TODO: incrementally update
        starttime = time()
        torrent_sim = {}    # [sim, pop]
        npref = 0
        for peer in self.preferences:
            preflist = self.getPeerPrefList(peer)
            peer_sim = self.getPeerSim(peer)
            for torrent in preflist:
                if torrent not in torrent_sim:
                    torrent_sim[torrent] = [0, 0]
                torrent_sim[torrent][0] += peer_sim
                torrent_sim[torrent][1] += 1
                npref += 1
        npeer = len(self.preferences)
        for torrent in torrent_sim:
            sim = torrent_sim[torrent][0]
            pop = torrent_sim[torrent][1]
            newsim = sim + pop
            if ret:
                torrent_sim[torrent].append(newsim)
            self.torrent_db.updateTorrentRelevance(torrent, newsim)
        if debug:
            print "bc: updated All I2I sim", len(torrent_sim), npref, npeer, time()-starttime
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
                
            self.peer_db.addPeer(peer_permid, new_peer_data)
        except KeyError:
            print_exc()
            print >> sys.stderr, "bc: _addPeerToDB has KeyError"
        except socket.gaierror:
            print >> sys.stderr, "bc: _addPeerToDB cannot find host by name", peer_data['ip']
        except:
            print_exc()

    def increaseBuddyCastTimes(self, peer_permid):
        self.peer_db.updateTimes(peer_permid, 'buddycast_times', 1)

    def get_dns_from_peerdb(self,permid):
        dns = None
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
    
