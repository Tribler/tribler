# Written by Pawel Garbacki, Arno Bakker
# see LICENSE.txt for license information
""" SecureOverlay message handler for a Helper"""


from sha import sha
import sys, os
from random import randint

from Tribler.toofastbt.intencode import toint, tobinary
from Tribler.Overlay.SecureOverlay import SecureOverlay
from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *

DEBUG = True

def get_random_filename(dir):
    while True:
        name = str(randint(1, sys.maxint - 1))
        p = os.path.join(dir, name)
        if not os.path.exists(p):
            return name

class HelperMessageHandler:
    def __init__(self,launchmany):
        self.metadata_queue = {}
        self.launchmany = launchmany

    def register(self, metadata_handler):
        self.metadata_handler = metadata_handler

    def handleMessage(self,permid,message):
        t = message[0]

        if DEBUG:
            print "helper: Got",getMessageName(t)
        if t == DOWNLOAD_HELP:
            return self.got_dlhelp_request(permid, message)
        elif t == STOP_DOWNLOAD_HELP:
            return self.got_dlhelp_request(permid, message)
        elif t == PIECES_RESERVED:
            return self.got_pieces_reserved(permid, message)


    def got_dlhelp_request(self, permid, message):
        try:
            #(torrent_hash, server_port) = bdecode(message[1:])
            torrent_hash = message[1:]
        except:
            errorfunc("warning: bad data in dlhelp_request")
            return False
        if DEBUG:
            print "helper: Got DOWNLOAD_HELP from ", `permid`
        
# TODO: add concurrency control

        if not self.can_help(torrent_hash):
            return False
        torrent_path = self.find_torrent(torrent_hash)
        if torrent_path:
            self.do_help(torrent_hash, torrent_path, permid)
        else:
            self.get_metadata(permid, torrent_hash)
        return True


    # It is very important here that we create safe filenames, i.e., it should
    # not be possible for a coordinator to send a METADATA message that causes
    # important files to be overwritten
    #
    def do_help(self, torrent_hash, torrent_data, permid):
        d = bdecode(torrent_data)
        data = {}
        data['file'] = get_random_filename(self.launchmany.torrent_dir)
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
        dest = os.path.join(self.launchmany.torrent_dir, data['file'] )
        data['dest'] = dest        

        # These values are used by abcengine.py to create BT1Download
        data['coordinator_permid'] = permid
        secure_overlay = SecureOverlay.getInstance()
        dns = secure_overlay.findDNSByPermid(permid)
        # Do this before writing torrent to disk
        if dns is None:
            print "helpmsg: Cannot get coordinator IP address, ignoring help request"
            return
        data['coordinator_ip'] = dns[0]

        tfile = os.path.join(self.launchmany.torrent_dir, data['file'] + '.torrent')
        data['path'] = tfile
        def setkey(k, d = d, data = data):
            if d.has_key(k):
                data[k] = d[k]
        setkey('failure reason')
        setkey('warning message')
        setkey('announce-list')
        data['metainfo'] = d

        if DEBUG:
            print "helpmsg: Got metadata required for helping"
            print "helpmsg: name:   ", data['name']
            print "helpmsg: torrent: ", data['path']
            print "helpmsg: saveas: ", data['file']

        # TODO: instead of writing .torrent to the disk keep it only in the memory
        torrent_file = open(data['path'], "wb")
        torrent_file.write(torrent_data)
        torrent_file.close()

        self.launchmany.torrent_cache[torrent_hash] = data
        self.launchmany.file_cache[data['path']] = \
            [(os.path.getmtime(data['path']), os.path.getsize(data['path'])), torrent_hash]

        # These values are used by launchmanycore??? in text mode????
        self.launchmany.config['role'] = 'helper'
        self.launchmany.config['coordinator_permid'] = permid
        self.launchmany.config['coordinator_ip'] = dns[0]

        # Start new download
        self.launchmany.add(torrent_hash, data)

    def get_metadata(self, permid, torrent_hash):
        if not self.metadata_queue.has_key(torrent_hash):
            self.metadata_queue[torrent_hash] = []
        self.metadata_queue[torrent_hash].append(permid)
        self.metadata_handler.send_metadata_request(permid, torrent_hash)

    def call_dlhelp_task(self, torrent_hash, torrent_data):
        print "helpmsg: Metadata handler reports torrent is in"
        if not self.metadata_queue.has_key(torrent_hash) or not self.metadata_queue[torrent_hash]:
            print "helpmsg: Metadata's data not right one!"
            return
        
        for permid in self.metadata_queue[torrent_hash]:
            # only ask for metadata once
            self.do_help(torrent_hash, torrent_data, permid)    

    def can_help(self, torrent_hash):    #TODO: test if I can help the cordinator to download this file
        return True                      #Future support: make the decision based on my preference

    def find_torrent(self, torrent_hash):
        return None

    def got_pieces_reserved(self,permid, message):
        try:
            print "helpmsg: pieces_reserved len is",len(message)
            torrent_hash = message[1:21]
            reqid = toint(message[21:25])
            pieces = bdecode(message[25:])
        except:
            errorfunc("warning: bad data in PIECES_RESERVED")
            return False

# TODO: add concurrency control

        h = self.launchmany.get_helper(torrent_hash)
        if h is None:
            return False

        if not h.is_coordinator(permid): 
            return False

        h.got_pieces_reserved(permid, pieces)
        # Wake up download thread
        h.notify(reqid)
        return True
        
