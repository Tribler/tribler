from bencode import bencode, bdecode
from BT1.MessageID import *
from sha import sha
import sys, os
from random import randint

DEBUG = True

def get_random_filename(dir):
    while True:
        name = str(randint(1, sys.maxint - 1))
        p = os.path.join(dir, name)
        if not os.path.exists(p):
            return name

class Helper:
    
    __single = None
    
    def __init__(self):
        if Helper.__single:
            raise RuntimeError, "Helper is singleton"
        self.dlhelp_queue = {}
        Helper.__single = self
        
    def getInstance(*args, **kw):
        if Helper.__single is None:
            Helper(*args, **kw)
        return Helper.__single
    getInstance = staticmethod(getInstance)
        
    def set_rawserver(self, rawserver):
        self.rawserver = rawserver

# 2fastbt_
    def set_launchmany(self, launchmany):
        self.launchmany = launchmany
# _2fastbt
        
    def set_metadata_handler(self, metadata_handler):
        self.metadata_handler = metadata_handler

    def send_dlhelp_request(self, conn, torrent_hash):
        dlhelp_request = bencode((torrent_hash, self.launchmany.listen_port))
        conn.send_overlay_message(DOWNLOAD_HELP + dlhelp_request)

    def got_dlhelp_request(self, conn, message):
        try:
            (torrent_hash, server_port) = bdecode(message[1:])
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
            self.do_help(torrent_hash, torrent_path, conn, server_port)
        else:
            self.add_dlhelp_task(conn, torrent_hash, server_port)
        return True

    def add_dlhelp_task(self, conn, torrent_hash, server_port):
        if not self.dlhelp_queue.has_key(torrent_hash):
            self.dlhelp_queue[torrent_hash] = []
        self.dlhelp_queue[torrent_hash].append((conn, server_port))
        self.metadata_handler.send_metadata_request(conn, torrent_hash)

    def call_dlhelp_task(self, torrent_hash, torrent_data):
        if not self.dlhelp_queue.has_key(torrent_hash) or not self.dlhelp_queue[torrent_hash]:
            return
        
        for (conn, server_port) in self.dlhelp_queue[torrent_hash]:
            if conn.is_closed():
                return
            self.do_help(torrent_hash, torrent_data, conn, server_port)    # only ask for metadata once

    def do_help(self, torrent_hash, torrent_data, conn, server_port):
        print "**************** download help **************"
#        print "Torrent hash:", torrent_hash, "From:", conn.get_ip(), conn.get_port()
        print "Torrent From:", conn.get_ip(), conn.get_port(), server_port
        d = bdecode(torrent_data)
        data = {}
        data['file'] = get_random_filename(self.launchmany.torrent_dir)
        print "file: ", data['file']
#        data['path'] = os.path.join(self.launchmany.torrent_dir, data['file'])
        data['type'] = 'torrent'
        i = d['info']
        h = sha(bencode(d['info'])).digest()
        assert(h == torrent_hash)
        l = 0
        nf = 0
        if i.has_key('length'):
            l = i.get('length', 0)
            nf = 1
        elif i.has_key('files'):
            for li in i['files']:
                nf += 1
                if li.has_key('length'):
                    l += li['length']
        data['numfiles'] = nf
        data['length'] = l
        data['name'] = i.get('name', data['file'])
        print "name: ", data['name']
        data['path'] = os.path.join(self.launchmany.torrent_dir, data['name'] + '.torrent')
        print "path: ", data['path']
        def setkey(k, d = d, data = data):
            if d.has_key(k):
                data[k] = d[k]
        setkey('failure reason')
        setkey('warning message')
        setkey('announce-list')
        data['metainfo'] = d

# TODO: instead of writing .torrent to the disk keep it only in the memory
        torrent_file = open(data['path'], "w")
        torrent_file.write(torrent_data)
        torrent_file.close()

        self.launchmany.torrent_cache[torrent_hash] = data
        self.launchmany.file_cache[data['path']] = \
            [(os.path.getmtime(data['path']), os.path.getsize(data['path'])), torrent_hash]
        self.launchmany.config['role'] = 'helper'
        self.launchmany.config['coordinator_ip'] = conn.get_ip()
        self.launchmany.config['coordinator_port'] = server_port
        self.launchmany.add(torrent_hash, data)

    def can_help(self, torrent_hash):    #TODO: test if I can help the cordinator to download this file
        return True                      #Future support: make the decision based on my preference

    def find_torrent(self, torrent_hash):
        return None

    def got_message(self, conn, message):
        
        t = message[0]
        
        if t == DOWNLOAD_HELP:
            if DEBUG:
                print "Helper got_message DOWNLOAD_HELP"
            return self.got_dlhelp_request(conn, message)
        else:
            print "UNKONW OVERLAY MESSAGE", ord(t)
        
    def startup(self):
        if DEBUG:
            print "DOWNLOAD HELPER starts"
        pass
        
            