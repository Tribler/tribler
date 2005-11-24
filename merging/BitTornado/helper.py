from bencode import bencode, bdecode
from BT1.MessageID import *

DEBUG = False

class Helper:
    
    __single = None
    
    def __init__(self):
        if Helper.__single:
            raise RuntimeError, "Helper is singleton"
        Helper.__single = self
        self.dlhelp_queue = {}
        
    def getInstance(*args, **kw):
        if Helper.__single is None:
            Helper(*args, **kw)
        return Helper.__single
    getInstance = staticmethod(getInstance)
        
    def set_rawserver(self, rawserver):
        self.rawserver = rawserver
        
    def set_metadata_handler(self, metadata_handler):
        self.metadata_handler = metadata_handler
        
    def send_dlhelp_request(self, conn, torrent_hash):
        dlhelp_request = bencode(torrent_hash)
        conn.send_overlay_message(DOWNLOAD_HELP + dlhelp_request)
                
    def got_dlhelp_request(self, conn, message):
        try:
            torrent_hash = bdecode(message[1:])
        except:
            errorfunc("warning: bad data in dlhelp_request")
            return False
        if DEBUG:
            print "Got dlhelp_request from ", conn.get_ip()
        if not conn.permid:
            return False
        
        if not self.can_help(torrent_hash):
            return False
        torrent_path = self.find_torrent(torrent_hash)
        if torrent_path:
            self.do_help(torrent_hash, torrent_path, conn)
        else:
            self.add_dlhelp_task(conn, torrent_hash)
        return True
    
    def add_dlhelp_task(self, conn, torrent_hash):
        if not self.dlhelp_queue.has_key(torrent_hash):
            self.dlhelp_queue[torrent_hash] = []
        self.dlhelp_queue[torrent_hash].append(conn)
        self.metadata_handler.send_metadata_request(conn, torrent_hash)
        
    def call_dlhelp_task(self, torrent_hash, torrent_data):
        if not self.dlhelp_queue.has_key(torrent_hash) or not self.dlhelp_queue[torrent_hash]:
            return
        
        for conn in self.dlhelp_queue[torrent_hash]:
            if conn.is_closed():
                return
            self.do_help(torrent_hash, torrent_data, conn)    # only ask for metadata once
            
    def do_help(self, torrent_hash, torrent_data, conn):
        print "**************** download help **************"
        print "Torrent hash:", torrent_hash, "From:", conn.get_ip(), conn.get_port()
        pass
    
    def can_help(self, torrent_hash):    #TODO: test if I can help the cordinator to download this file
        return True                      #Future support: make the decision based on my preference
    
    def find_torrent(self, torrent_hash):
        return None
                
    def got_message(self, conn, message):
        
        t = message[0]
        
        if t == DOWNLOAD_HELP:
            return self.got_dlhelp_request(conn, message)
        else:
            print "UNKONW OVERLAY MESSAGE", ord(t)
        
    def startup(self):
        if DEBUG:
            print "DOWNLOAD HELPER starts"
        pass
        
            