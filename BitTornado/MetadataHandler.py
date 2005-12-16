from bencode import bencode, bdecode
from BT1.MessageID import *
from FileCacheHandler import FileCacheHandler

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
        self.file_cache = FileCacheHandler()
        
    def getInstance(*args, **kw):
        if MetadataHandler.__single is None:
            MetadataHandler(*args, **kw)
        return MetadataHandler.__single
    getInstance = staticmethod(getInstance)
        
    def set_rawserver(self, rawserver):
        self.rawserver = rawserver
        
    def set_dlhelper(self, dlhelper):
        self.dlhelper = dlhelper
        
    def startup(self):
        if DEBUG:
            print "MetadataHandler starts"
        pass
        
    def valid_torrent_hash(self, torrent_hash):
        return len(torrent_hash) == 20 and torrent_hash != overlay_infohash
        
    def send_metadata_request(self, conn, torrent_hash):
        if not self.valid_torrent_hash(torrent_hash):
            return False
        try:
            metadata_request = bencode(torrent_hash)
            conn.send_overlay_message(GET_METADATA + metadata_request)
        except:
            return False
        return True
        
    def request_metadata(self, torrent_hash):
        # TODO: lookup all candidates who have this torrent_hash
        #       select a peer according to its upload speed. 
        #       Request another peer if the previous one failed
        print "Reuqest metadata", torrent_hash

    def send_metadata(self, conn, message):
        try:
            torrent_hash = bdecode(message[1:])
        except:
            return False
        if not self.valid_torrent_hash(torrent_hash):
            return False
        torrent_path = self.find_torrent(torrent_hash)
        if not torrent_path:
            return False
        torrent_data = self.read_torrent(torrent_path)
        if torrent_data:
            self.do_send_metadata(conn, torrent_hash, torrent_data)
        return True
    
    def do_send_metadata(self, conn, torrent_hash, torrent_data):
        md5sum = md5.new(torrent_data).digest()
        torrent = {'torrent_hash':torrent_hash, 'metadata':torrent_data, 'md5sum':md5sum}
        metadata_request = bencode(torrent)
        conn.send_overlay_message(METADATA + metadata_request)

    def find_torrent(self, torrent_hash):
        """ lookup torrent file and return torrent path """
        
        metadata = self.file_cache.findTorrent(torrent_hash)
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
                print "send torrent", torrent_size, md5.new(torrent_data).hexdigest()
            return torrent_data
        except:
            return None

    def save_torrent(self, torrent_hash, metadata):
        print "Store torrent", torrent_hash, "on disk"
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
            if DEBUG:
                print "************* got metadata *************"
                #print metadata
                
            torrent_hash = message['torrent_hash']
            if not self.valid_torrent_hash(torrent_hash):
                return False
            metadata = message['metadata']
            md5sum = message['md5sum']
            if md5.new(metadata).digest() != md5sum:
                raise RuntimeError, "md5 sum check failed"
            if DEBUG:
                torrent_size = len(metadata)
                print "recv torrent", torrent_size, md5.new(metadata).hexdigest()
            if not metadata:
                #TODO: try another candidate. If failed, stop requesting this torrent
                return False
            else:
                #torrent_path = self.save_torrent(torrent_hash, metadata)
                #self.dlhelper.call_dlhelp_task(torrent_hash, torrent_path, conn)
                self.dlhelper.call_dlhelp_task(torrent_hash, metadata)
        except Exception, msg:
            print_exc()
            print "Received metadata is broken", msg
            return False
        
        return True

    def got_message(self, conn, message):
        
        t = message[0]
        
        if t == GET_METADATA:
            if DEBUG:
                print "recv GET_METADATA"
            return self.send_metadata(conn, message)
        elif t == METADATA:
            if DEBUG:
                print "recv METADATA"
            return self.got_metadata(conn, message)
        else:
            print "UNKONW OVERLAY MESSAGE", ord(t)
            return False
        
