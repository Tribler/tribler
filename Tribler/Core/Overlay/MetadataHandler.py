# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information
import sys
import os
import stat
import random
import itertools
from Tribler.Core.Utilities.Crypto import sha
from time import time, ctime
from traceback import print_exc, print_stack
from sets import Set
from threading import currentThread

from Tribler.Core.simpledefs import *
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.Utilities.utilities import isValidInfohash, show_permid_short, sort_dictlist, bin2str, get_collected_torrent_filename
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FOURTH, OLPROTO_VER_ELEVENTH 
from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from Tribler.Core.osutils import getfreespace,get_readable_torrent_name
from Tribler.Core.CacheDB.CacheDBHandler import BarterCastDBHandler
from Tribler.Core.CacheDB.SqliteCacheDBHandler import PopularityDBHandler
from Tribler.Core.TorrentDef import TorrentDef

DEBUG = False

BARTERCAST_TORRENTS = False

# Python no recursive imports?
# from overlayswarm import overlay_infohash
overlay_infohash = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

Max_Torrent_Size = 2*1024*1024    # 2MB torrent = 6GB ~ 250GB content


class MetadataHandler:
    
    __single = None
    
    def __init__(self):
        if MetadataHandler.__single:
            raise RuntimeError, "MetadataHandler is singleton"
        MetadataHandler.__single = self
        self.num_torrents = -100
        self.avg_torrent_size = 25*(2**10)
        self.initialized = False
        self.registered = False
        self.popularity_db = PopularityDBHandler.getInstance()


    def getInstance(*args, **kw):
        if MetadataHandler.__single is None:
            MetadataHandler(*args, **kw)
        return MetadataHandler.__single
    getInstance = staticmethod(getInstance)
        
    def register(self, overlay_bridge, dlhelper, launchmany, config):
        self.registered = True
        self.overlay_bridge = overlay_bridge
        self.dlhelper = dlhelper
        self.launchmany = launchmany
        self.torrent_db = launchmany.torrent_db 
        self.config = config
        self.min_free_space = self.config['stop_collecting_threshold']*(2**20)
        #if self.min_free_space <= 0:
        #    self.min_free_space = 200*(2**20)    # at least 200 MB left on disk
        self.config_dir = os.path.abspath(self.config['state_dir'])
        self.torrent_dir = os.path.abspath(self.config['torrent_collecting_dir'])
        print >>sys.stderr,"metadata: collect dir is",self.torrent_dir 
        assert os.path.isdir(self.torrent_dir)
        self.free_space = self.get_free_space()
        print >> sys.stderr, "Available space for database and collecting torrents: %d MB," % (self.free_space/(2**20)), "Min free space", self.min_free_space/(2**20), "MB"
        self.max_num_torrents = self.init_max_num_torrents = int(self.config['torrent_collecting_max_torrents'])
        self.upload_rate = 1024 * int(self.config['torrent_collecting_rate'])   # 5KB/s
        self.num_collected_torrents = 0
        self.recently_collected_torrents = [] # list of infohashes
        self.load_recently_collected_torrents(10, 40)
        self.upload_queue = []
        self.requested_torrents = Set()
        self.next_upload_time = 0
        self.initialized = True
        self.rquerytorrenthandler = None
        self.delayed_check_overflow(5)

    def load_recently_collected_torrents(self, num_recent, num_random):
        """
        The self.recently_collected_torrents is used to inform other
        peers of existing torrent files.  This list should also
        contain torrent files that have been collected in the past
        (not just this running session).

        Hence, this function loads torrent files from the database.

        NUM_RECENT is the number of recent torrent files, and
        NUM_RANDOM is the number or random torrent files that will end
        up in the self.recently_collected_torrents list.
        """
        # collect all torrents on disk
        torrent_dir = self.torrent_db.getTorrentDir()
        join = os.path.join
        items = [join(torrent_dir, filename) for filename in os.listdir(torrent_dir)]

        # sort all torrents by creation/modification time
        get_stat = os.stat
        ST_MTIME = stat.ST_MTIME
        items = [(get_stat(filename)[ST_MTIME], filename) for filename in items]
        items.sort(reverse=True)

        # get last NUM_RECENT and NUM_RANDOM randomly choses items
        if len(items) >= num_recent:
            recent_items = items[:num_recent]
            random_items = random.sample(items[num_recent:], min(num_random, len(items) - num_recent))
        else:
            recent_items = items
            random_items = []

        # append the NUM_RECENT to the list
        append = self.recently_collected_torrents.append
        load = TorrentDef.load
        for _, filename in recent_items:
            torrent_def = load(filename)
            append(torrent_def.get_infohash())

        # append the NUM_RANDOM to the list
        for _, filename in random_items:
            torrent_def = load(filename)
            append(torrent_def.get_infohash())

    def register2(self,rquerytorrenthandler):
        self.rquerytorrenthandler = rquerytorrenthandler


    def handleMessage(self,permid,selversion,message):
        
        t = message[0]
        
        if t == GET_METADATA:   # the other peer requests a torrent
            if DEBUG:
                print >> sys.stderr,"metadata: Got GET_METADATA",len(message),show_permid_short(permid)
            return self.send_metadata(permid, message, selversion)
        elif t == METADATA:     # the other peer sends me a torrent
            if DEBUG:
                print >> sys.stderr,"metadata: Got METADATA",len(message),show_permid_short(permid),selversion, currentThread().getName()
            return self.got_metadata(permid, message, selversion)
        else:
            if DEBUG:
                print >> sys.stderr,"metadata: UNKNOWN OVERLAY MESSAGE", ord(t)
            return False

    def send_metadata_request(self, permid, infohash, selversion=-1, caller="BC"):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        if DEBUG:
            print >> sys.stderr,"metadata: Connect to send GET_METADATA to",show_permid_short(permid)
        if not isValidInfohash(infohash):
            return False
        
        filename,metadata = self.torrent_exists(infohash)
        if filename is not None:    # torrent already exists on disk
            if DEBUG:
                print >> sys.stderr,"metadata: send_meta_req: Already on disk??!"
            self.notify_torrent_is_in(infohash, metadata, filename)
            return True
        
        if caller == "dlhelp":
            self.requested_torrents.add(infohash)
        
        if self.min_free_space != 0 and (self.free_space - self.avg_torrent_size < self.min_free_space):   # no space to collect
            self.free_space = self.get_free_space()
            if self.free_space - self.avg_torrent_size < self.min_free_space:
                self.warn_disk_full()
                return True

        try:
            # Optimization: don't connect if we're connected, although it won't 
            # do any harm.
            if selversion == -1: # not currently connected
                self.overlay_bridge.connect(permid,lambda e,d,p,s:self.get_metadata_connect_callback(e,d,p,s,infohash))
            else:
                self.get_metadata_connect_callback(None,None,permid,selversion,infohash)
            
        except:
            print_exc()
            return False
        return True

    def torrent_exists(self, infohash):
        # if the torrent is already on disk, put it in db
        
        file_name = get_collected_torrent_filename(infohash)
        torrent_path = os.path.join(self.torrent_dir, file_name)
        if not os.path.exists(torrent_path):
            return None,None
        else:
            metadata = self.read_torrent(torrent_path)
            if not self.valid_metadata(infohash, metadata):
                return None
            self.addTorrentToDB(torrent_path, infohash, metadata, source="BC", extra_info={})
            return file_name, metadata

    def get_metadata_connect_callback(self,exc,dns,permid,selversion,infohash):
        if exc is None:
            if DEBUG:
                print >> sys.stderr,"metadata: Sending GET_METADATA to",show_permid_short(permid)
            ## Create metadata_request according to protocol version
            try:
                metadata_request = bencode(infohash)
                self.overlay_bridge.send(permid, GET_METADATA + metadata_request,self.get_metadata_send_callback)
                self.requested_torrents.add(infohash)
            except:
                print_exc()
        elif DEBUG:
            print >> sys.stderr,"metadata: GET_METADATA: error connecting to",show_permid_short(permid)

    def get_metadata_send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: error sending to",show_permid_short(permid),exc
            pass
        else:
            pass
        
    def send_metadata(self, permid, message, selversion):
        try:
            infohash = bdecode(message[1:])
        except:
            print_exc()
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: error becoding"
            return False
        if not isValidInfohash(infohash):
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: invalid hash"
            return False

        # TODO:
        res = self.torrent_db.getOne(('torrent_file_name', 'status_id'), infohash=bin2str(infohash))
        if not res:
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: not in database", infohash
            return True    # don't close connection because I don't have the torrent
        torrent_file_name, status_id = res
        if status_id == self.torrent_db._getStatusID('dead'):
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: Torrent was dead"
            return True
        if not torrent_file_name:
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: no torrent file name"
            return True
        torrent_path = os.path.join(self.torrent_dir, torrent_file_name)
        if not os.path.isfile(torrent_path):
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: not existing", res, torrent_path
            return True
        
        task = {'permid':permid, 'infohash':infohash, 'torrent_path':torrent_path, 'selversion':selversion}
        self.upload_queue.append(task)
        if int(time()) >= self.next_upload_time:
            self.checking_upload_queue()
        
        return True

    def read_and_send_metadata(self, permid, infohash, torrent_path, selversion):
        torrent_data = self.read_torrent(torrent_path)
        if torrent_data:
            # Arno: Don't send private torrents
            try:
                metainfo = bdecode(torrent_data)
                if 'info' in metainfo and 'private' in metainfo['info'] and metainfo['info']['private']:
                    if DEBUG:
                        print >> sys.stderr,"metadata: Not sending torrent", `torrent_path`,"because it is private"
                    return 0
            except:
                print_exc()
                return 0
            

            if DEBUG:
                print >> sys.stderr,"metadata: sending torrent", `torrent_path`, len(torrent_data)
                
            torrent = {}
            torrent['torrent_hash'] = infohash
            # P2PURLs: If URL compat then send URL
            tdef = TorrentDef.load_from_dict(metainfo)
            if selversion >= OLPROTO_VER_ELEVENTH and tdef.get_url_compat():
                torrent['metatype'] = URL_MIME_TYPE
                torrent['metadata'] = tdef.get_url()
            else:
                torrent['metatype'] = TSTREAM_MIME_TYPE
                torrent['metadata'] = torrent_data
                
            if selversion >= OLPROTO_VER_FOURTH:
                data = self.torrent_db.getTorrent(infohash)
                if data is None:
                    # DB inconsistency
                    return 0
                nleechers = data.get('leecher', -1)
                nseeders = data.get('seeder', -1)
                last_check_ago = int(time()) - data.get('last_check_time', 0)    # relative time
                if last_check_ago < 0:
                    last_check_ago = 0
                status = data.get('status', 'unknown')
                
                torrent.update({'leecher':nleechers,
                                'seeder':nseeders,
                                'last_check_time':last_check_ago,
                                'status':status})


            return self.do_send_metadata(permid, torrent, selversion)
        else:    # deleted before sending it
            self.torrent_db.deleteTorrent(infohash, delete_file=True, commit=True)
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: no torrent data to send"
            return 0

    def do_send_metadata(self, permid, torrent, selversion):
        metadata_request = bencode(torrent)
        if DEBUG:
            print >> sys.stderr,"metadata: send metadata", len(metadata_request)
        ## Optimization: we know we're currently connected
        self.overlay_bridge.send(permid,METADATA + metadata_request,self.metadata_send_callback)
        
        # BarterCast: add bytes of torrent to BarterCastDB
        # Save exchanged KBs in BarterCastDB
        if permid != None and BARTERCAST_TORRENTS:
            self.overlay_bridge.add_task(lambda:self.olthread_bartercast_torrentexchange(permid, 'uploaded'), 0)
        
        return len(metadata_request)
     
    def olthread_bartercast_torrentexchange(self, permid, up_or_down):
        
        if up_or_down != 'uploaded' and up_or_down != 'downloaded':
            return
        
        bartercastdb = BarterCastDBHandler.getInstance()
        
        torrent_kb = float(self.avg_torrent_size) / 1024
        name = bartercastdb.getName(permid)
        my_permid = bartercastdb.my_permid

        if DEBUG:
            print >> sys.stderr, "bartercast: Torrent (%d KB) %s to/from peer %s" % (torrent_kb, up_or_down, `name`)

        if torrent_kb > 0:
            bartercastdb.incrementItem((my_permid, permid), up_or_down, torrent_kb)
                

    def metadata_send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"metadata: METADATA: error sending to",show_permid_short(permid),exc
            pass

    def read_torrent(self, torrent_path):
        try:
            f = open(torrent_path, "rb")
            torrent_data = f.read()
            f.close()
            torrent_size = len(torrent_data)
            if DEBUG:
                print >> sys.stderr,"metadata: read torrent", `torrent_path`, torrent_size
            if torrent_size > Max_Torrent_Size:
                return None
            return torrent_data
        except:
            print_exc()
            return None


    def addTorrentToDB(self, filename, torrent_hash, metadata, source='BC', extra_info={}, hack=False):
        """ Arno: no need to delegate to olbridge, this is already run by OverlayThread """
        # 03/02/10 Boudewijn: addExternalTorrent now requires a
        # torrentdef, consequently we provide the filename through the
        # extra_info dictionary
        torrentdef = TorrentDef.load(filename)
        if not 'filename' in extra_info:
            extra_info['filename'] = filename
        torrent = self.torrent_db.addExternalTorrent(torrentdef, source, extra_info)
        if torrent is None:
            return

        # Arno, 2008-10-20: XXX torrents are filtered out in the final display stage
        self.launchmany.set_activity(NTFY_ACT_GOT_METADATA,unicode('"'+torrent['name']+'"'),torrent['category'])

        if self.initialized:
            self.num_torrents += 1 # for free disk limitation
        
            if not extra_info:
                self.refreshTrackerStatus(torrent)
            
            if len(self.recently_collected_torrents) < 50:    # Queue of 50
                self.recently_collected_torrents.append(torrent_hash)
            else:
                self.recently_collected_torrents.pop(0)
                self.recently_collected_torrents.append(torrent_hash)
        

    def set_overflow(self, max_num_torrent):
        self.max_num_torrents = self.init_max_num_torrents = max_num_torrent
        
    def delayed_check_overflow(self, delay=2):
        if not self.initialized:
            return
        self.overlay_bridge.add_task(self.check_overflow, delay)
        
    def delayed_check_free_space(self, delay=2):
        self.free_space = self.get_free_space()
        
    def check_overflow(self):    # check if there are too many torrents relative to the free disk space
        if self.num_torrents < 0:
            self.num_torrents = self.torrent_db.getNumberCollectedTorrents()
            #print >> sys.stderr, "**** torrent collectin self.num_torrents=", self.num_torrents

        if DEBUG:
            print >>sys.stderr,"metadata: check overflow: current", self.num_torrents, "max", self.max_num_torrents
        
        if self.num_torrents > self.max_num_torrents:
            num_delete = int(self.num_torrents - self.max_num_torrents*0.95)
            print >> sys.stderr, "** limit space::", self.num_torrents, self.max_num_torrents, num_delete
            self.limit_space(num_delete)
            
    def limit_space(self, num_delete):
        deleted = self.torrent_db.freeSpace(num_delete)
        if deleted:
            self.num_torrents = self.torrent_db.getNumberCollectedTorrents()
            self.free_space = self.get_free_space()
        
        
    def save_torrent(self, infohash, metadata, source='BC', extra_info={}):
        # check if disk is full before save it to disk and database
        if not self.initialized:
            return None

        self.check_overflow()
            
        if self.min_free_space != 0 and (self.free_space - len(metadata) < self.min_free_space or self.num_collected_torrents % 10 == 0):
            self.free_space = self.get_free_space()
            if self.free_space - len(metadata) < self.min_free_space:
                self.warn_disk_full()
                return None
        
        file_name = get_collected_torrent_filename(infohash)
        if DEBUG:
            print >> sys.stderr,"metadata: Storing torrent", sha(infohash).hexdigest(),"in",file_name
        
        save_path = self.write_torrent(metadata, self.torrent_dir, file_name)
        if save_path:
            self.num_collected_torrents += 1
            self.free_space -= len(metadata)
            self.addTorrentToDB(save_path, infohash, metadata, source=source, extra_info=extra_info)
            # check if space is enough and remove old torrents
            
        return file_name
        
        
    def refreshTrackerStatus(self, torrent):
        "Upon the reception of a new discovered torrent, directly check its tracker"
        if DEBUG:
            print >> sys.stderr, "metadata: checking tracker status of new torrent"
        check = TorrentChecking(torrent['infohash'])
        check.start()
        
    def write_torrent(self, metadata, dir, name):
        try:
            if not os.access(dir,os.F_OK):
                os.mkdir(dir)
            save_path = os.path.join(dir, name)
            file = open(save_path, 'wb')
            file.write(metadata)
            file.close()
            if DEBUG:
                print >> sys.stderr,"metadata: write torrent", `save_path`, len(metadata), hash(metadata)
            return save_path
        except:
            print_exc()
            print >> sys.stderr, "metadata: write torrent failed"
            return None

    def valid_metadata(self, infohash, metadata):
        try:
            metainfo = bdecode(metadata)
            tdef = TorrentDef.load_from_dict(metainfo)
            got_infohash = tdef.get_infohash()
            if infohash != got_infohash:
                print >> sys.stderr, "metadata: infohash doesn't match the torrent " + \
                "hash. Required: " + `infohash` + ", but got: " + `got_infohash`
                return False
            return True
        except:
            print_exc()
            #print >> sys.stderr, "problem metadata:", repr(metadata)
            return False
        
    def got_metadata(self, permid, message, selversion):    
        """ receive torrent file from others """
        
        # Arno, 2007-06-20: Disabled the following code. What's this? Somebody sends 
        # us something and we refuse? Also doesn't take into account download help 
        #and remote-query extension.
        
        #if self.upload_rate <= 0:    # if no upload, no download, that's the game
        #    return True    # don't close connection
        
        try:
            message = bdecode(message[1:])
        except:
            print_exc()
            return False
        if not isinstance(message, dict):
            return False
        try:
            infohash = message['torrent_hash']
            if not isValidInfohash(infohash):
                # 19/02/10 Boudewijn: isValidInfohash either returns
                # True or raises a ValueError. So this part of the
                # code will never be reached...
                return False
            
            assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
            assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
            
            #print >>sys.stderr,"metadata: got_metadata: hexinfohash: get_collected_torrent_filename(infohash)

            if not infohash in self.requested_torrents:    # got a torrent which was not requested
                return True
            if self.torrent_db.hasMetaData(infohash):
                return True

            # P2PURL
            goturl = False
            if selversion >= OLPROTO_VER_ELEVENTH:
                if 'metatype' in message and message['metatype'] == URL_MIME_TYPE:
                    try:
                        tdef = TorrentDef.load_from_url(message['metadata'])
                        # Internal storage format is still .torrent file
                        metainfo = tdef.get_metainfo()
                        metadata = bencode(metainfo)
                        goturl = True
                    except:
                        print_exc()
                        return False
                else:
                    metadata = message['metadata']
            else:
                metadata = message['metadata']
                    
            if not self.valid_metadata(infohash, metadata):
                return False
            
            if DEBUG:
                torrent_size = len(metadata)
                if goturl:
                    mdt = "URL"
                else:
                    mdt = "torrent" 
                print >> sys.stderr,"metadata: Recvd",mdt,`infohash`,sha(infohash).hexdigest(), torrent_size
            
            extra_info = {}
            if selversion >= OLPROTO_VER_FOURTH:
                try:
                    extra_info = {'leecher': message.get('leecher', -1),
                              'seeder': message.get('seeder', -1),
                              'last_check_time': message.get('last_check_time', -1),
                              'status':message.get('status', 'unknown')}
                except Exception, msg:
                    print_exc()
                    print >> sys.stderr, "metadata: wrong extra info in msg - ", message
                    extra_info = {}
                
            filename = self.save_torrent(infohash, metadata, extra_info=extra_info)
            self.requested_torrents.remove(infohash)
            
            #if DEBUG:
            #    print >>sys.stderr,"metadata: Was I asked to dlhelp someone",self.dlhelper

            if filename is not None:
                self.notify_torrent_is_in(infohash,metadata,filename)
            
            
            # BarterCast: add bytes of torrent to BarterCastDB
            # Save exchanged KBs in BarterCastDB
            if permid is not None and BARTERCAST_TORRENTS:
                self.overlay_bridge.add_task(lambda:self.olthread_bartercast_torrentexchange(permid, 'downloaded'), 0)
                
                
        except Exception, e:
            print_exc()
            print >> sys.stderr,"metadata: Received metadata is broken",e, message.keys()
            return False
        
        return True

    def notify_torrent_is_in(self,infohash,metadata,filename):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        if self.dlhelper is not None:
            self.dlhelper.metadatahandler_received_torrent(infohash, metadata)
        if self.rquerytorrenthandler is not None:
            self.rquerytorrenthandler.metadatahandler_got_torrent(infohash,metadata,filename)
        
    def get_num_torrents(self):
        return self.num_torrents
    
    def warn_disk_full(self):
        if DEBUG:
            print >> sys.stderr,"metadata: send_meta_req: Disk full!"
        drive,dir = os.path.splitdrive(os.path.abspath(self.torrent_dir))
        if not drive:
            drive = dir
        self.launchmany.set_activity(NTFY_ACT_DISK_FULL, drive)
        
    def get_free_space(self):
        if not self.registered:
            return 0
        try:
            freespace = getfreespace(self.torrent_dir)
            return freespace
        except:
            print >> sys.stderr, "meta: cannot get free space of", self.torrent_dir
            print_exc()
            return 0

    def set_rate(self, rate):
        self.upload_rate = rate * 1024
        
    def set_min_free_space(self, min_free_space):
        self.min_free_space = min_free_space*(2**20)

    def checking_upload_queue(self):
        """ check the upload queue every 5 seconds, and send torrent out if the queue 
            is not empty and the max upload rate is not reached.
            It is used for rate control
        """

        if DEBUG:
            print >> sys.stderr, "metadata: checking_upload_queue, length:", len(self.upload_queue), "now:", ctime(time()), "next check:", ctime(self.next_upload_time)
        if self.upload_rate > 0 and int(time()) >= self.next_upload_time and len(self.upload_queue) > 0:
            task = self.upload_queue.pop(0)
            permid = task['permid']
            infohash = task['infohash']
            torrent_path = task['torrent_path']
            selversion = task['selversion']
            sent_size = self.read_and_send_metadata(permid, infohash, torrent_path, selversion)
            idel = sent_size / self.upload_rate + 1
            self.next_upload_time = int(time()) + idel
            self.overlay_bridge.add_task(self.checking_upload_queue, idel)

    def getRecentlyCollectedTorrents(self, num, selversion):
        """
        This method returns a list of collected torrents. It is called by the 
        method hat creates BC message.
        @change: changed by Rahim. Since overlay version 10, the returned list should contain the swarm size info for the torrents.
        @param num: Maximum length of result list. If num=0 it means that the returned list is unlimited.
        @param selversion: Version of the overlay protocol that two communication nodes agreed on.
        """
        if selversion >= OLPROTO_VER_ELEVENTH: ## Amended list with swarm size info is returned. 
            if not self.initialized:
                return []
            else: 
                collectedList=self.recently_collected_torrents[-1*num:] # this is list of infohashes
                if len(collectedList) >0:
                    swarmSizeList= self.popularity_db.calculateSwarmSize(collectedList, content='Infohash' , toBC=True)
                for index in range(0,len(collectedList)):
                    collectedList[index]=[collectedList[index]]
                    collectedList[index].append(swarmSizeList[index][1]) # appends number of seeders
                    collectedList[index].append(swarmSizeList[index][2]) # appends number of leechers
                    collectedList[index].append(swarmSizeList[index][3]) # appends current time 
                    collectedList[index].append(swarmSizeList[index][4]) # appends 
                return collectedList;
                
        else:
            if not self.initialized:
                return []
            return self.recently_collected_torrents[-1*num:]    # get the last ones

            



