#!/usr/bin/env python

# Written by John Hoffman
# see LICENSE.txt for license information

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

from BitTornado.launchmanycore import LaunchMany
from BitTornado.download_bt1 import defaults, get_usage
from BitTornado.parseargs import parseargs
from threading import Event
from sys import argv, exit
import sys, os
from BitTornado import version, report_email
from BitTornado.ConfigDir import ConfigDir

assert sys.version >= '2', "Install Python 2.0 or greater"
try:
    True
except:
    True = 1
    False = 0

def hours(n):
    if n == 0:
        return 'complete!'
    try:
        n = int(n)
        assert n >= 0 and n < 5184000  # 60 days
    except:
        return '<unknown>'
    m, s = divmod(n, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return '%d hour %02d min %02d sec' % (h, m, s)
    else:
        return '%d min %02d sec' % (m, s)


Exceptions = []

class HeadlessDisplayer:
    def display(self, data):
        print ''
        if not data:
            self.message('no torrents')
        for x in data:
            ( name, status, progress, peers, seeds, seedsmsg, dist,
              uprate, dnrate, upamt, dnamt, size, t, msg ) = x
            print '"%s": "%s" (%s) - %sP%s%s%.3fD u%0.1fK/s-d%0.1fK/s u%dK-d%dK "%s"' % (
                        name, status, progress, peers, seeds, seedsmsg, dist,
                        uprate/1000, dnrate/1000, upamt/1024, dnamt/1024, msg)
        return False
            
    def message(self, s):
        print "### "+s

    def exception(self, s):
        Exceptions.append(s)
        self.message('SYSTEM ERROR - EXCEPTION GENERATED')


if __name__ == '__main__':
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
    ] )
    try:
        configdir = ConfigDir('launchmany')
        defaultsToIgnore = ['responsefile', 'url', 'priority']
        configdir.setDefaults(defaults,defaultsToIgnore)
        configdefaults = configdir.loadConfig()
        defaults.append(('save_options',0,
         "whether to save the current options as the new default configuration " +
         "(only for btlaunchmany.py)"))
        if len(argv) < 2:
            print "Usage: btlaunchmany.py <directory> <global options>\n"
            print "<directory> - directory to look for .torrent files (semi-recursive)"
            print get_usage(defaults, 80, configdefaults)
            exit(1)
        config, args = parseargs(argv[1:], defaults, 1, 1, configdefaults)
        if config['save_options']:
            configdir.saveConfig(config)
        configdir.deleteOldCacheData(config['expire_cache_data'])
        if not os.path.isdir(args[0]):
            raise ValueError("Warning: "+args[0]+" is not a directory")
        config['torrent_dir'] = args[0]
    except ValueError, e:
        print 'error: ' + str(e) + '\nrun with no args for parameter explanations'
        exit(1)

    LaunchMany(config, HeadlessDisplayer())
    if Exceptions:
        print '\nEXCEPTION:'
        print Exceptions[0]
        print 'please report this to '+report_email