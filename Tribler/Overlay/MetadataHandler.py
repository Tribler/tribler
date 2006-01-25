# Written by Jie Yang
# see LICENSE.txt for license information

from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *

import md5
from traceback import print_exc

# Python no recursive imports?
# from overlayswarm import overlay_infohash
overlay_infohash = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'


DEBUG = False
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
        
    def register(self,secure_overlay,dlhelper,launchmany):
        self.secure_overlay = secure_overlay
        self.dlhelper = dlhelper
        #self.file_cache = FileCacheHandler()
        self.arno_file_cache = launchmany.arno_file_cache

    def handleMessage(self, permid, message):
        
        t = message[0]
        
        if t == GET_METADATA:
            if DEBUG:
                print "metadata: Got GET_METADATA",len(message)
            return self.send_metadata(permid, message)
        elif t == METADATA:
            if DEBUG:
                print "metadata: Got METADATA",len(message)
            return self.got_metadata(permid, message)
        else:
            print "metadata: UNKNOWN OVERLAY MESSAGE", ord(t)
            return False

    def request_metadata(self, torrent_hash):
        # TODO: lookup all candidates who have this torrent_hash
        #       select a peer according to its upload speed. 
        #       Request another peer if the previous one failed
        print "Request metadata", torrent_hash


    def send_metadata_request(self, permid, torrent_hash):
        if not self.valid_torrent_hash(torrent_hash):
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
            return False
        if not self.valid_torrent_hash(torrent_hash):
            return False

        ## ARNO HACK
        torrent_data = self.arno_file_cache[torrent_hash]
        if torrent_data:
            self.do_send_metadata(conn, torrent_hash, torrent_data)
            return True

        ## PREVIOUS CODE
        torrent_path = self.find_torrent(torrent_hash)
        if not torrent_path:
            return False
        torrent_data = self.read_torrent(torrent_path)
        if torrent_data:
            self.do_send_metadata(conn, torrent_hash, torrent_data)
        return True
    
    def do_send_metadata(self, permid, torrent_hash, torrent_data):
        md5sum = md5.new(torrent_data).digest()
        torrent = {'torrent_hash':torrent_hash, 'metadata':torrent_data, 'md5sum':md5sum}
        metadata_request = bencode(torrent)
        self.secure_overlay.addTask(permid,METADATA + metadata_request)

    def find_torrent(self, torrent_hash):
        """ lookup torrent file and return torrent path """
        
        # metadata = self.file_cache.findTorrent(torrent_hash)
        if metadata:
            return metadata['torrent_path']    #TODO: handle merkle torrent
        return None

    def read_torrent(self, torrent_path):
        try:
            file = open(torrent_path, "rb")
            torrent_data = file.read()
            torrent_size = len(torrent_data)
            if torrent_size > Max_Torrent_Size:
                return None
            if DEBUG:
                print "metadata: sending torrent", torrent_size, md5.new(torrent_data).hexdigest()
            return torrent_data
        except:
            return None

    def save_torrent(self, torrent_hash, metadata):
        if DEBUG:
            print "metadata: Store torrent", torrent_hash, "on disk"
        torrent_path = '.'
        return torrent_path

    def got_metadata(self, conn, message):
        try:
            message = bdecode(message[1:])
        except:
            return False
        if not isinstance(message, dict):
            return False
        try:
            torrent_hash = message['torrent_hash']
            if not self.valid_torrent_hash(torrent_hash):
                return False
            metadata = message['metadata']
            md5sum = message['md5sum']
            if md5.new(metadata).digest() != md5sum:
                raise RuntimeError, "md5 sum check failed"
            if DEBUG:
                torrent_size = len(metadata)
                print "metadata: Recvd torrent", torrent_size, md5.new(metadata).hexdigest()
            if not metadata:
                #TODO: try another candidate. If failed, stop requesting this torrent
                return False
            else:
                #torrent_path = self.save_torrent(torrent_hash, metadata)
                #self.dlhelper.call_dlhelp_task(torrent_hash, torrent_path, conn)
                self.dlhelper.call_dlhelp_task(torrent_hash, metadata)
        except Exception, msg:
            print_exc()
            print "metadata: Received metadata is broken", msg
            return False
        
        return True
        
    def valid_torrent_hash(self, torrent_hash):
        return len(torrent_hash) == 20 and torrent_hash != overlay_infohash
        