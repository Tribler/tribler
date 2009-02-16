import sys
import os
import time
import sha
from traceback import print_exc

from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import validTorrentFile
from Tribler.Core.Overlay.MetadataHandler import get_filename

state_dir = Session.get_default_state_dir()
sconfig = SessionStartupConfig()
sconfig.set_state_dir(state_dir)
#sconfig.set_overlay(False)
# Set default Session params here
destdir = get_default_dest_dir()
torrcolldir = os.path.join(destdir,STATEDIR_TORRENTCOLL_DIR)
sconfig.set_torrent_collecting_dir(torrcolldir)

s = Session(sconfig)

torrent_db = s.open_dbhandler(NTFY_TORRENTS)

inttime = int(time.time())
extra_info = {'leecher': 100,'seeder': 100,'last_check_time':inttime,'status':'good'}
source = 'Manual'

#filenames = ['route2.tstream','star2.tstream','gopher.torrent']
#for filename in filenames:
dir = "c:\\Documents and Settings\\Arno\\Desktop\\downloadjunk"
filelist = os.listdir(dir)
for basename in filelist:
    filename = os.path.join(dir,basename)
    # Make this go on when a torrent fails to start
    try:
        f = open(filename,"rb")
        data = f.read()
        f.close()
        metainfo = bdecode(data)
        infohash = sha.sha(bencode(metainfo['info'])).digest()
        validTorrentFile(metainfo)
        
        fname = get_filename(infohash, None)
        if not os.access(torrcolldir,os.F_OK):
            os.mkdir(torrcolldir)
        save_path = os.path.join(torrcolldir,fname)
        print >>sys.stderr,"Saving torrent to",save_path
        
        file = open(save_path, 'wb')
        file.write(data)
        file.close()
        
        torrent = torrent_db.addExternalTorrent(save_path, source, extra_info)
        if torrent is None:
            print >>sys.stderr,"Error adding",filename
        else:
            print >>sys.stderr,"Added",filename
    except:
        print_exc()

s.shutdown()
time.sleep(2)