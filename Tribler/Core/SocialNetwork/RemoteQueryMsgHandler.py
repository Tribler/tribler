# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information
#
# Send free-form queries to all the peers you are connected to.
#
# TODO: make sure we return also items from download history, but need to verify if 
# their status is still checked.
#
#

import os
import sys
import re
from time import time
from sets import Set
from traceback import print_stack, print_exc
import datetime
import time as T

from M2Crypto import Rand

from Tribler.Core.simpledefs import *
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin
from Tribler.Core.CacheDB.CacheDBHandler import ChannelCastDBHandler,PeerDBHandler
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.BuddyCast.moderationcast_util import *
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_SIXTH, OLPROTO_VER_NINETH, OLPROTO_VER_ELEVENTH, OLPROTO_VER_TWELFTH
from Tribler.Core.Utilities.utilities import show_permid_short,show_permid
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.Core.Utilities.unicode import dunno2unicode
from Tribler.Core.Search.SearchManager import KEYWORDSPLIT_RE

MAX_RESULTS = 20
QUERY_ID_SIZE = 20
MAX_QUERY_REPLY_LEN = 100*1024    # 100K
MAX_PEERS_TO_QUERY = 20

DEBUG = False

class FakeUtility:
    
    def __init__(self,config_path):
        self.config_path = config_path
        
    def getConfigPath(self):
        return self.config_path


class RemoteQueryMsgHandler:
    
    __single = None
    
    def __init__(self):
        if RemoteQueryMsgHandler.__single:
            raise RuntimeError, "RemoteQueryMsgHandler is singleton"
        RemoteQueryMsgHandler.__single = self

        self.connections = {}    # only connected remote_search_peers -> selversion
        self.query_ids2rec = {}    # ARNOCOMMENT: TODO: purge old entries...
        self.overlay_log = None
        self.registered = False
        self.logfile = None 

    def getInstance(*args, **kw):
        if RemoteQueryMsgHandler.__single is None:
            RemoteQueryMsgHandler(*args, **kw)
        return RemoteQueryMsgHandler.__single
    getInstance = staticmethod(getInstance)
        

    def register(self,overlay_bridge,launchmany,config,bc_fac,log=''):
        if DEBUG:
            print >> sys.stderr,"rquery: register"
        self.overlay_bridge = overlay_bridge
        self.session =  launchmany.session
        self.torrent_db = launchmany.torrent_db
        self.peer_db = launchmany.peer_db
        self.channelcast_db = launchmany.channelcast_db
        # debug
        # self.superpeer_db = launchmany.superpeer_db
        
        self.config = config
        self.bc_fac = bc_fac # May be None
        if log:
            self.overlay_log = OverlayLogger.getInstance(log)
        self.torrent_dir = os.path.abspath(self.config['torrent_collecting_dir'])
        self.registered = True

    #
    # Incoming messages
    # 
    def handleMessage(self,permid,selversion,message):
        if not self.registered:
            return True
        
        t = message[0]
        if t == QUERY:
            if DEBUG:
                print >> sys.stderr,"rquery: Got QUERY",len(message)
            return self.recv_query(permid,message,selversion)
        if t == QUERY_REPLY:
            if DEBUG:
                print >> sys.stderr,"rquery: Got QUERY_REPLY",len(message)
            return self.recv_query_reply(permid,message,selversion)
        else:
            if DEBUG:
                print >> sys.stderr,"rquery: UNKNOWN OVERLAY MESSAGE", ord(t)
            return False

    #
    # Incoming connections
    #
    def handleConnection(self,exc,permid,selversion,locally_initiated):
        if not self.registered:
            return True
        
        if DEBUG:
            print >> sys.stderr,"rquery: handleConnection",exc,"v",selversion,"local",locally_initiated, ";#conn:", len(self.connections)
        
        if selversion < OLPROTO_VER_SIXTH:
            return True

        if exc is None:
            self.connections[permid] = selversion
            #superpeers = self.superpeer_db.getSuperPeers()
            #if permid in superpeers:
             #   print >> sys.stderr,"rquery: handleConnection: Connect to superpeer"
        else:
            try:
                del self.connections[permid]
            except:
                pass
                #print_exc()

        return True

    #
    # Send query
    # 
    def send_query(self,query,usercallback,max_peers_to_query=MAX_PEERS_TO_QUERY):
        """ Called by GUI Thread """
        if max_peers_to_query is None:
            max_peers_to_query = MAX_PEERS_TO_QUERY
        if DEBUG:
            print >>sys.stderr,"rquery: send_query",query
        if max_peers_to_query > 0:
            send_query_func = lambda:self.network_send_query_callback(query,usercallback,max_peers_to_query)
            self.overlay_bridge.add_task(send_query_func,0)


    def network_send_query_callback(self,query,usercallback,max_peers_to_query):
        """ Called by overlay thread """
        p = self.create_query(query,usercallback)
        m = QUERY+p
        query_conn_callback_lambda = lambda exc,dns,permid,selversion:self.conn_callback(exc,dns,permid,selversion,m)

        if query.startswith("CHANNEL"):
            wantminoversion = OLPROTO_VER_ELEVENTH
        else:
            wantminoversion =  OLPROTO_VER_SIXTH
            
        if query.startswith("SIMPLE+METADATA"):
            wantminoversion = OLPROTO_VER_TWELFTH
        else:
            wantminoversion =  OLPROTO_VER_SIXTH

        if DEBUG:
            print >>sys.stderr,"rquery: send_query: Connected",len(self.connections),"peers"
        
        #print "******** send query net cb:", query, len(self.connections), self.connections
        
        peers_to_query = 0
        for permid,selversion in self.connections.iteritems():
            if selversion >= wantminoversion:
                self.overlay_bridge.connect(permid,query_conn_callback_lambda)
                peers_to_query += 1
        
        if peers_to_query < max_peers_to_query and self.bc_fac and self.bc_fac.buddycast_core:
            query_cand = self.bc_fac.buddycast_core.getRemoteSearchPeers(MAX_PEERS_TO_QUERY-peers_to_query,wantminoversion)
            for permid in query_cand:
                if permid not in self.connections:    # don't call twice
                    self.overlay_bridge.connect(permid,query_conn_callback_lambda)
                    peers_to_query += 1
        
        if DEBUG:
            print >>sys.stderr,"rquery: send_query: Sent to",peers_to_query,"peers"
        
    def create_query(self,query,usercallback):
        d = {}
        d['q'] = query
        d['id'] = self.create_and_register_query_id(query,usercallback)
        return bencode(d)
        
    def create_and_register_query_id(self,query,usercallback):
        id = Rand.rand_bytes(QUERY_ID_SIZE)
        queryrec = {'query':query,'usercallback':usercallback}
        self.query_ids2rec[id] = queryrec
        return id
        
    def is_registered_query_id(self,id):
        if id in self.query_ids2rec:
            return self.query_ids2rec[id]
        else:
            return None
        
    def conn_callback(self,exc,dns,permid,selversion,message):
        if exc is None and selversion >= OLPROTO_VER_SIXTH:
            self.overlay_bridge.send(permid,message,self.send_callback)
            
    def send_callback(self,exc,permid):
        #print "******* queury was sent to", show_permid_short(permid), exc
        pass
    
    
    #
    # Receive query
    # 
    
    def recv_query(self,permid,message,selversion):
        if selversion < OLPROTO_VER_SIXTH:
            return False

        # Unpack
        try:
            d = bdecode(message[1:])
        except:
            if DEBUG:
                print >>sys.stderr,"rquery: Cannot bdecode QUERY message"
            #print_exc()
            return False
        
        if not isValidQuery(d,selversion):
            if DEBUG:
                print >>sys.stderr,"rquery: QUERY invalid",`d`
            return False

        # ACCESS CONTROL, INCLUDING CHECKING IF PEER HAS NOT EXCEEDED
        # QUERY QUOTUM IS DONE in Tribler/Core/RequestPolicy.py
        #

        # Process
        self.process_query(permid, d, selversion)
        
        return True

    def set_log_file(self, logfile):
        self.logfile = open(logfile, "a") 
   
   
    def log(self, permid, decoded_message):        
        lt = T.localtime(T.time())
        timestamp = "%04d-%02d-%02d %02d:%02d:%02d" % (lt[0], lt[1], lt[2], lt[3], lt[4], lt[5])
        ip = self.peer_db.getPeer(permid, "ip")
        #ip = "x.y.z.1"
        s = "%s\t%s\t%s\t%s\n"% (timestamp, bin2str(permid), ip, decoded_message)
        
        print dunno2unicode(s)
        self.logfile.write(dunno2unicode(s)) # bin2str(
        self.logfile.flush()
    
    
    #
    # Send query reply
    #
    def process_query(self, permid, d, selversion):
        hits = None
        p = None
        sendtorrents = False

        netwq = d['q']
        if netwq.startswith("SIMPLE"): # remote query
            # Format: 'SIMPLE '+string of space separated keywords or
            #         'SIMPLE+METADATA' +string of space separated keywords
            #
            # In the future we could support full SQL queries:
            # SELECT infohash,torrent_name FROM torrent_db WHERE status = ALIVE
            
            if netwq.startswith('SIMPLE+METADATA'):
                q = d['q'][len('SIMPLE+METADATA '):]
                sendtorrents = True
            else:
                q = d['q'][len('SIMPLE '):]
                    
            q = self.clean_netwq(q)
            q = dunno2unicode(q)
            kws = re.split(KEYWORDSPLIT_RE,q.lower())
            hits = self.search_torrents(kws, maxhits=MAX_RESULTS,sendtorrents=sendtorrents)
            p = self.create_remote_query_reply(d['id'],hits,selversion)
            
        elif netwq.startswith("CHANNEL"): # channel query
            q = d['q'][len('CHANNEL '):]
            q = self.clean_netwq(q)
            q = dunno2unicode(q)
            hits = self.channelcast_db.searchChannels(q)
            p = self.create_channel_query_reply(d['id'],hits,selversion)

        # log incoming query, if logfile is set
        if self.logfile:
            self.log(permid, q)        
     
        m = QUERY_REPLY+p

        if self.overlay_log:
            nqueries = self.get_peer_nqueries(permid)
            # RECV_MSG PERMID OVERSION NUM_QUERIES MSG
            self.overlay_log('RECV_QRY', show_permid(permid), selversion, nqueries, repr(d))

            # RPLY_QRY PERMID NUM_HITS MSG
            self.overlay_log('RPLY_QRY', show_permid(permid), len(hits), repr(p))

        self.overlay_bridge.send(permid, m, self.send_callback)
        
        self.inc_peer_nqueries(permid)


    def clean_netwq(self,q):
        # Filter against bad input
        newq = u''
        for i in range(0,len(q)):
            if q[i].isalnum():
                newq += q[i]
        return newq
            
        
    def create_remote_query_reply(self,id,hits,selversion):
        getsize = os.path.getsize
        join = os.path.join
        d = {}
        d['id'] = id
        d2 = {}
        for torrent in hits:
            r = {}
            # NEWDBSTANDARD. Do not rename r's fields: they are part of the 
            # rquery protocol spec.
            r['content_name'] = torrent['name'] # According to TorrentDBHandler.addExternalTorrentencoded this is the original encoded name, TODO: standardize on UTF-8 encoding. 
            r['length'] = torrent['length']
            r['leecher'] = torrent['num_leechers']
            r['seeder'] = torrent['num_seeders']
            # Arno: TODO: sending category doesn't make sense as that's user-defined
            # leaving it now because of time constraints
            r['category'] = torrent['category']
            if selversion >= OLPROTO_VER_NINETH:
                r['torrent_size'] = getsize(join(self.torrent_dir, torrent['torrent_file_name']))
            if selversion >= OLPROTO_VER_ELEVENTH:
                r['channel_permid'] = torrent['channel_permid']
                r['channel_name'] = torrent['channel_name']
            if selversion >= OLPROTO_VER_TWELFTH and 'metadata' in torrent:
                if DEBUG:
                    print >>sys.stderr,"rqmh: create_query_reply: Adding torrent file"
                r['metatype'] = torrent['metatype']
                r['metadata'] = torrent['metadata']
                
            d2[torrent['infohash']] = r
        d['a'] = d2
        return bencode(d)

    def create_channel_query_reply(self,id,hits,selversion):
        d = {}
        d['id'] = id
        d2 = {}
        for hit in hits:
            r = {}
            r['publisher_id'] = hit[0]
            r['publisher_name'] = hit[1]
            r['infohash'] = hit[2]
            r['torrenthash'] = hit[3]
            r['torrentname'] = hit[4]
            r['time_stamp'] = hit[5]
            # hit[6]: signature, which is unique for any torrent published by a user
            signature = hit[6].encode('ascii','ignore')
            d2[signature] = r
        d['a'] = d2
        return bencode(d)
    
    #
    # Receive query reply
    #
    def recv_query_reply(self,permid,message,selversion):
        
        #print "****** recv query reply", len(message)
        
        if selversion < OLPROTO_VER_SIXTH:
            return False
        
        #if len(message) > MAX_QUERY_REPLY_LEN:
        #    return True    # don't close

        # Unpack
        try:
            d = bdecode(message[1:])
        except:
            if DEBUG:
                print >>sys.stderr,"rquery: Cannot bdecode QUERY_REPLY message", selversion
            return False
        
        if not isValidQueryReply(d,selversion):
            if DEBUG:
                print >>sys.stderr,"rquery: not valid QUERY_REPLY message", selversion
            return False

        
        # Check auth
        queryrec = self.is_registered_query_id(d['id'])
        if not queryrec:
            if DEBUG:
                print >>sys.stderr,"rquery: QUERY_REPLY has unknown query ID", selversion
            return False

        if selversion >= OLPROTO_VER_TWELFTH:
            if queryrec['query'].startswith('SIMPLE+METADATA'):
                for infohash,torrentrec in d['a'].iteritems():
                    if not 'metatype' in torrentrec:
                        if DEBUG:
                            print >>sys.stderr,"rquery: QUERY_REPLY has no metatype field", selversion
                        return False

                    if not 'metadata' in torrentrec:
                        if DEBUG:
                            print >>sys.stderr,"rquery: QUERY_REPLY has no metadata field", selversion
                        return False
                    if torrentrec['torrent_size'] != len(torrentrec['metadata']):
                        if DEBUG:
                            print >>sys.stderr,"rquery: QUERY_REPLY torrent_size != len metadata", selversion
                        return False
                    try:
                        # Validity test
                        if torrentrec['metatype'] == URL_MIME_TYPE:
                            tdef = TorrentDef.load_from_url(torrentrec['metadata'])
                        else:
                            metainfo = bdecode(torrentrec['metadata'])
                            tdef = TorrentDef.load_from_dict(metainfo)
                    except:
                        if DEBUG:
                            print_exc()
                        return False
                        

        # Process
        self.process_query_reply(permid,queryrec['query'],queryrec['usercallback'],d)
        return True


    def process_query_reply(self,permid,query,usercallback,d):
        
        if DEBUG:
            print >>sys.stderr,"rquery: process_query_reply:",show_permid_short(permid),query,d
        
        if len(d['a']) > 0:
            remote_query_usercallback_lambda = lambda:usercallback(permid,query,d['a'])
            self.session.uch.perform_usercallback(remote_query_usercallback_lambda)
        elif DEBUG:
            print >>sys.stderr,"rquery: QUERY_REPLY: no results found"


    def inc_peer_nqueries(self, permid):
        peer = self.peer_db.getPeer(permid)
        try:
            if peer is not None:
                nqueries = peer['num_queries']
                if nqueries is None:
                    nqueries = 0
                self.peer_db.updatePeer(permid, num_queries=nqueries+1)
        except:
            print_exc()

    def get_peer_nqueries(self, permid):
        peer = self.peer_db.getPeer(permid)
        if peer is None:
            return 0
        else:
            return peer['num_queries']


    def search_torrents(self,kws,maxhits=None,sendtorrents=False):
        
        if DEBUG:
            print >>sys.stderr,"rquery: search for torrents matching",`kws`
        
        allhits = self.torrent_db.searchNames(kws,local=False)
        
        print >>sys.stderr,"rquery: got matches",`allhits`
        
        if maxhits is None:
            hits = allhits
        else:
            hits = allhits[:maxhits]
            
        colltorrdir = self.session.get_torrent_collecting_dir()
        if sendtorrents:
            
            print >>sys.stderr,"rqmh: search_torrents: adding torrents"
            for hit in hits:
                filename = os.path.join(colltorrdir,hit['torrent_file_name'])
                try:
                    tdef = TorrentDef.load(filename)
                    if tdef.get_url_compat():
                        metatype = URL_MIME_TYPE
                        metadata = tdef.get_url()
                    else:
                        metatype = TSTREAM_MIME_TYPE
                        metadata = bencode(tdef.get_metainfo())
                except:
                    print_exc()
                    metadata = None
                hit['metatype'] = metatype
                hit['metadata'] = metadata
                
            # Filter out hits for which we could not read torrent file (rare)
            newhits = []
            for hit in hits:
                if hit['metadata'] is not None:
                    newhits.append(hit)
            hits = newhits
            
        return hits



def isValidQuery(d,selversion):
    if not isinstance(d,dict):
        if DEBUG:
            print >> sys.stderr, "rqmh: not dict"
        return False
    if not ('q' in d and 'id' in d):
        if DEBUG:
            print >> sys.stderr, "rqmh: some keys are missing", d.keys()
        return False
    if not ((isinstance(d['q'],str) or isinstance(d['q'], unicode)) and isinstance(d['id'],str)):
        if DEBUG:
            print >> sys.stderr, "rqmh: d['q'] or d['id'] are not of string format", d['q'], d['id']
        return False
    if len(d['q']) == 0:
        if DEBUG:
            print >> sys.stderr, "rqmh: len(d['q']) == 0"
        return False
    if selversion < OLPROTO_VER_TWELFTH and d['q'].startswith('SIMPLE+METADATA'):
        return False
    idx = d['q'].find(' ')
    if idx == -1:
        return False
    keyw = d['q'][idx+1:]
    if not keyw.isalnum():
        return False
    if len(d) > 2: # no other keys
        if DEBUG:
            print >> sys.stderr, "rqmh: d has more than 2 keys"
        return False
    return True

def isValidQueryReply(d,selversion):
    if not isinstance(d,dict):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: not dict"
        return False
    if not ('a' in d and 'id' in d):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: a or id key missing"
        return False
    if not (isinstance(d['a'],dict) and isinstance(d['id'],str)):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: a or id key not dict/str"
        return False
    if not isValidHits(d['a'],selversion):
        return False
    if len(d) > 2: # no other keys
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: too many keys, got",d.keys()
        return False
    return True

def isValidHits(d,selversion):
    if not isinstance(d,dict):
        return False
    ls = d.values()
    if len(ls)>0:
        l = ls[0]
        if 'publisher_id' in l: # channel search result
            if not validChannelCastMsg(d):
                return False
        elif 'content_name' in l: # remote search
            for key in d.keys():
        #        if len(key) != 20:
        #            return False
                val = d[key]
                if not isValidRemoteVal(val,selversion):
                    return False
    return True

def isValidChannelVal(d, selversion):
    if not isinstance(d,dict):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: torrentrec: value not dict"
        return False
    if not ('publisher_id' in d and 'publisher_name' in d and 'infohash' in d and 'torrenthash' in d and 'torrentname' in d and 'time_stamp' in d):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: a: key missing, got",d.keys()
        return False
    return True

def isValidRemoteVal(d,selversion):
    if not isinstance(d,dict):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: a: value not dict"
        return False
    if selversion >= OLPROTO_VER_TWELFTH:
        if not ('content_name' in d and 'length' in d and 'leecher' in d and 'seeder' in d and 'category' in d and 'torrent_size' in d and 'channel_permid' in d and 'channel_name' in d):
            if DEBUG:
                print >>sys.stderr,"rqmh: reply: torrentrec12: key missing, got",d.keys()
            return False
        if 'metatype' in d and 'metadata' in d:
            try:
                metatype = d['metatype']
                metadata = d['metadata']
                if metatype == URL_MIME_TYPE:
                    tdef = TorrentDef.load_from_url(metadata)
                else:
                    metainfo = bdecode(metadata)
                    tdef = TorrentDef.load_from_dict(metainfo)
            except:
                if DEBUG:
                    print >>sys.stderr,"rqmh: reply: torrentrec12: metadata invalid"
                    print_exc()
                return False

    elif selversion >= OLPROTO_VER_ELEVENTH:
        if not ('content_name' in d and 'length' in d and 'leecher' in d and 'seeder' in d and 'category' in d and 'torrent_size' in d and 'channel_permid' in d and 'channel_name' in d):
            if DEBUG:
                print >>sys.stderr,"rqmh: reply: torrentrec11: key missing, got",d.keys()
            return False
        
    elif selversion >= OLPROTO_VER_NINETH:
        if not ('content_name' in d and 'length' in d and 'leecher' in d and 'seeder' in d and 'category' in d and 'torrent_size' in d):
            if DEBUG:
                print >>sys.stderr,"rqmh: reply: torrentrec9: key missing, got",d.keys()
            return False
    else:
        if not ('content_name' in d and 'length' in d and 'leecher' in d and 'seeder' in d and 'category' in d):
            if DEBUG:
                print >>sys.stderr,"rqmh: reply: torrentrec6: key missing, got",d.keys()
            return False
        
#    if not (isinstance(d['content_name'],str) and isinstance(d['length'],int) and isinstance(d['leecher'],int) and isinstance(d['seeder'],int)):
#        return False
#    if len(d) > 4: # no other keys
#        return False
    return True

        
