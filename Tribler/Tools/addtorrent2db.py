#!/usr/bin/env python
#
# HACK by Arno to add a torrent to the database.
# Usage:
# $ python addtorrent2db.py --torrent file .
#
# Don't forget the . at the end. I haven't hacked that out yet, 
# this is a stripped btlaunchmany.
#
# Written by John Hoffman and Pawel Garbacki
# see LICENSE.txt for license information


from Tribler.Core.BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

from sha import sha
from Tribler.Core.BitTornado.launchmanycore import LaunchMany
from Tribler.Core.BitTornado.download_bt1 import defaults, get_usage
from Tribler.Core.BitTornado.parseargs import parseargs
from threading import Event
from sys import argv, exit
import sys, os
from Tribler.Core.BitTornado import version, report_email
from Tribler.Core.BitTornado.ConfigDir import ConfigDir
from Tribler.Core.BitTornado.bencode import bdecode,bencode

#--- 2fastbt_
from time import time,sleep
from Tribler.Core.simpledefs import tribler_init, tribler_done
from Tribler.Core.Overlay.MetadataHandler import MetadataHandler
import Tribler.Core.BitTornado.BT1.Encrypter as Encrypter
# _2fastbt

assert sys.version >= '2', "Install Python 2.0 or greater"
try:
    True
except:
    True = 1
    False = 0

def hours(n):
    if n == -1:
        return '<unknown>'
    if n == 0:
        return 'complete!'
    n = int(n)
    h, r = divmod(n, 60 * 60)
    m, sec = divmod(r, 60)
    if h > 1000000:
        return '<unknown>'
    if h > 0:
        return '%d hour %02d min %02d sec' % (h, m, sec)
    else:
        return '%d min %02d sec' % (m, sec)


Exceptions = []

class HeadlessDisplayer:
#--- 2fastbt_
    def __init__(self):
        self.start_time = time()
        self.end_time = None
# _2fastbt
    
    def display(self, data):
        print ''
        if not data:
            self.message('no torrents')
        for x in data:
            ( name, status, progress, peers, seeds, seedsmsg, dist,
              uprate, dnrate, upamt, dnamt, size, t, msg ) = x
#--- 2fastbt_
            if status != "seeding":
                delta = time() - self.start_time
            else:
                if self.end_time is None:
                    self.end_time = time()
                delta = self.end_time - self.start_time
            x = '"%s": "%s" (%s) - %sP%s%s%.3fD u%0.1fK/s-d%0.1fK/s u%dK-d%dK "%s" %d' % (
                    name, status, progress, peers, seeds, seedsmsg, dist,
                    uprate/1000, dnrate/1000, upamt/1024, dnamt/1024, msg, int(delta))
            print x
# _2fastbt
        return False
            
    def message(self, s):
        pass
        #print "### "+`s`

    def exception(self, s):
        self.message(s)
        # Exceptions.append(s)
        self.message('SYSTEM ERROR - EXCEPTION GENERATED')


if __name__ == '__main__':

    # ---- Only for buddycast debug version ------
    DEBUG = 0
    if DEBUG:
        peer_db_path = '.Tribler/bsddb/peers.bsd'
        my_db_path = '.Tribler/bsddb/mydata.bsd'
        if os.path.exists(peer_db_path):
            os.remove(peer_db_path)
            os.remove(my_db_path)
            print "removed", peer_db_path, os.path.exists(peer_db_path)
        else:
            print "cannot remove", peer_db_path, os.path.exists(peer_db_path)
    # ---- -----------------------------
    
    if argv[1:] == ['--version']:
        print version
        exit(0)
    defaults.extend( [
        ( 'parse_dir_interval', 60,
          "how often to rescan the torrent directory, in seconds" ),
        ( 'saveas_style', 1,
          "How to name torrent downloads (1 = rename to torrent name, " +
          "2 = save under name in torrent, 3 = save in directory under torrent name)" ),
        ( 'display_path', 1,
          "whether to display the full path or the torrent contents for each torrent" ),
       ('config_path', '',
          'directory containing the Tribler config files (default $HOME/.Tribler)'),
        ( 'seed_only', 0,
          "whether to act just as a seeder and not participate in any overlay apps" ),
        ('torrent', '',
         'file to add to database')
    ] )
    try:
        # Make sure we can have a directory with config files in a user-chosen
        # location
        presets = {}
        for tuple in defaults:
            presets[tuple[0]] = tuple[1]
        if len(argv) < 2:
            print "Usage: btlaunchmany.py <directory> <global options>\n"
            print "<directory> - directory to look for .torrent files (semi-recursive)"
            print get_usage(defaults, 80, presets)
            exit(1)

        tempconfig, tempargs = parseargs(argv[1:], defaults, 1, 1, presets)
        if tempconfig['config_path'] != '':
            config_path = tempconfig['config_path']
            configdir = ConfigDir('launchmany', config_path)
        else:
            configdir = ConfigDir('launchmany')
            config_path = configdir.getDirRoot()
            
        # original init
        defaultsToIgnore = ['responsefile', 'url', 'priority']
        configdir.setDefaults(defaults,defaultsToIgnore)
        configdefaults = configdir.loadConfig()
        defaults.append(('save_options',0,
         "whether to save the current options as the new default configuration " +
         "(only for btlaunchmany.py)"))

        config, args = parseargs(argv[1:], defaults, 1, 1, configdefaults)
        if config['save_options']:
            configdir.saveConfig(config)

        config['config_path'] = config_path
	config['internaltracker'] = 0
        if not os.path.isdir(config['config_path']):
            print "Tribler requires config_path parameter pointing to dir with ecpub.pem, etc.!"
            exit(1)
        configdir.deleteOldCacheData(config['expire_cache_data'])
        if not os.path.isdir(args[0]):
            raise ValueError("Warning: "+args[0]+" is not a directory")
        config['torrent_dir'] = args[0]
    except ValueError, e:
        print 'error: ' + str(e) + '\nrun with no args for parameter explanations'
        exit(1)
    
    install_dir = os.path.dirname(argv[0])
    tribler_init(config['config_path'],install_dir)

    config['text_mode'] = 1
    if config['seed_only'] == 1:
        # This disables all overlay apps, such as Buddycast etc.
        config['megacache'] = 0
        config['overlay'] = 0
        # Make sure we don't advertise we understand overlay conns
        #Encrypter.option_pattern = Encrypter.disabled_overlay_option_pattern 

    lm = LaunchMany(config, HeadlessDisplayer())
    #lm.start()

    if config['torrent'] != '':
        mdb = MetadataHandler.getInstance()
        torrentfilename = config['torrent']
        
        f = open(torrentfilename,"rb")
        bdata = f.read()
        f.close()
        data = bdecode(bdata)
        torrent_hash = sha(bencode(data['info'])).digest()
        metadata = bdata
        mdb.addTorrentToDB(torrentfilename, torrent_hash, metadata, hack = True)

    tribler_done(config['config_path'])

    # Particularly if we're a seeder we need to make sure that the Threads 
    # started to tell the tracker we're stopping are allowed to run to
    # completion. Otherwise the tracker admin may get messed up. It gets messed
    # up if we use different ports on each run and we don't unregister properly.
    # The tracker will then think the old instance is still running and give it
    # to peers.
    #
    print "Client shutting down. Sleeping a while to allow other threads to finish"
    sleep(4)
    print "Client done sleeping, other threads should have finished"


    if Exceptions:
        print '\nEXCEPTION:'
        print Exceptions[0]
        print >> sys.stderr,"btlaunchmany EXCEPTION: " + str(Exceptions[0])
        print 'please report this to '+report_email+'. Thank you!'
