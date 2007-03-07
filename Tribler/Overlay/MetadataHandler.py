# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information
import sys
import os
from sha import sha
from time import time, ctime
from traceback import print_exc

from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *
from Tribler.utilities import isValidInfohash, show_permid_short, sort_dictlist
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler
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
        
    def register(self, secure_overlay, dlhelper, launchmany, config_dir, max_num_torrents):
        self.secure_overlay = secure_overlay
        self.dlhelper = dlhelper
        self.launchmany = launchmany
        self.config_dir = os.path.join(config_dir, 'torrent2')    #TODO: user can set it
        self.torrent_db = SynTorrentDBHandler()
        self.num_torrents = -1
        self.max_num_torrents = max_num_torrents

    def handleMessage(self,permid,selversion,message):
        
        t = message[0]
        
        if t == GET_METADATA:
            if DEBUG:
                print >> sys.stderr,"metadata: Got GET_METADATA",len(message),show_permid_short(permid)
            return self.send_metadata(permid, message, selversion)
        elif t == METADATA:
            if DEBUG:
                print >> sys.stderr,"metadata: Got METADATA",len(message)
            return self.got_metadata(permid, message, selversion)
        else:
            if DEBUG:
                print >> sys.stderr,"metadata: UNKNOWN OVERLAY MESSAGE", ord(t)
            return False

    def send_metadata_request(self, permid, torrent_hash, selversion=-1):
        if DEBUG:
            print >> sys.stderr,"metadata: Connect to send GET_METADATA to",show_permid_short(permid)
        if not isValidInfohash(torrent_hash):
            return False
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


    def get_metadata_connect_callback(self,exc,dns,permid,selversion,torrent_hash):
        if exc is None:
            if DEBUG:
                print >> sys.stderr,"metadata: Sending GET_METADATA to",show_permid_short(permid)
            ## Create metadata_request according to protocol version
            try:
                metadata_request = bencode(torrent_hash)
                self.secure_overlay.send(permid, GET_METADATA + metadata_request,self.get_metadata_send_callback)
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
            pass    # TODO: Log
        
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

        torrent_path = self.find_torrent(torrent_hash)
        if not torrent_path:
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: not torrent path"
            return False
        torrent_data = self.read_torrent(torrent_path)
        if torrent_data:
            if DEBUG:
                print >> sys.stderr,"metadata: sending torrent", torrent_path, len(torrent_data)
            self.do_send_metadata(permid, torrent_hash, torrent_data, selversion)
        else:
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: no torrent data to send"
            pass
        return True
    
    def do_send_metadata(self, permid, torrent_hash, torrent_data, selversion):
        torrent = {'torrent_hash':torrent_hash, 'metadata':torrent_data}
        metadata_request = bencode(torrent)
        if DEBUG:
            print >> sys.stderr,"metadata: send metadata", len(metadata_request)
        ## Optimization: we know we're currently connected
        self.secure_overlay.send(permid,METADATA + metadata_request,self.metadata_send_callback)

    def metadata_send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"metadata: METADATA: error sending to",show_permid_short(permid),exc
            pass

    def find_torrent(self, torrent_hash):
        """ lookup torrent file and return torrent path """
        
        data = self.torrent_db.getTorrent(torrent_hash)
        if not data:
            return None
        try:
            filepath = os.path.join(data['torrent_dir'], data['torrent_name'])
            if os.path.isfile(filepath):
                return filepath
        except:
            print_exc(file=sys.stderr)
            return None

    def read_torrent(self, torrent_path):
        try:
            file = open(torrent_path, "rb")
            torrent_data = file.read()
            file.close()
            torrent_size = len(torrent_data)
            if DEBUG:
                print >> sys.stderr,"metadata: read torrent", torrent_path, torrent_size
            if torrent_size > Max_Torrent_Size:
                return None
            return torrent_data
        except:
            print_exc(file=sys.stderr)
            return None


    def addTorrentToDB(self, src, torrent_hash, metadata):
        
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
        torrent["last_check_time"] = long(time())
        torrent["retry_number"] = 0
        torrent["seeder"] = -1
        torrent["leecher"] = -1
        torrent["status"] = "unknown"
        #if (torrent['category'] != []):
        #    print '### one torrent added from MetadataHandler: ' + str(torrent['category']) + ' ' + torrent['torrent_name'] + '###'
        
        self.torrent_db.addTorrent(torrent_hash, torrent, new_metadata=True, updateFlag=True)
        self.check_overflow()
        self.torrent_db.sync()
        
        torrent.update({'infohash':torrent_hash})
        self.refreshTrackerStatus(torrent)
        
        # Arno: show activity
        self.launchmany.set_activity(ACT_GOT_METADATA,unicode('"'+torrent_info['name']+'"'))
        
    def check_overflow(self, update=True):    # check if torrents are more than enough
        if self.num_torrents < 0:
            self.torrent_list = self.torrent_db.getRecommendedTorrents(light=True)
            self.num_torrents = len(self.torrent_list)
            self.check_overflow(update=False)    # check at start time
        
        self.num_torrents += 1
        if self.num_torrents > self.max_num_torrents:
            # get current torrent list again
            if update:
                self.torrent_list = self.torrent_db.getRecommendedTorrents(light=True)
                self.num_torrents = len(self.torrent_list)
            if self.num_torrents > self.max_num_torrents:
                self.limit_space()
            
    def limit_space(self):
        def get_weight(torrent):
            # policy of removing torrent:
            # status*10**7 + retry_number(max 99)*10**5 + (99-relevance(max 99)*10**3 + date (max 999)
            
            status_key = torrent.get('status', 'dead')
            status_value = {'dead':2, 'unknown':1, 'good':0}
            status = status_value.get(status_key, 2)
            
            retry_number = min(torrent.get('retry_number', 0), 99)
            
            relevance = min(torrent.get('relevance', 0), 99)
            
            info = torrent.get('info', {})
            date = info.get('creation date', 0)
            rel_date = min(int((time() - date)/(24*60*60)), 999)
            
            weight = status*10**7 + retry_number*10**5 + (99-relevance)*10**3 + rel_date
            return weight
        
        for i in xrange(len(self.torrent_list)):
            torrent = self.torrent_list[i]
            torrent['weight'] = get_weight(torrent)
        self.torrent_list = sort_dictlist(self.torrent_list, 'weight', order='decrease')
        num_delete = self.num_torrents - self.max_num_torrents + self.max_num_torrents / 10
        if num_delete <= 0:
            num_delete = 1
        for torrent in self.torrent_list[:num_delete]:
            infohash = torrent['infohash']
            self.torrent_db.deleteTorrent(infohash, delete_file=True, updateFlag=True)
                    
        
    def save_torrent(self, torrent_hash, metadata):
        file_name = self.get_filename(torrent_hash)
        if DEBUG:
            print >> sys.stderr,"metadata: Storing torrent", sha(torrent_hash).hexdigest(),"in",file_name
        #TODO: 
        save_path = os.path.join(self.config_dir, file_name)
        self.addTorrentToDB(save_path, torrent_hash, metadata)
        self.write_torrent(metadata, self.config_dir, file_name)
        
    def refreshTrackerStatus(self, torrent):
        "Upon the reception of a new discovered torrent, directly check its tracker"
        if DEBUG:
            print >> sys.stderr, "metadata: checking tracker status of new torrent"
        check = SingleManualChecking(torrent)
        check.start()
        
    def get_filename(self,torrent_hash):
        # assign a name for the torrent. add a timestamp if it exists.
        file_name = sha(torrent_hash).hexdigest()+'.torrent'
        _path = os.path.join(self.config_dir, file_name)
        if os.path.exists(_path):
            file_name = str(time()) + '_' + file_name 
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
                print >> sys.stderr,"metadata: write torrent", save_path, len(metadata), hash(metadata)
        except:
            print_exc(file=sys.stderr)
            print >> sys.stderr, "metadata: write torrent failed"

    def valid_metadata(self, torrent_hash, metadata):
        metainfo = bdecode(metadata)
        infohash = sha(bencode(metainfo['info'])).digest()
        if infohash != torrent_hash:
            print >> sys.stderr, "metadata: infohash doesn't match the torrent " + \
            "hash. Required: " + `torrent_hash` + ", but got: " + `infohash`
            return False
        return True
        
    def got_metadata(self, permid, message, selversion):    # receive torrent file from others
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
            metadata = message['metadata']
            if not self.valid_metadata(torrent_hash, metadata):
                return False
            if DEBUG:
                torrent_size = len(metadata)
                print >> sys.stderr,"metadata: Recvd torrent", sha(torrent_hash).hexdigest(), torrent_size
            self.save_torrent(torrent_hash, metadata)
            if self.dlhelper is not None:
                self.dlhelper.call_dlhelp_task(torrent_hash, metadata)
        except Exception, msg:
            print_exc(file=sys.stderr)
            print >> sys.stderr,"metadata: Received metadata is broken", msg
            return False
        
        return True
        

