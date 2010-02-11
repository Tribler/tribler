# Written by Arno Bakker, Diego Rabioli
# see LICENSE.txt for license information

#
# TODO:
#   - Switch to SIMPLE+METADATA query
#
#   - adjust SIMPLE+METADATA such that it returns P2PURLs if possible.

#   - DO NOT SAVE P2PURLs as .torrent, put in 'torrent_file_name' field in DB.
#
#   - Implement continuous dump of results to JS. I.e. push sorting and 
#     rendering to browser.
#       * One option is RFC5023: Atom Pub Proto, $10.1 "Collecting Partial 
#       Lists" I.e. return a partial list and add a 
#            <link ref="next" href="/.../next10> tag pointing
#       to the next set. See http://www.iana.org/assignments/link-relations/link-relations.xhtml
#       for def of next/first/last, etc. link relations.
#
#        Arno, 2009-10-10: we current add such a <link ref="next" link,
#        which contains a URL that will give all hits found so far. So
#        people should poll this URL.
#
#  - Background thread to save torrentfiles to localdb.
#        Arno, 2009-12-03: Now offloaded to a new TimedTaskQueue.
# 
#
#  - garbage collect hits at connection close. 
#     Not vital, current mechanism will GC. 
#        
#  - Support for multifile torrents
#
#  - BuddyCast hits: Create LIVE MPEG7 fields for live (i.e., livetimepoint) 
#    and VOD MPEG7 fields for VOD. 
#
#  - Use separte HTTP server, Content-serving one needs to be single-threaded
#    at the moment to prevent concurrent RANGE queries on same stream from VLC.
#    Alternative is to put a Condition variable on a content stream.
#
#       Arno, 2009-12-4: I've added locks per content URL and made 
#       VideoHTTPServer multithreaded and it now also serves the search traffic.
#
#  - Debug hanging searches on Windows. May be due to "incomplete outbound TCP 
#    connection" limit, see Encrypter.py :-( I get timeouts opening the feeds
#    listed in the metafeed, whilst the feed server is responding fast.
#    Lowering Encrypter's MAX_INCOMPLETE doesn't help. Alt is to periodically
#    parse the feeds and store the results. 
#
#       Arno, 2009-12-4: Problem still exists. Note that TCP limit has been
#       lifted on Windows > Vista SP2.
#
#  - Update VLC plugin-1.0.1 such that it doesn't show a video window when
#    target is empty.
#
#       Arno, 2009-12-4: At the moment, setting the window size to (0,0) and
#       not providing a URL of a torrent works.
# 

import sys
import time
import random
import urllib
import urlparse
import cgi
import binascii
import copy
from cStringIO import StringIO
from traceback import print_exc,print_stack
from threading import RLock

from Tribler.Core.API import *
from Tribler.Core.BitTornado.bencode import *
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from Tribler.Video.VideoServer import AbstractPathMapper


from Tribler.Plugin.defs import *
from Tribler.Plugin.AtomFeedParser import *

DEBUG = False


P2PQUERYTYPE = "SIMPLE"

def streaminfo404():
    return {'statuscode':404, 'statusmsg':'404 Not Found'}


class SearchPathMapper(AbstractPathMapper):
    
    def __init__(self,session,id2hits,tqueue):
        self.session = session
        self.id2hits = id2hits
        self.tqueue = tqueue
        
        self.metafp = None
        self.metafeedurl = None
        
    def get(self,urlpath):
        if not urlpath.startswith(URLPATH_SEARCH_PREFIX):
            return streaminfo404()
        
        fakeurl = 'http://127.0.0.1'+urlpath
        o = urlparse.urlparse(fakeurl)
        
        print >>sys.stderr,"searchmap: Parsed",o
        
        qdict = cgi.parse_qs(o[4])
        print >>sys.stderr,"searchmap: qdict",qdict
        
        searchstr = qdict['q'][0]
        searchstr = searchstr.strip()
        collection = qdict['collection'][0]
        metafeedurl = qdict['metafeed'][0]
        

        print >>sys.stderr,"searchmap: searchstr",`searchstr`
        
        # Garbage collect:
        self.id2hits.garbage_collect_timestamp_smaller(time.time() - HITS_TIMEOUT)

        
        if collection == "metafeed":
            if not self.check_reload_metafeed(metafeedurl):
                return {'statuscode':504, 'statusmsg':'504 MetaFeed server did not respond'}
            return self.process_search_metafeed(searchstr)
        else:
            return self.process_search_p2p(searchstr)


    def process_search_metafeed(self,searchstr):
        """ Search for hits in the ATOM feeds we got from the meta feed """

        allhits = []
        for feedurl in self.metafp.get_feedurls():
            feedp = FeedParser(feedurl)
            try:
                feedp.parse()
            except:
                # TODO: return 504 gateway error if none of the feeds return anything
                print_exc()
            hits = feedp.search(searchstr)
            allhits.extend(hits)
        
        for hitentry in allhits:
            titleelement = hitentry.find('{http://www.w3.org/2005/Atom}title')
            print >>sys.stderr,"bg: search: meta: Got hit",titleelement.text

        
        id = str(random.random())[2:]
        atomurlpathprefix = URLPATH_HITS_PREFIX+'/'+str(id)
        atomxml = feedhits2atomxml(allhits,searchstr,atomurlpathprefix)
        
        atomstream = StringIO(atomxml)
        atomstreaminfo = { 'statuscode':200,'mimetype': 'application/atom+xml', 'stream': atomstream, 'length': len(atomxml)}

        return atomstreaminfo


    def process_search_p2p(self,searchstr):
        """ Search for hits in local database and perform remote query. 
        EXPERIMENTAL: needs peers with SIMPLE+METADATA query support.
        """
        
        # Initially, searchstr = keywords
        keywords = searchstr.split()

        id = str(random.random())[2:]
        self.id2hits.add_query(id,searchstr,time.time())
        
        # Parallel:  initiate remote query
        q = P2PQUERYTYPE+' '+searchstr
        
        print >>sys.stderr,"bg: search: p2p: Remote query for",q
        got_remote_hits_lambda = lambda permid,query,remotehits:self.sesscb_got_remote_hits(id,permid,query,remotehits)
        self.st = time.time()
        self.session.query_connected_peers(q,got_remote_hits_lambda,max_peers_to_query=20)
        
        # Query local DB while waiting
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        localdbhits = torrent_db.searchNames(keywords)
        print >>sys.stderr,"bg: Local hits",len(localdbhits)
        self.session.close_dbhandler(torrent_db)
        
        # Convert list to dict keyed by infohash
        localhits = localdbhits2hits(localdbhits)
        self.id2hits.add_hits(id,localhits)
        
        # TODO ISSUE: incremental display of results to user? How to implement this?
        atomurlpathprefix = URLPATH_HITS_PREFIX+'/'+str(id)
        nextlinkpath = atomurlpathprefix  
        
        atomhits = hits2atomhits(localhits,atomurlpathprefix)
        atomxml = atomhits2atomxml(atomhits,searchstr,atomurlpathprefix,nextlinkpath=nextlinkpath)
        
        atomstream = StringIO(atomxml)
        atomstreaminfo = { 'statuscode':200,'mimetype': 'application/atom+xml', 'stream': atomstream, 'length': len(atomxml)}
        
        return atomstreaminfo
        

    def sesscb_got_remote_hits(self,id,permid,query,remotehits):
        # Called by SessionCallback thread 
        try:
            
            et = time.time()
            diff = et - self.st
            print >>sys.stderr,"bg: sesscb_got_remote_hits",len(remotehits),"after",diff

            hits = remotehits2hits(remotehits)
            self.id2hits.add_hits(id,hits)
        
            if P2PQUERYTYPE=="SIMPLE+METADATA": 
                bgsearch_save_remotehits_lambda = lambda:self.tqueue_save_remote_hits(remotehits) 
                self.tqueue.add_task(bgsearch_save_remotehits_lambda,0)
            
        except:
            print_exc()


    def check_reload_metafeed(self,metafeedurl):
        if self.metafeedurl is None or self.metafeedurl != metafeedurl:
            self.metafp = MetaFeedParser(metafeedurl)
            try:
                self.metafp.parse() # TODO: offload to separate thread?
                print >>sys.stderr,"bg: search: meta: Found feeds",self.metafp.get_feedurls()
                self.metafeedurl = metafeedurl
            except:
                print_exc()
                return False
            
        return True
                
    def tqueue_save_remote_hits(self,remotehits):
        """ Save .torrents received from SIMPLE+METADATA query on a separate
        thread.
        Run by TimedTaskQueueThread
        """
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)        
        extra_info = {'status':'good'}
        
        n = len(remotehits)
        count = 0
        commit = False
        for infohash,remotehit in remotehits.iteritems():
            if count == n-1:
                commit = True
            try:
                torrentpath = self.tqueue_save_collected_torrent(remotehit['metatype'],remotehit['metadata'])
                torrent_db.addExternalTorrent(torrentpath, source='BC', extra_info=extra_info, commit=commit)
            except:
                print_exc()
            count += 1
            
        self.session.close_dbhandler(torrent_db)

    def tqueue_save_collected_torrent(self,metatype,metadata):
        """ Run by TimedTaskQueueThread """
        if metatype == URL_MIME_TYPE:
            tdef = TorrentDef.load_from_url(metadata)
        else:
            metainfo = bdecode(metadata)
            tdef = TorrentDef.load_from_dict(metainfo)

        infohash = tdef.get_infohash()
        colldir = self.session.get_torrent_collecting_dir()
        
        filename = get_collected_torrent_filename(infohash)
        torrentpath = os.path.join(colldir, filename)
        
        print >>sys.stderr,"bg: search: saving remotehit",torrentpath
        tdef.save(torrentpath)
        return torrentpath


def localdbhits2hits(localdbhits):
    hits = {}
    for dbhit in localdbhits:
        localhit = {}
        localhit['hittype'] = "localdb"
        localhit.update(dbhit)
        infohash = dbhit['infohash'] # convenient to also have in record
        hits[infohash] = localhit
    return hits


def remotehits2hits(remotehits):
    hits = {}
    for infohash,hit in remotehits.iteritems():
        
        #print >>sys.stderr,"remotehit2hits: keys",hit.keys()
        
        remotehit = {}
        remotehit['hittype'] = "remote"
        #remotehit['query_permid'] = permid # Bit of duplication, ignore
        remotehit['infohash'] = infohash  # convenient to also have in record
        remotehit.update(hit)

        # HACK until we use SIMPLE+METADATA: Create fake torrent file
        if not 'metadata' in hit:
            metatype = TSTREAM_MIME_TYPE
            metadata = hack_make_default_merkletorrent(hit['content_name'])
            remotehit['metatype'] = metatype
            remotehit['metadata'] = metadata
        
        hits[infohash] = remotehit
    return hits


class Query2HitsMap:
    """ Stores localdb and remotehits in common hits format, i.e., each
    hit has a 'hittype' attribute that tells which type it is (localdb or remote).
    This Query2HitsMap is passed to the Hits2AnyPathMapper, which is connected
    to the internal HTTP server. 
    
    The HTTP server will then forward all "/hits" GET requests to this mapper.
    The mapper then dynamically generates the required contents from the stored
    hits, e.g. an ATOM feed, MPEG7 description, .torrent file and thumbnail
    images from the torrent.
    """

    def __init__(self):
        self.lock = RLock()
        self.d = {}

        
    def add_query(self,id,searchstr,timestamp):
        if DEBUG:
            print >>sys.stderr,"q2h: lock1",id
        self.lock.acquire()
        try:
            qrec = self.d.get(id,{})
            qrec['searchstr'] = searchstr
            qrec['timestamp'] = timestamp
            qrec['hitlist'] = {}
            self.d[id] = qrec
        finally:
            if DEBUG:
                print >>sys.stderr,"q2h: unlock1"
            self.lock.release()

        
    def add_hits(self,id,hits):
        if DEBUG:
            print >>sys.stderr,"q2h: lock2",id,len(hits)
        self.lock.acquire()
        try:
            qrec = self.d[id]
            qrec['hitlist'].update(hits)
        finally:
            if DEBUG:
                print >>sys.stderr,"q2h: unlock2"
            self.lock.release()
            
    def get_hits(self,id):
        if DEBUG:
            print >>sys.stderr,"q2h: lock3",id
        self.lock.acquire()
        try:
            qrec = self.d[id]
            return copy.copy(qrec['hitlist']) # return shallow copy
        finally:
            if DEBUG:
                print >>sys.stderr,"q2h: unlock3"
            self.lock.release()

    def get_searchstr(self,id):
        if DEBUG:
            print >>sys.stderr,"q2h: lock4"
        self.lock.acquire()
        try:
            qrec = self.d[id]
            return qrec['searchstr']
        finally:
            if DEBUG:
                print >>sys.stderr,"q2h: unlock4"
            self.lock.release()

    def garbage_collect_timestamp_smaller(self,timethres):
        self.lock.acquire()
        try:
            idlist = []
            for id,qrec in self.d.iteritems():
                if qrec['timestamp'] < timethres:
                    idlist.append(id)
            for id in idlist:
                del self.d[id]
        finally:
            self.lock.release()
            


class Hits2AnyPathMapper(AbstractPathMapper):
    """ See Query2Hits description """
    
    def __init__(self,session,id2hits):
        self.session = session
        self.id2hits = id2hits
        
    def get(self,urlpath):
        """ 
        Possible paths:
        /hits/id -> ATOM feed
        /hits/id/infohash.xml  -> MPEG 7
        /hits/id/infohash.tstream -> Torrent file
        /hits/id/infohash.tstream/thumbnail -> Thumbnail
        """
        if DEBUG:
            print >>sys.stderr,"hitsmap: Got",urlpath
        
        if not urlpath.startswith(URLPATH_HITS_PREFIX):
            return streaminfo404()

        paths = urlpath.split('/')
        if len(paths) < 3:
            return streaminfo404()
        
        id = paths[2]
        if len(paths) == 3:
            # ATOM feed
            searchstr = self.id2hits.get_searchstr(id)
            hits = self.id2hits.get_hits(id)

            if DEBUG:
                print >>sys.stderr,"hitsmap: Found",len(hits),"hits"

            
            atomhits = hits2atomhits(hits,urlpath)

            if DEBUG:
                print >>sys.stderr,"hitsmap: Found",len(atomhits),"atomhits"
            
            
            atomxml = atomhits2atomxml(atomhits,searchstr,urlpath)
            
            #if DEBUG:
            #    print >>sys.stderr,"hitsmap: atomstring is",`atomxml`
                
            atomstream = StringIO(atomxml)
            atomstreaminfo = { 'statuscode':200,'mimetype': 'application/atom+xml', 'stream': atomstream, 'length': len(atomxml)}
            return atomstreaminfo
        
        elif len(paths) >= 4:
            # Either NS Metadata, Torrent file, or thumbnail
            urlinfohash = paths[3]
            
            print >>sys.stderr,"hitsmap: path3 is",urlinfohash
            
            if urlinfohash.endswith(URLPATH_TORRENT_POSTFIX):
                # Torrent file, or thumbnail
                coded = urlinfohash[:-len(URLPATH_TORRENT_POSTFIX)]
                infohash = urlpath2infohash(coded)
            else:
                # NS Metadata / MPEG7
                coded = urlinfohash[:-len(URLPATH_NSMETA_POSTFIX)]
                infohash = urlpath2infohash(coded)
            
            # Check if hit:
            hits = self.id2hits.get_hits(id)
            print >>sys.stderr,"hitsmap: meta: Found",len(hits),"hits"
            
            hit = hits.get(infohash,None)
            if hit is not None:
                if len(paths) == 5:
                    # Thumbnail
                    return self.get_thumbstreaminfo(infohash,hit)
                
                elif urlinfohash.endswith(URLPATH_TORRENT_POSTFIX):
                    # Torrent file
                    return self.get_torrentstreaminfo(infohash,hit)
                else:
                    # NS Metadata / MPEG7
                    hiturlpathprefix = URLPATH_HITS_PREFIX+'/'+id
                    return self.get_nsmetastreaminfo(infohash,hit,hiturlpathprefix,urlpath)
        return streaminfo404()

    def get_torrentstreaminfo(self,infohash,hit):
        
        if DEBUG:
            print >>sys.stderr,"hitmap: get_torrentstreaminfo",infohash2urlpath(infohash)
        
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        try:
            if hit['hittype'] == "localdb":
                
                dbhit = torrent_db.getTorrent(infohash,include_mypref=False)
                
                colltorrdir = self.session.get_torrent_collecting_dir()
                filepath = os.path.join(colltorrdir,dbhit['torrent_file_name'])
                # Return stream that contains torrent file
                stream = open(filepath,"rb")
                length = os.path.getsize(filepath)
                torrentstreaminfo = {'statuscode':200,'mimetype':TSTREAM_MIME_TYPE,'stream':stream,'length':length}
                return torrentstreaminfo
            else:
                if hit['metatype'] == URL_MIME_TYPE:
                    # Shouldn't happen, P2PURL should be embedded in atom
                    return streaminfo404()
                else:
                    stream = StringIO(hit['metadata'])
                    length = len(hit['metadata'])
                    torrentstreaminfo = {'statuscode':200,'mimetype':TSTREAM_MIME_TYPE,'stream':stream,'length':length}
                    return torrentstreaminfo
        finally:
            self.session.close_dbhandler(torrent_db)

    def get_thumbstreaminfo(self,infohash,hit):
        
        if DEBUG:
            print >>sys.stderr,"hitmap: get_thumbstreaminfo",infohash2urlpath(infohash)
        
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        try:
            if hit['hittype'] == "localdb":
                dbhit = torrent_db.getTorrent(infohash,include_mypref=False)
                
                colltorrdir = self.session.get_torrent_collecting_dir()
                filepath = os.path.join(colltorrdir,dbhit['torrent_file_name'])
                tdef = TorrentDef.load(filepath)
                (thumbtype,thumbdata) = tdef.get_thumbnail()
                return self.create_thumbstreaminfo(thumbtype,thumbdata)
                    
            else:
                if hit['metatype'] == URL_MIME_TYPE:
                    # Shouldn't happen, not thumb in P2PURL
                    return streaminfo404()
                else:
                    if DEBUG:
                        print >>sys.stderr,"hitmap: get_thumbstreaminfo: looking for thumb in remote hit"
                    
                    metainfo = bdecode(hit['metadata'])
                    tdef = TorrentDef.load_from_dict(metainfo)
                    (thumbtype,thumbdata) = tdef.get_thumbnail()
                    return self.create_thumbstreaminfo(thumbtype,thumbdata)
        finally:
            self.session.close_dbhandler(torrent_db)


    def create_thumbstreaminfo(self,thumbtype,thumbdata):
        if thumbtype is None:
            return streaminfo404()
        else:
            # Return stream that contains thumb
            stream = StringIO(thumbdata)
            length = len(thumbdata)
            thumbstreaminfo = {'statuscode':200,'mimetype':thumbtype,'stream':stream,'length':length}
            return thumbstreaminfo

    def get_nsmetastreaminfo(self,infohash,hit,hiturlpathprefix,hitpath):
        colltorrdir = self.session.get_torrent_collecting_dir()
        nsmetahit = hit2nsmetahit(hit,hiturlpathprefix,colltorrdir)
        
        if DEBUG:
            print >>sys.stderr,"hitmap: get_nsmetastreaminfo: nsmetahit is",`nsmetahit`
        
        nsmetarepr = nsmetahit2nsmetarepr(nsmetahit,hitpath)
        nsmetastream = StringIO(nsmetarepr)
        nsmetastreaminfo = { 'statuscode':200,'mimetype': 'text/xml', 'stream': nsmetastream, 'length': len(nsmetarepr)}
        return nsmetastreaminfo


def infohash2urlpath(infohash):
    
    if len(infohash) != 20:
        raise ValueError("infohash len 20 !=" + str(len(infohash)))
    
    hex = binascii.hexlify(infohash)
    if len(hex) != 40:
        raise ValueError("hex len 40 !=" + str(len(hex)))
    
    return hex
    
def urlpath2infohash(hex):

    if len(hex) != 40:
        raise ValueError("hex len 40 !=" + str(len(hex)) + " " + hex)

    infohash = binascii.unhexlify(hex)
    if len(infohash) != 20:
        raise ValueError("infohash len 20 !=" + str(len(infohash)))
    
    return infohash


def hits2atomhits(hits,urlpathprefix):
    atomhits = {}
    for infohash,hit in hits.iteritems():
        if hit['hittype'] == "localdb":
            atomhit = localdbhit2atomhit(hit,urlpathprefix)
            atomhits[infohash] = atomhit
        else:
            atomhit = remotehit2atomhit(hit,urlpathprefix)
            atomhits[infohash] = atomhit
            
    return atomhits
            

def localdbhit2atomhit(dbhit,urlpathprefix):
    atomhit = {}
    atomhit['title'] = htmlfilter(unicode2iri(dbhit['name']))
    atomhit['summary'] = htmlfilter(unicode2iri(dbhit['comment']))
    if dbhit['thumbnail']:
        urlpath = urlpathprefix+'/'+infohash2urlpath(dbhit['infohash'])+URLPATH_TORRENT_POSTFIX+URLPATH_THUMBNAIL_POSTFIX
        atomhit['p2pnext:image'] = urlpath
    
    return atomhit

def remotehit2atomhit(remotehit,urlpathprefix):
    # TODO: make RemoteQuery return full DB schema of TorrentDB
    
    #print >>sys.stderr,"remotehit2atomhit: keys",remotehit.keys()
    
    atomhit = {}
    atomhit['title'] = htmlfilter(remotehit['content_name'])
    atomhit['summary'] = "Seeders: "+str(remotehit['seeder'])+" Leechers: "+str(remotehit['leecher'])
    if remotehit['metatype'] != URL_MIME_TYPE:
        # TODO: thumbnail, see if we can detect presence (see DB schema remark). 
        # Now we assume it's always there if not P2PURL
        urlpath = urlpathprefix+'/'+infohash2urlpath(remotehit['infohash'])+URLPATH_TORRENT_POSTFIX+URLPATH_THUMBNAIL_POSTFIX
        atomhit['p2pnext:image'] = urlpath

    return atomhit

def htmlfilter(s):
    """ Escape characters to which HTML parser is sensitive """
    if s is None:
        return ""
    news = s
    news = news.replace('&','&amp;')
    news = news.replace('<','&lt;')
    news = news.replace('>','&gt;')
    return news

def atomhits2atomxml(atomhits,searchstr,urlpathprefix,nextlinkpath=None):
    
    # TODO: use ElementTree parser here too, see AtomFeedParser:feedhits2atomxml
    
    atom = ''
    atom += '<?xml version="1.0" encoding="UTF-8"?>\n'
    atom += '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:sy="http://purl.org/rss/1.0/modules/syndication/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:p2pnext="urn:p2pnext:contentfeed:2009" xmlns:taxo="http://purl.org/rss/1.0/modules/taxonomy/">\n'
    atom += '  <title>Hits for '+searchstr+'</title>\n'
    atom += '  <link rel="self" href="'+urlpathprefix+'" />\n'
    if nextlinkpath:
         atom += '  <link rel="next" href="'+nextlinkpath+'" />\n'
    atom += '  <author>\n'
    atom += '  <name>NSSA</name>\n'
    atom += '  </author>\n'
    atom += '  <id>urn:nssa</id>\n'
    atom += '  <updated>'+now2formatRFC3339()+'</updated>\n'
    #atom += '<p2pnext:image src="http://p2pnextfeed1.rad0.net/images/bbc.png" />\n' # TODO

    for infohash,hit in atomhits.iteritems():
        urlinfohash = infohash2urlpath(infohash)
        hitpath = urlpathprefix+'/'+urlinfohash+URLPATH_NSMETA_POSTFIX
        atom += '  <entry>\n'
        atom += '    <title>'+hit['title']+'</title>\n'
        atom += '    <link type="application/xml" href="'+hitpath+'" />\n'
        atom += '    <id>urn:nssa-'+urlinfohash+'</id>\n'
        atom += '    <updated>'+now2formatRFC3339()+'</updated>\n'
        if hit['summary'] is not None:
            atom += '    <summary>'+hit['summary']+'</summary>\n'
        if 'p2pnext:image' in hit:
            atom += '    <p2pnext:image src="'+hit['p2pnext:image']+'" />\n'
        atom += '  </entry>\n'
    
    atom += '</feed>\n'
    return atom


def hit2nsmetahit(hit,hiturlprefix,colltorrdir):
    """ Convert common hit to the fields required for the MPEG7 NS metadata """

    print >>sys.stderr,"his2nsmetahit:"
    
    # Read info from torrent files / P2PURLs
    if hit['hittype'] == "localdb":
        
        name = hit['name']
        if hit['torrent_file_name'].startswith(P2PURL_SCHEME): 
            # Local DB hit that is P2PURL 
            torrenturl = hit['torrent_file_name']
            titleimgurl = None
            tdef = TorrentDef.load_from_url(torrenturl)
        else: 
            # Local DB hit that is torrent file
            torrenturlpath = '/'+infohash2urlpath(hit['infohash'])+URLPATH_TORRENT_POSTFIX
            torrenturl = hiturlprefix + torrenturlpath
            filepath = os.path.join(colltorrdir,hit['torrent_file_name'])
            tdef = TorrentDef.load(filepath)
            (thumbtype,thumbdata) = tdef.get_thumbnail()
            if thumbtype is None:
                titleimgurl = None
            else:
                titleimgurl = torrenturl+URLPATH_THUMBNAIL_POSTFIX
           
    else:
        # Remote hit
        name = hit['content_name']
        if hit['metatype'] == URL_MIME_TYPE:
            torrenturl = hit['torrent_file_name']
            titleimgurl = None
            tdef = TorrentDef.load_from_url(torrenturl)
        else:
            torrenturlpath = '/'+infohash2urlpath(hit['infohash'])+URLPATH_TORRENT_POSTFIX
            torrenturl = hiturlprefix + torrenturlpath
            metainfo = bdecode(hit['metadata'])
            tdef = TorrentDef.load_from_dict(metainfo)
            (thumbtype,thumbdata) = tdef.get_thumbnail()
            if thumbtype is None:
                titleimgurl = None
            else:
                titleimgurl = torrenturl+URLPATH_THUMBNAIL_POSTFIX

    
    # Extract info required for NS metadata MPEG7 representation. 
    nsmetahit = {}
    nsmetahit['title'] = unicode2iri(name)
    nsmetahit['titleimgurl'] = titleimgurl
    comment = tdef.get_comment()
    if comment is None:
        nsmetahit['abstract'] = None
    else:
        nsmetahit['abstract'] = unicode2iri(comment)
    nsmetahit['producer'] = 'Insert Name Here'
    creator = tdef.get_created_by()
    if creator is None:
        creator = 'Insert Name Here Too' 
    nsmetahit['disseminator'] = creator 
    nsmetahit['copyrightstr'] = 'Copyright '+creator
    nsmetahit['torrent_url'] = torrenturl
    # TODO: multifile torrents, LIVE
    nsmetahit['duration']  = bitratelength2nsmeta_duration(tdef.get_bitrate(),tdef.get_length())  

    return nsmetahit

    

def unicode2iri(uni):
    # Roughly after http://www.ietf.org/rfc/rfc3987.txt Sec 3.1 procedure.
    # TODO: do precisely after.
    s = uni.encode('UTF-8')
    return urllib.quote(s)    


    
def bitratelength2nsmeta_duration(bitrate,length):    
    # Format example: PT0H15M0S
    if bitrate is None:
        return 'PT01H00M0S' # 1 hour
    secs = float(length)/float(bitrate)
    hours = float(int(secs / 3600.0))
    secs = secs - hours*3600.0
    mins = float(int(secs / 60.0))
    secs = secs - mins*60.0
    
    return 'PT%02.0fH%02.0fM%02.0fS' % (hours,mins,secs)


def nsmetahit2nsmetarepr(hit,hitpath):
    
    title = hit['title']
    titleimgurl = hit['titleimgurl']
    abstract = hit['abstract']   
    producer = hit['producer']
    disseminator = hit['disseminator']
    copyrightstr = hit['copyrightstr']
    torrenturl = hit['torrent_url']
    duration  = hit['duration'] # Format example: PT0H15M0S
    livetimepoint = now2formatRFC3339() # Format example: '2009-10-05T00:40:00+01:00' # TODO VOD
    
    s = ''
    s += '<?xml version="1.0" encoding="UTF-8"?>\n'
    s += '<Mpeg7 xmlns="urn:mpeg:mpeg7:schema:2001" xmlns:p2pnext="urn:p2pnext:metadata:2008" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    s += '  <Description xsi:type="p2pnext:P2PBasicDescriptionType">\n'
    s += '    <CreationInformation>\n'
    s += '     <Creation>\n'
    s += '        <Title type="main" xml:lang="en">'+title+'</Title>\n'
    s += '        <TitleMedia xsi:type="TitleMediaType">\n'
    if titleimgurl:
        s += '         <TitleImage>\n'
        s += '            <MediaUri>'+titleimgurl+'</MediaUri>\n'
        s += '          </TitleImage>\n'
    s += '        </TitleMedia>\n'
    if abstract:
        s += '        <Abstract>\n'
        s += '          <FreeTextAnnotation>'+abstract+'</FreeTextAnnotation>\n'
        s += '        </Abstract>\n'
    s += '        <Creator>\n'
    s += '          <Role href="urn:mpeg:mpeg7:cs:RoleCS:2001:PRODUCER" />\n'
    s += '          <Agent xsi:type="OrganizationType">\n'
    s += '            <Name>'+producer+'</Name>\n'
    s += '          </Agent>\n'
    s += '        </Creator>\n'
    s += '        <Creator>\n'
    s += '          <Role href="urn:mpeg:mpeg7:cs:RoleCS:2001:DISSEMINATOR" />\n'
    s += '          <Agent xsi:type="OrganizationType">\n'
    s += '            <Name>'+disseminator+'</Name>\n'
    s += '          </Agent>\n'
    s += '        </Creator>\n'
    s += '        <CopyrightString>'+copyrightstr+'</CopyrightString>\n'
    s += '      </Creation>\n'
    s += '    </CreationInformation>\n'
    s += '    <p2pnext:IsInteractiveContent>false</p2pnext:IsInteractiveContent>\n'
    s += '    <p2pnext:IsCommercialContent>false</p2pnext:IsCommercialContent>\n'
    s += '    <p2pnext:ContainsCommercialContent>false</p2pnext:ContainsCommercialContent>\n'
    s += '    <p2pnext:P2PData>\n'
    s += '      <p2pnext:Torrent>\n'
    s += '        <MediaUri>'+torrenturl+'</MediaUri>\n'
    s += '      </p2pnext:Torrent>\n'
    s += '      <p2pnext:P2PFragment>offset(0, 1000)</p2pnext:P2PFragment>\n'
    s += '   </p2pnext:P2PData>\n'
    s += '  </Description>\n'
    s += '  <Description xsi:type="ContentEntityType">\n'
    s += '    <MultimediaContent xsi:type="VideoType">\n'
    s += '      <Video>\n'
    s += '        <MediaTime>\n'
    s += '          <MediaTimePoint>T00:00:00</MediaTimePoint>\n'
    s += '          <MediaDuration>'+duration+'</MediaDuration>\n'
    s += '        </MediaTime>\n'
    s += '      </Video>\n'
    s += '    </MultimediaContent>\n'
    s += '  </Description>\n'
    s += '  <Description xsi:type="UsageDescriptionType">\n'
    s += '    <UsageInformation>\n'
    s += '      <Availability>\n'
    s += '        <InstanceRef href="'+hitpath+'" />\n'
    s += '        <AvailabilityPeriod type="live">\n'
    s += '          <TimePoint>'+livetimepoint+'</TimePoint>\n'
    s += '        </AvailabilityPeriod>\n'
    s += '     </Availability>\n'
    s += '    </UsageInformation>\n'
    s += '  </Description>\n'
    s += '</Mpeg7>\n'

    return s





def hack_make_default_merkletorrent(title):
    metainfo = {}
    metainfo['announce'] = 'http://localhost:0/announce'
    metainfo['creation date'] = int(time.time())
    info = {}
    info['name'] = title
    info['length'] = 2 ** 30
    info['piece length'] = 2 ** 16
    info['root hash'] = '*' * 20
    metainfo['info'] = info
    
    mdict = {}
    mdict['Publisher'] = 'Tribler'
    mdict['Description'] = ''
    mdict['Progressive'] = 1
    mdict['Speed Bps'] = str(2 ** 16)
    mdict['Title'] = metainfo['info']['name']
    mdict['Creation Date'] = long(time.time())
    # Azureus client source code doesn't tell what this is, so just put in random value from real torrent
    mdict['Content Hash'] = 'PT3GQCPW4NPT6WRKKT25IQD4MU5HM4UY'
    mdict['Revision Date'] = long(time.time())
    cdict = {}
    cdict['Content'] = mdict
    metainfo['azureus_properties'] = cdict
    
    return bencode(metainfo)



    

"""
class Infohash2TorrentPathMapper(AbstractPathMapper):
    Mapper to map in the collection of known torrents files (=collected + started
    + own) into the HTTP address space of the local HTTP server. In particular,
    it maps a "/infohash/aabbccdd...zz.tstream" path to a streaminfo dict.
    
    Also supported are "/infohash/aabbccdd...zz.tstream/thumbnail" queries, which
    try to read the thumbnail from the torrent.
        
    def __init__(self,urlpathprefix,session):
        self.urlpathprefix = urlpathprefix
        self.session = session
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        
    def get(self,urlpath):
        if not urlpath.startswith(self.urlpathprefix):
            return None
        try:
            wantthumb = False
            if urlpath.endswith(URLPATH_THUMBNAIL_POSTFIX):
                wantthumb = True
                infohashquote = urlpath[len(self.urlpathprefix):-len(URLPATH_TORRENT_POSTFIX+URLPATH_THUMBNAIL_POSTFIX)]
            else:
                infohashquote = urlpath[len(self.urlpathprefix):-len(URLPATH_TORRENT_POSTFIX)]
            infohash = urlpath2infohash(infohash)
            dbhit = self.torrent_db.getTorrent(infohash,include_mypref=False)
            
            colltorrdir = self.session.get_torrent_collecting_dir()
            filepath = os.path.join(colltorrdir,dbhit['torrent_file_name'])
                                                      
            if not wantthumb:
                # Return stream that contains torrent file
                stream = open(filepath,"rb")
                length = os.path.getsize(filepath)
                streaminfo = {'statuscode':200,'mimetype':TSTREAM_MIME_TYPE,'stream':stream,'length':length}
            else:
                # Return stream that contains thumbnail
                tdef = TorrentDef.load(filepath)
                (thumbtype,thumbdata) = tdef.get_thumbnail()
                if thumbtype is None:
                    return None
                else:
                    stream = StringIO(thumbdata)
                    streaminfo = {'statuscode':200,'mimetype':thumbtype,'stream':stream,'length':len(thumbdata)}
                
            return streaminfo
        except:
            print_exc()
            return None

"""
