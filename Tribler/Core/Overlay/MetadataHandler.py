# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information
import sys
import os
from sha import sha
from time import time, ctime
from traceback import print_exc, print_stack
from sets import Set

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.Utilities.utilities import isValidInfohash, show_permid_short, sort_dictlist, bin2str
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FOURTH
from Tribler.Core.Utilities.unicode import metainfoname2unicode
from Tribler.Category.Category import Category
from Tribler.Core.simpledefs import *
from Tribler.TrackerChecking.ManualChecking import SingleManualChecking
from Tribler.Core.osutils import getfreespace
from Tribler.Core.CacheDBHandler import BarterCastDBHandler

from threading import currentThread
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
        if self.min_free_space <= 0:
            self.min_free_space = 200*(2**20)    # at least 1 MB left on disk
        self.config_dir = os.path.abspath(self.config['state_dir'])
        self.torrent_dir = os.path.abspath(self.config['torrent_collecting_dir'])
        assert os.path.isdir(self.torrent_dir)
        self.free_space = self.get_free_space()
        print "Available space for database and collecting torrents: %d MB," % (self.free_space/(2**20)), "Min free space", self.min_free_space/(2**20), "MB"
        self.max_num_torrents = self.init_max_num_torrents = int(self.config['torrent_collecting_max_torrents'])
        self.upload_rate = 1024 * int(self.config['torrent_collecting_rate'])   # 5KB/s
        self.num_collected_torrents = 0
        self.recently_collected_torrents = []
        self.upload_queue = []
        self.requested_torrents = Set()
        self.next_upload_time = 0
        self.initialized = True
        self.rquerytorrenthandler = None

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
                print >> sys.stderr,"metadata: Got METADATA",len(message),show_permid_short(permid),selversion
            return self.got_metadata(message, selversion)
        else:
            if DEBUG:
                print >> sys.stderr,"metadata: UNKNOWN OVERLAY MESSAGE", ord(t)
            return False

    def send_metadata_request(self, permid, infohash, selversion=-1, caller="BC"):
        if DEBUG:
            print >> sys.stderr,"metadata: Connect to send GET_METADATA to",show_permid_short(permid)
        if not isValidInfohash(infohash):
            return False
        
        metadata = self.torrent_exists(infohash)
        if metadata is not None:    # torrent already exists on disk
            if DEBUG:
                print >> sys.stderr,"metadata: send_meta_req: Already on disk??!"
            self.notify_torrent_is_in(infohash, metadata)
            return True
        
        if caller == "dlhelp":
            self.requested_torrents.add(infohash)
        
        if self.free_space - self.avg_torrent_size < self.min_free_space:   # no space to collect
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
        
        file_name = sha(infohash).hexdigest()+'.torrent'
        torrent_path = os.path.join(self.torrent_dir, file_name)
        if not os.path.exists(torrent_path):
            return None
        else:
            metadata = self.read_torrent(torrent_path)
            if not self.valid_metadata(infohash, metadata):
                return None
            self.addTorrentToDB(torrent_path, infohash, metadata, source="BC", extra_info={})
            return metadata

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
                print >> sys.stderr,"metadata: GET_METADATA: not in database"
            return True    # don't close connection because I don't have the torrent
        torrent_file_name, status_id = res
        if status_id == self.torrent_db._getStatusID('dead'):
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: Torrent was dead"
            return True
        if not torrent_file_name:
            return True
        torrent_path = os.path.join(self.torrent_dir, torrent_file_name)
        if not os.path.isfile(torrent_path):
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: not existing", res, torrent_path
            return True
#        
#        data = self.torrent_db.getTorrent(infohash)
#        if not data or not data['torrent_name']:
#            return True     # don't close connection
#        live = data.get('status', 'unknown')
#        #print "**************** check live before send metadata", live
#        if live == 'dead':
#            return True    # don't send dead torrents around
#        
#        torrent_path = None
#        try:
#            torrent_path = os.path.join(data['torrent_dir'], data['torrent_name'])
#            if not os.path.isfile(torrent_path):
#                torrent_path = None
#        except:
#            print_exc()
#            
#        if not torrent_path:
#            if DEBUG:
#                print >> sys.stderr,"metadata: GET_METADATA: not torrent path"
#            return True
        
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
            torrent = {'torrent_hash':infohash, 
                       'metadata':torrent_data}
            if selversion >= OLPROTO_VER_FOURTH:
                data = self.torrent_db.getTorrent(infohash)
                nleechers = data.get('leecher', -1)
                nseeders = data.get('seeder', -1)
                last_check_time = int(time()) - data.get('last_check_time', 0)
                status = data.get('status', 'unknown')
                
                torrent.update({'leecher':nleechers,
                                'seeder':nseeders,
                                'last_check_time':last_check_time,
                                'status':status})

            return self.do_send_metadata(permid, torrent, selversion)
        else:    # deleted before sending it
            self.torrent_db.deleteTorrent(infohash, delete_file=True, updateFlag=True)
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
            
            bartercastdb = BarterCastDBHandler.getInstance()
            
            torrent_kb = float(self.avg_torrent_size) / 1024
            name = bartercastdb.getName(permid)
            my_permid = bartercastdb.my_permid

            if DEBUG:
                print >> sys.stdout, "barter: Torrent (%d KB) sent to peer %s (PermID = %s)" % (torrent_kb, name, permid)

            if torrent_kb > 0:
                bartercastdb.incrementItem((my_permid, permid), 'uploaded', torrent_kb)
        
        return len(metadata_request)
        

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
        torrent = self.torrent_db.addExternalTorrent(filename, source, extra_info)

        
        self.launchmany.set_activity(NTFY_ACT_GOT_METADATA,unicode('"'+torrent['name']+'"'))

        if self.initialized:
            self.num_torrents += 1 # for free disk limitation
            self.check_overflow()
        
            if not extra_info:
                self.refreshTrackerStatus(torrent)
            
            if len(self.recently_collected_torrents) < 50:    # Queue of 50
                self.recently_collected_torrents.append(torrent_hash)
            else:
                self.recently_collected_torrents.pop(0)
                self.recently_collected_torrents.append(torrent_hash)
        
#
#    def addTorrentToDB(self, filename, torrent_hash, metadata, source='BC', extra_info={}, hack=False):
#        
#        metainfo = bdecode(metadata)
#        namekey = metainfoname2unicode(metainfo)  # convert info['name'] to type(unicode)
#        info = metainfo['info']
#        
#        torrent = {}
#        torrent['torrent_dir'], torrent['torrent_name'] = os.path.split(filename)
#        
#        torrent_info = {}
#        torrent_info['name'] = info.get(namekey, '')
#        
#        catobj = Category.getInstance(self.config['install_dir'], self.config['state_dir'])
#        torrent['category'] = catobj.calculateCategory(info, torrent_info['name'])
#        
#        #if DEBUG:
#        #    print >>sys.stderr,"metadata: Category for",`torrent_info['name']`,torrent['category']
#        
#        for cat in torrent['category']:
#            rank = catobj.getCategoryRank(cat)
#            if rank == -1:
#                if DEBUG:
#                    print >>sys.stderr,"metadata: Got torrent",`torrent_info['name']`,"from banned category",cat,", discarded it."
#                return
#        
#        length = 0
#        nf = 0
#        if info.has_key('length'):
#            length = info.get('length', 0)
#            nf = 1
#        elif info.has_key('files'):
#            for li in info['files']:
#                nf += 1
#                if li.has_key('length'):
#                    length += li['length']
#        torrent_info['length'] = length
#        torrent_info['num_files'] = nf
#        torrent_info['announce'] = metainfo.get('announce', '')
#        torrent_info['announce-list'] = metainfo.get('announce-list', '')
#        torrent_info['creation date'] = metainfo.get('creation date', 0)
#        torrent['info'] = torrent_info
#        
#        torrent["ignore_number"] = 0
#        torrent["retry_number"] = 0
#        if hack:
#            torrent["seeder"] = 1
#            torrent["leecher"] = 1
#            torrent["status"] = "good"
#            torrent["last_check_time"] = 0
#        else:
#            torrent["seeder"] = extra_info.get('seeder', -1)
#            torrent["leecher"] = extra_info.get('leecher', -1)
#            other_last_check = extra_info.get('last_check_time', -1)
#            if other_last_check >= 0:
#                torrent["last_check_time"] = int(time()) - other_last_check
#            else:
#                torrent["last_check_time"] = 0
#            torrent["status"] = extra_info.get('status', "unknown")
#        
#        torrent["source"] = source
#        torrent["inserttime"] = long(time())
#
#        #if (torrent['category'] != []):
#        #    print '### one torrent added from MetadataHandler: ' + str(torrent['category']) + ' ' + torrent['torrent_name'] + '###'
#        
#        self.torrent_db.addTorrent(torrent_hash, torrent, new_metadata=True)#, updateFlag=True)
#        self.torrent_db.sync()

    def set_overflow(self, max_num_torrent):
        self.max_num_torrents = self.init_max_num_torrents = max_num_torrent
        
    def delayed_check_overflow(self, delay=2):
        if not self.initialized:
            return
        self.overlay_bridge.add_task(self.check_overflow, delay)
        
    def delayed_check_free_space(self, delay=2):
        self.free_space = self.get_free_space()
        #if not self.initialized:
        #    return
        #self.overlay_bridge.add_task(self.check_free_space, delay)
        
    def check_overflow(self):    # check if there are too many torrents relative to the free disk space
        if self.num_torrents < 0:
            collected_infohashes = self.torrent_db.getCollectedTorrentHashes()
            self.num_torrents = len(collected_infohashes)
            #print >> sys.stderr, "**** torrent collectin self.num_torrents=", self.num_torrents

        if DEBUG:
            print >>sys.stderr,"metadata: check overflow: current", self.num_torrents, "max", self.max_num_torrents
        
        if self.num_torrents > self.max_num_torrents:
            num_delete = int(self.num_torrents - self.max_num_torrents*0.95)
            print "** limit space::", self.num_torrents, self.max_num_torrents, num_delete
            self.limit_space(num_delete)
            
    def limit_space(self, num_delete):
        return 
        # TODO: 
        def get_weight(torrent):
            # policy of removing torrent:
            # status*1000 + retry_number*100 - relevance/10 + date - leechers - 3*seeders
            # The bigger, the more possible to delete
            
            status_key = torrent.get('status', 'dead')
            leechers = min(torrent.get('leecher', -1), 1000)
            seeders = min(torrent.get('seeder', -1), 1000)
            
            status_value = {'dead':2, 'unknown':1, 'good':0}
            status = status_value.get(status_key, 1)
            
            retry_number = min(torrent.get('retry_number', 0), 10)
            
            relevance = min(torrent.get('relevance', 0), 25000)
            
            info = torrent.get('info',{})
            cdate = info.get('creation date', '0')
            try:
                date = int(cdate)
            except:
                cdate = torrent.get('inserttime',0)
                try:
                    date = int(cdate)
                except:
                    date = 0
            age = max(int(time())-date, 24*60*60)
            rel_date = min(age/(24*60*60), 1000)    # [1, 1000]
            
            weight = status*1000 + retry_number*100 + rel_date - relevance/10 - leechers - 3*seeders
            return weight
        
        collected_infohashes = self.torrent_db.getCollectedTorrentHashes()
        self.num_torrents = len(collected_infohashes)    # sync point

        if DEBUG:
            print >>sys.stderr,"metadata: limit space: num", self.num_torrents,"max", self.max_num_torrents

        weighted_infohashes = []
        for infohash in collected_infohashes:
            torrent = self.torrent_db.getTorrent(infohash)
            weight = get_weight(torrent)
            weighted_infohashes.append((weight,infohash))
        weighted_infohashes.sort()

        for (weight,infohash) in weighted_infohashes[-num_delete:]:
            deleted = self.torrent_db.deleteTorrent(infohash, delete_file=True, updateFlag=True)
            if deleted > 0:
                self.num_torrents -= 1
            if DEBUG:
                print >>sys.stderr,"metadata: limit space: delete torrent, succeeded?", deleted, self.num_torrents,weight

        if num_delete > 0:
            self.free_space = self.get_free_space()
        
#===============================================================================
#    def check_free_space(self):
#        self.free_space = self.get_free_space()
#        if self.free_space < self.min_free_space < self.free_space + 2:    
#            # no enough space caused by this module, removing old torrents
#            # if the disk is suddenly used a lot, it may be other reason, so we stop removing torrents
#            if self.num_torrents >= 0:    # wait for loading it before deleting
#                space_need = self.min_free_space - self.free_space
#                num2del = 1 + space_need / (25*(2**10))    # how many torrents to del, assume each torrent is 25K
#                self.max_num_torrents = self.num_torrents - num2del
#                if DEBUG:
#                    print >> sys.stderr, "meta: disk overflow when save_torrent", self.free_space/(2**20), \
#                        self.min_free_space/(2**20), num2del, self.num_torrents, self.max_num_torrents
#                if self.max_num_torrents > 0:
#                    self.check_overflow()
#        # always change back
#        self.max_num_torrents = self.init_max_num_torrents
#===============================================================================
        
    def save_torrent(self, infohash, metadata, source='BC', extra_info={}):
        if not self.initialized:
            return

#        if self.free_space <= self.min_free_space or self.num_collected_torrents % 10 == 0:
#            self.check_free_space()
            
        if self.free_space - len(metadata) < self.min_free_space or self.num_collected_torrents % 10 == 0:
            self.free_space = self.get_free_space()
            if self.free_space - len(metadata) < self.min_free_space:
                self.warn_disk_full()
                return
        
        file_name = self.get_filename(infohash)
        if DEBUG:
            print >> sys.stderr,"metadata: Storing torrent", sha(infohash).hexdigest(),"in",file_name
        
        save_path = self.write_torrent(metadata, self.torrent_dir, file_name)
        if save_path:
            self.num_collected_torrents += 1
            self.free_space -= len(metadata)
            self.addTorrentToDB(save_path, infohash, metadata, source=source, extra_info=extra_info)
            # check if space is enough and remove old torrents
        
        
    def refreshTrackerStatus(self, torrent):
        "Upon the reception of a new discovered torrent, directly check its tracker"
        if DEBUG:
            print >> sys.stderr, "metadata: checking tracker status of new torrent"
        check = SingleManualChecking(torrent,self.launchmany.session)
        check.start()
        
    def get_filename(self,infohash):
        # Arno: Better would have been the infohash in hex.
        file_name = sha(infohash).hexdigest()+'.torrent'
        #_path = os.path.join(self.torrent_dir, file_name)
        #if os.path.exists(_path):
            # assign a name for the torrent. add a timestamp if it exists.
            #file_name = str(time()) + '_' + file_name 
        return file_name
        # exceptions will be handled by got_metadata()
        
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
            got_infohash = sha(bencode(metainfo['info'])).digest()
            if infohash != got_infohash:
                print >> sys.stderr, "metadata: infohash doesn't match the torrent " + \
                "hash. Required: " + `infohash` + ", but got: " + `got_infohash`
                return False
            return True
        except:
            print_exc()
            print >> sys.stderr, "problem metadata:", repr(metadata)
            return False
        
    def got_metadata(self, message, selversion):    
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
                return False

            if not infohash in self.requested_torrents:    # got a torrent which was not requested
                return True
            if self.torrent_db.hasMetaData(infohash):
                return True
            
            metadata = message['metadata']
            if not self.valid_metadata(infohash, metadata):
                return False
            if DEBUG:
                torrent_size = len(metadata)
                print >> sys.stderr,"metadata: Recvd torrent", `infohash`, sha(infohash).hexdigest(), torrent_size
            
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
                
            self.save_torrent(infohash, metadata, extra_info=extra_info)
            self.requested_torrents.remove(infohash)
            
            if DEBUG:
                print >>sys.stderr,"metadata: Was I asked to dlhelp someone",self.dlhelper

            self.notify_torrent_is_in(infohash,metadata)
            
            
            # BarterCast: add bytes of torrent to BarterCastDB
            # Save exchanged KBs in BarterCastDB
            if permid != None and BARTERCAST_TORRENTS:
                
                bartercastdb = BarterCastDBHandler.getInstance()
                                
                torrent_kb = float(self.avg_torrent_size) / 1024
                name = bartercastdb.getName(permid)
                my_permid = bartercastdb.my_permid

                if DEBUG:
                    print >> sys.stdout, "barter: Torrent (%d KB) received from peer %s (PermID = %s)" % (torrent_kb, name, permid)

                if torrent_kb > 0:
                    bartercastdb.incrementItem((my_permid, permid), 'downloaded', torrent_kb)
            
            
                
        except Exception, e:
            print_exc()
            print >> sys.stderr,"metadata: Received metadata is broken",e, message.keys()
            return False
        
        return True

    def notify_torrent_is_in(self,infohash,metadata):
        if self.dlhelper is not None:
            self.dlhelper.metadatahandler_received_torrent(infohash, metadata)
        if self.rquerytorrenthandler is not None:
            self.rquerytorrenthandler.metadatahandler_got_torrent(infohash,metadata)
        
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
            freespace = getfreespace(self.config_dir)
            return freespace
        except:
            print >> sys.stderr, "meta: cannot get free space of", self.config_dir
            print_exc()
            return 0

    def set_rate(self, rate):
        self.upload_rate = rate * 1024
        
    def set_min_free_space(self, min_free_space):
        self.min_free_space = max(1, min_free_space)*(2**20)    # at least 1 MB

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

    def getRecentlyCollectedTorrents(self, num):
        if not self.initialized:
            return []
        return self.recently_collected_torrents[-1*num:]    # get the last ones

