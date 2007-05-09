# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information
import sys
import os
from sha import sha
from time import time, ctime
from traceback import print_exc
from sets import Set

from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *
from Tribler.utilities import isValidInfohash, show_permid_short, sort_dictlist
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler
from Tribler.Overlay.SecureOverlay import OLPROTO_VER_FOURTH
from Tribler.unicode import name2unicode
from Tribler.Category.Category import Category
from Tribler.Dialogs.activities import ACT_GOT_METADATA
from Tribler.TrackerChecking.ManualChecking import SingleManualChecking

DEBUG = True

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

    def getInstance(*args, **kw):
        if MetadataHandler.__single is None:
            MetadataHandler(*args, **kw)
        return MetadataHandler.__single
    getInstance = staticmethod(getInstance)
        
    def register(self, secure_overlay, dlhelper, launchmany, config):
        self.secure_overlay = secure_overlay
        self.rawserver = secure_overlay.rawserver
        self.dlhelper = dlhelper
        self.launchmany = launchmany
        self.config = config
        config_dir = self.config['config_path']
        self.config_dir = os.path.join(config_dir, 'torrent2')    #TODO: user can set it
        self.max_num_torrents = int(self.config['max_torrents'])
        self.upload_rate = 1024 * int(self.config['torrent_collecting_rate'])   # 5KB/s
        self.torrent_db = SynTorrentDBHandler()
        self.num_torrents = -10
        self.recently_collected_torrents = []
        self.upload_queue = []
        self.requested_torrents = Set()
        self.next_upload_time = 0

    def set_rate(self, rate):
        self.upload_rate = rate * 1024

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
            torrent_hash = task['torrent_hash']
            torrent_path = task['torrent_path']
            selversion = task['selversion']
            sent_size = self.read_and_send_metadata(permid, torrent_hash, torrent_path, selversion)
            idel = sent_size / self.upload_rate + 1
            self.next_upload_time = int(time()) + idel
            self.rawserver.add_task(self.checking_upload_queue, idel)

    def getRecentlyCollectedTorrents(self, num):
        return self.recently_collected_torrents[-1*num:]    # get the last ones

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

    def send_metadata_request(self, permid, torrent_hash, selversion=-1):
        if DEBUG:
            print >> sys.stderr,"metadata: Connect to send GET_METADATA to",show_permid_short(permid)
        if not isValidInfohash(torrent_hash):
            return False
        
        if self.torrent_exists(torrent_hash):    # torrent already exists on disk
            return True
        
        try:
            # Optimization: don't connect if we're connected, although it won't 
            # do any harm.
            if selversion == -1: # not currently connected
                self.secure_overlay.connect(permid,lambda e,d,p,s:self.get_metadata_connect_callback(e,d,p,s,torrent_hash))
            else:
                self.get_metadata_connect_callback(None,None,permid,selversion,torrent_hash)
            
        except:
            print_exc(file=sys.stderr)
            return False
        return True

    def torrent_exists(self, torrent_hash):
        # if the torrent is already on disk, put it in db
        
        file_name = sha(torrent_hash).hexdigest()+'.torrent'
        torrent_path = os.path.join(self.config_dir, file_name)
        if not os.path.exists(torrent_path):
            return False
        else:
            metadata = self.read_torrent(torrent_path)
            if not self.valid_metadata(torrent_hash, metadata):
                return False
            self.addTorrentToDB(torrent_path, torrent_hash, metadata, source="BC", extra_info={})
            return True

    def get_metadata_connect_callback(self,exc,dns,permid,selversion,torrent_hash):
        if exc is None:
            if DEBUG:
                print >> sys.stderr,"metadata: Sending GET_METADATA to",show_permid_short(permid)
            ## Create metadata_request according to protocol version
            try:
                metadata_request = bencode(torrent_hash)
                self.secure_overlay.send(permid, GET_METADATA + metadata_request,self.get_metadata_send_callback)
                self.requested_torrents.add(torrent_hash)
            except:
                print_exc(file=sys.stderr)
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
            torrent_hash = bdecode(message[1:])
        except:
            print_exc(file=sys.stderr)
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: error becoding"
            return False
        if not isValidInfohash(torrent_hash):
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: invalid hash"
            return False

        data = self.torrent_db.getTorrent(torrent_hash)
        if not data or not data['torrent_name']:
            return True     # don't close connection
        
        torrent_path = None
        try:
            torrent_path = os.path.join(data['torrent_dir'], data['torrent_name'])
            if not os.path.isfile(torrent_path):
                torrent_path = None
        except:
            print_exc(file=sys.stderr)
            
        if not torrent_path:
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: not torrent path"
            return True
        
        task = {'permid':permid, 'torrent_hash':torrent_hash, 'torrent_path':torrent_path, 'selversion':selversion}
        self.upload_queue.append(task)
        if int(time()) >= self.next_upload_time:
            self.checking_upload_queue()
        
        return True

    def read_and_send_metadata(self, permid, torrent_hash, torrent_path, selversion):
        torrent_data = self.read_torrent(torrent_path)
        if torrent_data:
            if DEBUG:
                print >> sys.stderr,"metadata: sending torrent", `torrent_path`, len(torrent_data)
            torrent = {'torrent_hash':torrent_hash, 
                       'metadata':torrent_data}
            if selversion >= OLPROTO_VER_FOURTH:
                data = self.torrent_db.getTorrent(torrent_hash)
                nleechers = data.get('leecher', -1)
                nseeders = data.get('seeder', -1)
                last_check_time = int(time()) - data.get('last_check_time', 0)
                status = data.get('status', 'unknown')
                
                torrent.update({'leecher':nleechers,
                                'seeder':nseeders,
                                'last_check_time':last_check_time,
                                'status':status})

            return self.do_send_metadata(permid, torrent, selversion)
        else:
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: no torrent data to send"
            return 0

    def do_send_metadata(self, permid, torrent, selversion):
        metadata_request = bencode(torrent)
        if DEBUG:
            print >> sys.stderr,"metadata: send metadata", len(metadata_request)
        ## Optimization: we know we're currently connected
        self.secure_overlay.send(permid,METADATA + metadata_request,self.metadata_send_callback)
        return len(metadata_request)

    def metadata_send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"metadata: METADATA: error sending to",show_permid_short(permid),exc
            pass


    def read_torrent(self, torrent_path):
        try:
            file = open(torrent_path, "rb")
            torrent_data = file.read()
            file.close()
            torrent_size = len(torrent_data)
            if DEBUG:
                print >> sys.stderr,"metadata: read torrent", `torrent_path`, torrent_size
            if torrent_size > Max_Torrent_Size:
                return None
            return torrent_data
        except:
            print_exc(file=sys.stderr)
            return None


    def addTorrentToDB(self, src, torrent_hash, metadata, source='BC', extra_info={}, hack=False):
        
        metainfo = bdecode(metadata)
        namekey = name2unicode(metainfo)  # convert info['name'] to type(unicode)
        info = metainfo['info']
        
        torrent = {}
        torrent['torrent_dir'], torrent['torrent_name'] = os.path.split(src)
        
        torrent_info = {}
        torrent_info['name'] = info.get(namekey, '')
        length = 0
        nf = 0
        if info.has_key('length'):
            length = info.get('length', 0)
            nf = 1
        elif info.has_key('files'):
            for li in info['files']:
                nf += 1
                if li.has_key('length'):
                    length += li['length']
        torrent_info['length'] = length
        torrent_info['num_files'] = nf
        torrent_info['announce'] = metainfo.get('announce', '')
        torrent_info['announce-list'] = metainfo.get('announce-list', '')
        torrent_info['creation date'] = metainfo.get('creation date', 0)
        torrent['info'] = torrent_info
        torrent['category'] = Category.getInstance().calculateCategory(info, torrent_info['name'])
        torrent["ignore_number"] = 0
        torrent["retry_number"] = 0
        if hack:
            torrent["seeder"] = 1
            torrent["leecher"] = 1
            torrent["status"] = "good"
        else:
            torrent["seeder"] = extra_info.get('seeder', -1)
            torrent["leecher"] = extra_info.get('leecher', -1)
            other_last_check = extra_info.get('last_check_time', -1)
            if other_last_check >= 0:
                torrent["last_check_time"] = int(time()) - other_last_check
            else:
                torrent["last_check_time"] = 0
            torrent["status"] = extra_info.get('status', "unknown")
        
        torrent["source"] = source
        torrent["inserttime"] = long(time())

        #if (torrent['category'] != []):
        #    print '### one torrent added from MetadataHandler: ' + str(torrent['category']) + ' ' + torrent['torrent_name'] + '###'
        
        self.torrent_db.addTorrent(torrent_hash, torrent, new_metadata=True, updateFlag=True)
        self.num_torrents += 1
        self.check_overflow()
        self.torrent_db.sync()
        
        if not extra_info:
            torrent.update({'infohash':torrent_hash})
            self.refreshTrackerStatus(torrent)
        
        if len(self.recently_collected_torrents) < 50:    # Queue of 50
            self.recently_collected_torrents.append(torrent_hash)
        else:
            self.recently_collected_torrents.pop(0)
            self.recently_collected_torrents.append(torrent_hash)
        
        # Arno: show activity
        self.launchmany.set_activity(ACT_GOT_METADATA,unicode('"'+torrent_info['name']+'"'))
        
    def set_overflow(self, max_num_torrent):
        self.max_num_torrents = max_num_torrent
        
    def delayed_check_overflow(self, delay=2):
        rawserver = self.secure_overlay.rawserver    # not a good way, but simple
        rawserver.add_task(self.check_overflow, delay)
        
    def check_overflow(self):    # check if torrents are more than enough
        if self.num_torrents < 0:
            self.num_torrents = len(self.torrent_db.getCollectedTorrents())
            #print >> sys.stderr, "** torrent collectin self.num_torrents=", self.num_torrents
        
        if self.num_torrents > self.max_num_torrents:
            num_delete = int(self.num_torrents - self.max_num_torrents*0.95)
            #print >> sys.stderr, "** limit space::", self.num_torrents, self.max_num_torrents, num_delete
            self.limit_space(num_delete)
            
    def limit_space(self, num_delete):
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
            
            date = torrent.get('creation date', 0)
            age = max(int(time())-date, 24*60*60)
            rel_date = min(age/(24*60*60), 1000)    # [1, 1000]
            
            weight = status*1000 + retry_number*100 + rel_date - relevance/10 - leechers - 3*seeders
            return weight
        
        torrent_list = self.torrent_db.getCollectedTorrents(light=False)
        self.num_torrents = len(torrent_list)    # sync point
        for i in xrange(len(torrent_list)):
            torrent = torrent_list[i]
            torrent['weight'] = get_weight(torrent)
        torrent_list = sort_dictlist(torrent_list, 'weight', order='decrease')
        
        for torrent in torrent_list[:num_delete]:
            infohash = torrent['infohash']
            self.torrent_db.deleteTorrent(infohash, delete_file=True, updateFlag=True)
            self.num_torrents -= 1
        del torrent_list
        
    def save_torrent(self, torrent_hash, metadata, source='BC', extra_info={}):
        file_name = self.get_filename(torrent_hash)
        if DEBUG:
            print >> sys.stderr,"metadata: Storing torrent", sha(torrent_hash).hexdigest(),"in",file_name
        save_path = os.path.join(self.config_dir, file_name)
        self.write_torrent(metadata, self.config_dir, file_name)
        self.addTorrentToDB(save_path, torrent_hash, metadata, source=source, extra_info=extra_info)
        
    def refreshTrackerStatus(self, torrent):
        "Upon the reception of a new discovered torrent, directly check its tracker"
        if DEBUG:
            print >> sys.stderr, "metadata: checking tracker status of new torrent"
        check = SingleManualChecking(torrent)
        check.start()
        
    def get_filename(self,torrent_hash):
        file_name = sha(torrent_hash).hexdigest()+'.torrent'
        #_path = os.path.join(self.config_dir, file_name)
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
        except:
            print_exc(file=sys.stderr)
            print >> sys.stderr, "metadata: write torrent failed"

    def valid_metadata(self, torrent_hash, metadata):
        try:
            metainfo = bdecode(metadata)
            infohash = sha(bencode(metainfo['info'])).digest()
            if infohash != torrent_hash:
                print >> sys.stderr, "metadata: infohash doesn't match the torrent " + \
                "hash. Required: " + `torrent_hash` + ", but got: " + `infohash`
                return False
            return True
        except:
            print_exc()
            print >> sys.stderr, "problem metadata:", repr(metadata)
            return False
        
    def got_metadata(self, message, selversion):    # receive torrent file from others
        if self.upload_rate <= 0:    # if no upload, no download, that's the game
            return True    # don't close connection
        
        try:
            message = bdecode(message[1:])
        except:
            print_exc(file=sys.stderr)
            return False
        if not isinstance(message, dict):
            return False
        try:
            torrent_hash = message['torrent_hash']
            if not isValidInfohash(torrent_hash):
                return False

            if not torrent_hash in self.requested_torrents:    # got a torrent which was not requested
                return True
            if self.torrent_db.hasMetaData(torrent_hash):
                return True
            
            metadata = message['metadata']
            if not self.valid_metadata(torrent_hash, metadata):
                return False
            if DEBUG:
                torrent_size = len(metadata)
                print >> sys.stderr,"metadata: Recvd torrent", `torrent_hash`, sha(torrent_hash).hexdigest(), torrent_size
            
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
                
            self.save_torrent(torrent_hash, metadata, extra_info=extra_info)
            self.requested_torrents.remove(torrent_hash)
            
            if DEBUG:
                print >>sys.stderr,"metadata: Was I asked to dlhelp someone",self.dlhelper
            
            if self.dlhelper is not None:
                self.dlhelper.call_dlhelp_task(torrent_hash, metadata)
        except Exception, msg:
            print_exc(file=sys.stderr)
            print >> sys.stderr,"metadata: Received metadata is broken", msg
        
        return True
        