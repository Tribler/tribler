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
import Tribler.Core.BitTornado.parseargs as parseargs

argsdef = [('name', '', 'name of the stream'),
           ('source', '-', 'source to stream (url, file or "-" to indicate stdin)'),
           ('fileloop', False, 'if source is file, loop over it endlessly'),
           ('destdir', '.','dir to save torrent (and stream)'),
           ('bitrate', (512*1024)/8, 'bitrate of the streams in bytes'),
           ('piecesize', 32768, 'transport piece size'),
           ('duration', '1:00:00', 'duration of the stream in hh:mm:ss format'),
           ('nuploads', 7, 'the max number of peers to serve directly'),
           ('port', 7764, 'the TCP+UDP listen port'),
           ('thumb', '', 'filename of image in JPEG format, preferably 171x96'),
           ('cs_keys', '', 'semi-colon separated list of Closed Swarm keys for this torrent'),
           ('generate_cs', 'no', "Create a closed swarm, generating the keys ('yes' to generate)"),

           ('auth', 'RSA', 'Live-souce authentication method to use (ECDSA or RSA)')
           ]


def state_callback(ds):
    d = ds.get_download()
    print >>sys.stderr,`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)

    return (1.0,False)

def vod_ready_callback(d,mimetype,stream,filename):
    """ Called by the Session when the content of the Download is ready
     
    Called by Session thread """
    print >>sys.stderr,"main: VOD ready callback called ###########################################################",mimetype

def generate_key(source, config):
    """
    Generate and a closed swarm key matching the config.  Source is the 
    source of the torrent
    """
    
    
    a, b = os.path.split(source)
    if b == '':
        target = a
    else:
        target = os.path.join(a, b)
    target += ".torrent"
    print "Generating key to '%s.tkey' and '%s.pub'"%(target, target)
    
    keypair, pubkey = ClosedSwarm.generate_cs_keypair(target + ".tkey",
                                                      target + ".pub")
    
    return keypair,pubkey


def get_usage(defs):
    return parseargs.formatDefinitions(defs,80)
    
    
class FileLoopStream:
    
    def __init__(self,stream):
        self.stream = stream
        
    def read(self,nbytes=None):
        data = self.stream.read(nbytes)
        if len(data) == 0: # EOF
            self.stream.seek(0)
            data = self.stream.read(nbytes)
        return data
    
    def close(self):
        self.stream.close()


if __name__ == "__main__":

    config, fileargs = parseargs.parseargs(sys.argv, argsdef, presets = {})
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
    
    s = Session(sscfg)


    # LIVESOURCEAUTH
    authfilename = os.path.join(config['destdir'],config['name']+'.sauth')
    if config['auth'] == 'RSA':
        try:
            authcfg = RSALiveSourceAuthConfig.load(authfilename)
        except:
            print_exc()
            authcfg = RSALiveSourceAuthConfig()
            authcfg.save(authfilename)
    else:
        try:
            authcfg = ECDSALiveSourceAuthConfig.load(authfilename)
        except:
            print_exc()
            authcfg = ECDSALiveSourceAuthConfig()
            authcfg.save(authfilename)

    print >>sys.stderr,"main: Source auth pubkey",`str(authcfg.get_pubkey())`

    tdef = TorrentDef()
    # hint: to derive bitrate and duration from a file, use
    #    ffmpeg -i file.mpeg /dev/null
    tdef.create_live(config['name'],config['bitrate'],config['duration'],authcfg)
    tdef.set_tracker(s.get_internal_tracker_url())
    tdef.set_piece_length(config['piecesize']) #TODO: auto based on bitrate?
    if len(config['thumb']) > 0:
        tdef.set_thumbnail(config['thumb'])

    if config['generate_cs'].lower() == "yes":
        if config['cs_keys']:
            print "Refusing to generate keys when key is given"
            raise SystemExit(1)

        cs_keypair, config['cs_keys'] = generate_key(config['name'], config)

        # TODO: Read POA if keys are already given (but generate_cs is "no")
        # Will also create POA for this node - which will seed it!
    if len(config['cs_keys']) > 0:
        print >>sys.stderr,"Setting torrent keys to:",config['cs_keys'].split(";")
        tdef.set_cs_keys(config['cs_keys'])
    else:
        print >>sys.stderr,"No keys"
    #tdef2 = TorrentDef.load(torrentfilename)
    #print >>sys.stderr,"main: Source auth pubkey2",`tdef2.metainfo['info']['live']`

    tdef.finalize()
    
    torrentbasename = config['name']+'.tstream'
    torrentfilename = os.path.join(config['destdir'],torrentbasename)
    tdef.save(torrentfilename)

    poa = None
    if tdef.get_cs_keys():
        # Try to read POA, or if none was found, generate it
        try:
            poa = ClosedSwarm.trivial_get_poa(Session.get_default_state_dir(),
                                              authcfg.get_pubkey(),
                                              tdef.infohash)
        except:
            # Generate and save
            poa = ClosedSwarm.create_poa(tdef.infohash,
                                         cs_keypair,
                                         authcfg.get_pubkey())
            
            try:
                ClosedSwarm.trivial_save_poa(Session.get_default_state_dir(),
                                             authcfg.get_pubkey(),
                                             tdef.infohash,
                                             poa)
                print >>sys.stderr,"POA saved"
            except Exception,e:
                print >>sys.stderr,"Could not save POA"



    dscfg = DownloadStartupConfig()
    dscfg.set_dest_dir(config['destdir'])

    if poa:
        dscfg.set_poa(poa)
        
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
        stream = open(config['source'],"rb")
        if config['fileloop']:
            source = FileLoopStream(stream)
        else:
            source = stream
        dscfg.set_video_ratelimit(tdef.get_bitrate())
        
    dscfg.set_video_source(source,authcfg)

    dscfg.set_max_uploads(config['nuploads'])

    d = s.start_download(tdef,dscfg)
    d.set_state_callback(state_callback,getpeerlist=False)
   
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
    
