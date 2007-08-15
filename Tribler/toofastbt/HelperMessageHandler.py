# Written by Pawel Garbacki, Arno Bakker
# see LICENSE.txt for license information
""" SecureOverlay message handler for a Helper"""


from sha import sha
import sys, os
from random import randint

from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.utilities import show_permid_short
from Tribler.CacheDB.CacheDBHandler import FriendDBHandler,TorrentDBHandler
from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *

DEBUG = False

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
        self.helpdir = launchmany.torrent_dir
        self.torrent_db = TorrentDBHandler()

    def register(self, metadata_handler,secure_overlay):
        self.metadata_handler = metadata_handler
        self.secure_overlay = secure_overlay

    def handleMessage(self,permid,selversion,message):
        t = message[0]
        #if DEBUG:
        #    print >> sys.stderr,"helper: Got",getMessageName(t)

        # Access control
        friends = FriendDBHandler().getFriends()
        flag = 0
        for peer in friends:
            if peer['permid'] == permid:
                if DEBUG:
                    print >> sys.stderr,"helper: Got",getMessageName(t),"from friend",peer['name']
                flag = 1
                break
        if flag == 0:
            if DEBUG:
                print >> sys.stderr,"helper: Got",getMessageName(t),"from unknown peer",show_permid_short(permid)
            return False
        
        if t == DOWNLOAD_HELP:
            return self.got_dlhelp_request(permid, message, selversion)
        elif t == STOP_DOWNLOAD_HELP:
            return self.got_stop_dlhelp_request(permid, message, selversion)
        elif t == PIECES_RESERVED:
            return self.got_pieces_reserved(permid, message, selversion)


    def got_dlhelp_request(self, permid, message,selversion):
        try:
            torrent_hash = message[1:]
        except:
            print >> sys.stderr,"helper: warning: bad data in dlhelp_request"
            return False
        
        if len(torrent_hash) != 20:
            return False
        
        if not self.can_help(torrent_hash):
            return False
        torrent_data = self.find_torrent(torrent_hash)
        if torrent_data:
            self.do_help(torrent_hash, torrent_data, permid)
        else:
            self.get_metadata(permid, torrent_hash,selversion)
        return True


    # It is very important here that we create safe filenames, i.e., it should
    # not be possible for a coordinator to send a METADATA message that causes
    # important files to be overwritten
    #
    def do_help(self, torrent_hash, torrent_data, permid):
        d = bdecode(torrent_data)
        data = {}
        data['file'] = get_random_filename(self.helpdir)
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
        dest = os.path.join(self.helpdir, data['file'] )
        data['dest'] = dest        

        # These values are used by abcengine.py to create BT1Download
        data['coordinator_permid'] = permid

        tfile = os.path.join(self.helpdir, data['file'] + '.torrent')
        data['path'] = tfile
        def setkey(k, d = d, data = data):
            if d.has_key(k):
                data[k] = d[k]
        setkey('failure reason')
        setkey('warning message')
        setkey('announce-list')
        data['metainfo'] = d

        friendname = None
        friends = FriendDBHandler().getFriends()
        for peer in friends:
            if peer['permid'] == permid:
                friendname = peer['name']
                break
        data['friendname'] = friendname

        if DEBUG:
            print >> sys.stderr,"helpmsg: Got metadata required for helping",friendname
            print >> sys.stderr,"helpmsg: name:   ", data['name']
            print >> sys.stderr,"helpmsg: torrent: ", data['path']
            print >> sys.stderr,"helpmsg: saveas: ", data['file']

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

        # Start new download
        self.launchmany.add(torrent_hash, data)

    def get_metadata(self, permid, torrent_hash, selversion):
        if DEBUG:
            print >> sys.stderr,"helpmsg: Don't have torrent yet, ask coordinator"
        if not self.metadata_queue.has_key(torrent_hash):
            self.metadata_queue[torrent_hash] = []
        self.metadata_queue[torrent_hash].append(permid)
        self.metadata_handler.send_metadata_request(permid, torrent_hash, selversion,caller="dlhelp")

    def call_dlhelp_task(self, torrent_hash, torrent_data):
        if DEBUG:
            print >> sys.stderr,"helpmsg: Metadata handler reports torrent is in."
        if not self.metadata_queue.has_key(torrent_hash) or not self.metadata_queue[torrent_hash]:
            if DEBUG:
                print >> sys.stderr,"helpmsg: Metadata handler reported a torrent we are not waiting for."
            return
        
        for permid in self.metadata_queue[torrent_hash]:
            # only ask for metadata once
            self.do_help(torrent_hash, torrent_data, permid)
        del self.metadata_queue[torrent_hash]

    def can_help(self, torrent_hash):    #TODO: test if I can help the cordinator to download this file
        return True                      #Future support: make the decision based on my preference

    def find_torrent(self, torrent_hash):
        torrent = self.torrent_db.getTorrent(torrent_hash)
        if torrent is None:
            return None
        elif 'torrent_dir' in torrent:
            fn = torrent['torrent_dir']
            if os.path.isfile(fn):
                f = open(fn,"rb")
                data = f.read()
                f.close()
                return data
            else:
                return None
        else:
            return None


    def got_stop_dlhelp_request(self, permid, message, selversion):
        try:
            torrent_hash = message[1:]
        except:
            print >> sys.stderr,"helper: warning: bad data in STOP_DOWNLOAD_HELP"
            return False

        h = self.launchmany.get_helper(torrent_hash)
        if h is None:
            return False

        if not h.is_coordinator(permid): 
            return False

        self.launchmany.remove(torrent_hash)
        
        self.secure_overlay.close(permid)
        
        return True


    def got_pieces_reserved(self,permid, message, selversion):
        try:
            torrent_hash = message[1:21]
            pieces = bdecode(message[21:])
        except:
            print >> sys.stderr,"helper: warning: bad data in PIECES_RESERVED"
            return False


        h = self.launchmany.get_helper(torrent_hash)
        if h is None:
            return False

        if not h.is_coordinator(permid): 
            return False

        h.got_pieces_reserved(permid, pieces)
        # Wake up download thread
        h.notify()
        return True
        
