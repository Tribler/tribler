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

argsdef = [('source', '', 'source file or directory'),
           ('tracker', 'http://127.0.0.1:6969/announce', 'tracker URL'),
           ('destdir', '.','dir to save torrent'),
           ('duration', '1:00:00', 'duration of the stream in hh:mm:ss format'),           
           ('piecesize', 32768, 'transport piece size'),
           ('thumb', '', 'filename of image in JPEG format, preferably 171x96'),
           ('url', False, 'Create URL instead of torrent (cannot be used with thumb)')]


def get_usage(defs):
    return parseargs.formatDefinitions(defs,80)
    
    
if __name__ == "__main__":

    config, fileargs = parseargs.parseargs(sys.argv, argsdef, presets = {})
    print >>sys.stderr,"config is",config
    
    if config['source'] == '':
        print "Usage:  ",get_usage(argsdef)
        sys.exit(0)
        
    if isinstance(config['source'],unicode):
        usource = config['source']
    else:
        usource = config['source'].decode(sys.getfilesystemencoding())
        
    tdef = TorrentDef()
    if os.path.isdir(usource):
        for filename in os.listdir(usource):
            path = os.path.join(usource,filename)
            tdef.add_content(path,path,playtime=config['duration'])
    else:
        tdef.add_content(usource,playtime=config['duration'])
        
    tdef.set_tracker(config['tracker'])
    tdef.set_piece_length(config['piecesize']) #TODO: auto based on bitrate?
    
    if config['url']:
        tdef.set_create_merkle_torrent(1)
        tdef.set_url_compat(1)
    else:
        if len(config['thumb']) > 0:
            tdef.set_thumbnail(config['thumb'])
    tdef.finalize()
    
    if config['url']:
        urlbasename = config['source']+'.url'
        urlfilename = os.path.join(config['destdir'],urlbasename)
        f = open(urlfilename,"wb")
        f.write(tdef.get_url())
        f.close()
    else:
        torrentbasename = config['source']+'.tstream'
        torrentfilename = os.path.join(config['destdir'],torrentbasename)
        tdef.save(torrentfilename)
