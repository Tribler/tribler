# Written by Arno Bakker
# see LICENSE.txt for license information
#

import sys
import os
import shutil
import time
import tempfile
import random
import urllib2
from traceback import print_exc
from threading import Condition

from Tribler.Core.API import *
import Tribler.Core.Utilities.parseargs as parseargs

argsdef = [('name', '', 'name of the stream'),
           ('source', '-', 'source to stream (url, file or "-" to indicate stdin)'),
           ('destdir', '.','dir to save torrent (and stream)'),
           ('bitrate', (512*1024)/8, 'bitrate of the streams in bytes'),
           ('piecesize', 32768, 'transport piece size'),
           ('duration', '1:00:00', 'duration of the stream in hh:mm:ss format'),
           ('nuploads', 7, 'the max number of peers to serve directly'),
           ('port', 7764, 'the TCP+UDP listen port'),
           ('thumb', '', 'filename of image in JPEG format, preferably 171x96')]


def state_callback(ds):
    d = ds.get_download()
    print >>sys.stderr,`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)

    return (1.0,False)

def vod_ready_callback(d,mimetype,stream,filename):
    """ Called by the Session when the content of the Download is ready

    Called by Session thread """
    print >>sys.stderr,"main: VOD ready callback called ###########################################################",mimetype

def get_usage(defs):
    return parseargs.formatDefinitions(defs,80)


if __name__ == "__main__":

    config, fileargs = parseargs.Utilities.parseargs(sys.argv, argsdef, presets = {})
    print >>sys.stderr,"config is",config
    print "fileargs is",fileargs

    if config['name'] == '':
        print "Usage:  ",get_usage(argsdef)
        sys.exit(0)


    print "Press Ctrl-C to stop the download"

    try:
        os.remove(os.path.join(config['destdir'],config['name']))
    except:
        print_exc()

    sscfg = SessionStartupConfig()
    statedir = tempfile.mkdtemp()
    sscfg.set_state_dir(statedir)
    sscfg.set_listen_port(config['port'])
    sscfg.set_megacache(False)
    sscfg.set_overlay(False)
    sscfg.set_dialback(True)
    sscfg.set_dispersy(False)

    s = Session(sscfg)


    # no LIVESOURCEAUTH for Pioneer, saves CPU


    tdef = TorrentDef()
    # hint: to derive bitrate and duration from a file, use
    #    ffmpeg -i file.mpeg /dev/null
    tdef.create_live(config['name'],config['bitrate'],config['duration'])
    tdef.set_tracker(s.get_internal_tracker_url())
    tdef.set_piece_length(config['piecesize']) #TODO: auto based on bitrate?
    if len(config['thumb']) > 0:
        tdef.set_thumbnail(config['thumb'])
    tdef.finalize()

    torrentbasename = config['name']+'.tstream'
    torrentfilename = os.path.join(config['destdir'],torrentbasename)
    tdef.save(torrentfilename)

    #tdef2 = TorrentDef.load(torrentfilename)
    #print >>sys.stderr,"main: Source auth pubkey2",`tdef2.metainfo['info']['live']`

    dscfg = DownloadStartupConfig()
    dscfg.set_dest_dir(config['destdir'])
    dscfg.set_live_aux_seeders( [
            # servers:
            ("130.161.211.232",8764), # ss1
            ("130.161.211.233",8764), # ss2
            ("130.161.211.234",8764), # ss3
            ("193.29.139.222",8764), # peer2peer.colo.mediadesign.nl, old ip
            ("83.96.143.114",8764), # peer2peer.colo.mediadesign.nl, new ip
            ("130.37.198.236",8764), # jip

            # machines to verify the video stream:
            ("130.161.159.89",8620), # jd's laptop
            ("130.161.159.210",8620), # arno's st interface
            ] )
    if config['source'] == '-':
        # Arno: doesn't appear to work on Linux
        source = sys.stdin
    elif config['source'].startswith('http:'):
        # HTTP source
        source = urllib2.urlopen(config['source'])
        """
        # Windows Media Encoder gives Bad Request if we don't include User-Agent
        url = config['source']
        user_agent = 'NSPlayer/4.1.0.3856'
        headers = { 'User-Agent' : user_agent }

        req = urllib2.Request(url, None, headers)
        source = urllib2.urlopen(req)
        """
    elif config['source'].startswith('pipe:'):
        # Program as source via pipe
        cmd = config['source'][len('pipe:'):]
        (child_out,source) = os.popen2( cmd, 'b' )
    else:
        # File source
        source = open(config['source'],"rb")
        dscfg.set_video_ratelimit(tdef.get_bitrate())

    restartstatefilename = config['name']+'.restart'
    dscfg.set_video_source(source, restartstatefilename=restartstatefilename)

    dscfg.set_max_uploads(config['nuploads'])

    d = s.start_download(tdef,dscfg)
    d.set_state_callback(state_callback,getpeerlist=[])

    # condition variable would be prettier, but that don't listen to
    # KeyboardInterrupt
    #time.sleep(sys.maxint/2048)
    #try:
    #    while True:
    #        x = sys.stdin.read()
    #except:
    #    print_exc()
    cond = Condition()
    cond.acquire()
    cond.wait()

    s.shutdown()
    time.sleep(3)
    shutil.rmtree(statedir)
