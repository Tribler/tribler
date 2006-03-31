# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information
import sys
import md5
import os
from sha import sha
from time import time, ctime
from traceback import print_exc

from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *
from Tribler.utilities import isValidInfohash, show_permid
from Tribler.CacheDB.CacheDBHandler import TorrentDBHandler

# Python no recursive imports?
# from overlayswarm import overlay_infohash
overlay_infohash = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'


DEBUG = False
## Arno: FIXME: 8MB too large, IMHO.
Max_Torrent_Size = 8*1024*1024    # 8MB torrent = about 80G files

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
        
    def register(self, secure_overlay, dlhelper, launchmany, config_dir):
        self.secure_overlay = secure_overlay
        self.dlhelper = dlhelper
        self.config_dir = os.path.join(config_dir, 'torrent2')    #TODO: user can set it
        self.torrent_db = TorrentDBHandler()

    def handleMessage(self, permid, message):
        
        t = message[0]
        
        if t == GET_METADATA:
            if DEBUG:
                print >> sys.stderr,"metadata: Got GET_METADATA",len(message),show_permid(permid)
            return self.send_metadata(permid, message)
        elif t == METADATA:
            if DEBUG:
                print >> sys.stderr,"metadata: Got METADATA",len(message)
            return self.got_metadata(permid, message)
        else:
            if DEBUG:
                print >> sys.stderr,"metadata: UNKNOWN OVERLAY MESSAGE", ord(t)
            return False

    def send_metadata_request(self, permid, torrent_hash):
        if not isValidInfohash(torrent_hash):
            return False
        try:
            metadata_request = bencode(torrent_hash)
            self.secure_overlay.addTask(permid, GET_METADATA + metadata_request)
        except:
            return False
        return True
        

    def send_metadata(self, conn, message):
        try:
            torrent_hash = bdecode(message[1:])
        except:
            print_exc()
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
            self.do_send_metadata(conn, torrent_hash, torrent_data)
        else:
            if DEBUG:
                print >> sys.stderr,"metadata: GET_METADATA: no torrent data to send"
            pass
        return True
    
    def do_send_metadata(self, permid, torrent_hash, torrent_data):
        torrent = {'torrent_hash':torrent_hash, 'metadata':torrent_data}
        metadata_request = bencode(torrent)
        if DEBUG:
            print >> sys.stderr,"metadata: send metadata", len(metadata_request)
        self.secure_overlay.addTask(permid,METADATA + metadata_request)

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
            if DEBUG:
                print >> sys.stderr,"metadata: sending torrent", torrent_size, md5.new(torrent_data).hexdigest()
            return torrent_data
        except:
            return None


    def addTorrentToDB(self, src, torrent_hash, metadata):
        
        metainfo = bdecode(metadata)
        info = metainfo['info']
        
        torrent = {}
        torrent['torrent_dir'], torrent['torrent_name'] = os.path.split(src)
        
        torrent_info = {}
        torrent_info['name'] = info.get('name', '')
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
        
        self.torrent_db.addTorrent(torrent_hash, torrent)
        self.torrent_db.sync()
        
    def save_torrent(self, torrent_hash, metadata):
        if DEBUG:
            print >> sys.stderr,"metadata: Store torrent", md5.new(torrent_hash).digest(), "on disk"
        #TODO: 
        file_name = self.get_filename(metadata, torrent_hash)
        save_path = os.path.join(self.config_dir, file_name)
        self.addTorrentToDB(save_path, torrent_hash, metadata)
        self.write_torrent(metadata, self.config_dir, file_name)

    def get_filename(self, metadata, torrent_hash):
        # assign a name for the torrent. add a timestamp if it exists.
        metainfo = bdecode(metadata)
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
            print_exc()
            print >> sys.stderr, "metadata: write torrent failed"

    def valid_metadata(self, torrent_hash, metadata):
        metainfo = bdecode(metadata)
        infohash = sha(bencode(metainfo['info'])).digest()
        assert infohash == torrent_hash, "infohash doesn't match the torrent hash " + `infohash` + "!=" + `torrent_hash` 
        return True
        
    def got_metadata(self, conn, message):
        try:
            message = bdecode(message[1:])
        except:
            return False
        if not isinstance(message, dict):
            return False
        try:
            torrent_hash = message['torrent_hash']
            if not isValidInfohash(torrent_hash):
                return False
            metadata = message['metadata']
            self.valid_metadata(torrent_hash, metadata)
            if DEBUG:
                torrent_size = len(metadata)
                print >> sys.stderr,"metadata: Recvd torrent", torrent_size, md5.new(metadata).hexdigest()
            self.save_torrent(torrent_hash, metadata)
            if self.dlhelper is not None:
                self.dlhelper.call_dlhelp_task(torrent_hash, metadata)
        except Exception, msg:
            print_exc()
            print >> sys.stderr,"metadata: Received metadata is broken", msg
            return False
        
        return True
        
