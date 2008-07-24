# Written by John Hoffman
# see LICENSE.txt for license information

from inifile import ini_write, ini_read
from bencode import bencode, bdecode
from types import IntType, LongType, StringType, FloatType
from parseargs import defaultargs
from __init__ import product_name, version_short
import sys, os
from time import time, strftime
import shutil

from binascii import b2a_hex as tohex, a2b_hex as unhex

try:
    True
except:
    True = 1
    False = 0

try:
    realpath = os.path.realpath
except:
    realpath = lambda x: x
OLDICONPATH = os.path.abspath(os.path.dirname(realpath(sys.argv[0])))

DIRNAME = '.'+product_name


def copyfile(oldpath, newpath): # simple file copy, all in RAM
    try:
        f = open(oldpath, 'rb')
        r = f.read()
        success = True
    except:
        success = False
    try:
        f.close()
    except:
        pass
    if not success:
        return False
    try:
        f = open(newpath, 'wb')
        f.write(r)
    except:
        success = False
    try:
        f.close()
    except:
        pass
    return success


class ConfigDir:

    ###### INITIALIZATION TASKS ######

    def __init__(self, config_type = None, dir_root = None):
        self.config_type = config_type
        if config_type:
            config_ext = '.'+config_type
        else:
            config_ext = ''

        def check_sysvars(x):
            y = os.path.expandvars(x)
            if y != x and os.path.isdir(y):
                return y
            return None

        if dir_root is None or dir_root == '':
            for d in ['${APPDATA}', '${HOME}', '${HOMEPATH}', '${USERPROFILE}']:
                dir_root = check_sysvars(d)
                if dir_root:
                    break
            else:
                dir_root = os.path.expanduser('~')
                if not os.path.isdir(dir_root):
                    dir_root = os.path.abspath(os.path.dirname(sys.argv[0]))

            cur_dir_root = os.path.join(dir_root, DIRNAME)
        else:
            cur_dir_root = dir_root

        self.dir_root = cur_dir_root
        old_dir_root = os.path.join( dir_root, '.ABC' )

        # Arno: upgrade .ABC to .Tribler, if necessary
        # Arno,2007-05-03: disabled
        """
        old_exists = os.path.isdir(old_dir_root)
        cur_exists = os.path.isdir(cur_dir_root)
        if old_exists and not cur_exists:
            # upgrade old to new
            print "Upgrading 3.3.x config files to new version..."
            shutil.copytree(old_dir_root,cur_dir_root)
        """
            
        self._normal_init(config_ext)

    def _normal_init(self,config_ext):
        if not os.path.isdir(self.dir_root):
            os.mkdir(self.dir_root, 0700)    # exception if failed

        self.dir_icons = os.path.join(self.dir_root, 'icons')
        if not os.path.isdir(self.dir_icons):
            os.mkdir(self.dir_icons)

        self.dir_subscrip = os.path.join(self.dir_root, 'subscriptions')
        if not os.path.isdir(self.dir_subscrip):
            os.mkdir(self.dir_subscrip)

        self.dir_torrentcache = os.path.join(self.dir_root, 'torrentcache')
        if not os.path.isdir(self.dir_torrentcache):
            os.mkdir(self.dir_torrentcache)

        self.dir_datacache = os.path.join(self.dir_root, 'datacache')
        if not os.path.isdir(self.dir_datacache):
            os.mkdir(self.dir_datacache)

        self.dir_piececache = os.path.join(self.dir_root, 'piececache')
        if not os.path.isdir(self.dir_piececache):
            os.mkdir(self.dir_piececache)

        self.dir_itracker = os.path.join(self.dir_root, 'itracker')
        if not os.path.isdir(self.dir_itracker):
            os.mkdir(self.dir_itracker)

        self.configfile = os.path.join(self.dir_root, 'config'+config_ext+'.ini')
        self.statefile = os.path.join(self.dir_root, 'state'+config_ext)

        self.TorrentDataBuffer = {}

        # Arno: delete old log file
        try:
            old2fastbtlog = os.path.join(self.dir_root, '2fastbt.log')
            os.remove(old2fastbtlog)
        except:
            pass

    ###### CONFIG HANDLING ######

    def setDefaults(self, defaults, ignore=[]):
        self.config = defaultargs(defaults)
        for k in ignore:
            if self.config.has_key(k):
                del self.config[k]

    def checkConfig(self):
        return os.path.exists(self.configfile)

    def loadConfig(self):
        try:
            r = ini_read(self.configfile)['']
        except:
            return self.config
        l = self.config.keys()
        for k, v in r.items():
            if self.config.has_key(k):
                t = type(self.config[k])
                try:
                    if t == StringType:
                        self.config[k] = v
                    elif t == IntType or t == LongType:
                        self.config[k] = long(v)
                    elif t == FloatType:
                        self.config[k] = float(v)
                    l.remove(k)
                except:
                    pass
        if l: # new default values since last save
            self.saveConfig()
        return self.config

    def saveConfig(self, new_config = None):
        if new_config:
            for k, v in new_config.items():
                if self.config.has_key(k):
                    self.config[k] = v
        try:
            ini_write(self.configfile, self.config, 
                       'Generated by '+product_name+'/'+version_short+'\n'
                       + strftime('%x %X'))
            return True
        except:
            return False

    def getConfig(self):
        return self.config

    def getDirRoot(self):
        return self.dir_root

    ###### STATE HANDLING ######

    def getState(self):
        try:
            f = open(self.statefile, 'rb')
            r = f.read()
        except:
            r = None
        try:
            f.close()
        except:
            pass
        try:
            r = bdecode(r)
        except:
            r = None
        return r        

    def saveState(self, state):
        try:
            f = open(self.statefile, 'wb')
            f.write(bencode(state))
            success = True
        except:
            success = False
        try:
            f.close()
        except:
            pass
        return success


    ###### TORRENT HANDLING ######

    def getTorrents(self):
        d = {}
        for f in os.listdir(self.dir_torrentcache):
            f = os.path.basename(f)
            try:
                f, garbage = f.split('.')
            except:
                pass
            d[unhex(f)] = 1
        return d.keys()

    def getTorrentVariations(self, t):
        t = tohex(t)
        d = []
        for f in os.listdir(self.dir_torrentcache):
            f = os.path.basename(f)
            if f[:len(t)] == t:
                try:
                    garbage, ver = f.split('.')
                except:
                    ver = '0'
                d.append(int(ver))
        d.sort()
        return d

    def getTorrent(self, t, v = -1):
        t = tohex(t)
        if v == -1:
            v = max(self.getTorrentVariations(t))   # potential exception
        if v:
            t += '.'+str(v)
        try:
            f = open(os.path.join(self.dir_torrentcache, t), 'rb')
            r = bdecode(f.read())
        except:
            r = None
        try:
            f.close()
        except:
            pass
        return r

    def writeTorrent(self, data, t, v = -1):
        t = tohex(t)
        if v == -1:
            try:
                v = max(self.getTorrentVariations(t))+1
            except:
                v = 0
        if v:
            t += '.'+str(v)
        try:
            f = open(os.path.join(self.dir_torrentcache, t), 'wb')
            f.write(bencode(data))
        except:
            v = None
        try:
            f.close()
        except:
            pass
        return v


    ###### TORRENT DATA HANDLING ######

    def getTorrentData(self, t):
        if self.TorrentDataBuffer.has_key(t):
            return self.TorrentDataBuffer[t]
        t = os.path.join(self.dir_datacache, tohex(t))
        if not os.path.exists(t):
            return None
        try:
            f = open(t, 'rb')
            r = bdecode(f.read())
        except:
            r = None
        try:
            f.close()
        except:
            pass
        self.TorrentDataBuffer[t] = r
        return r

    def writeTorrentData(self, t, data):
        self.TorrentDataBuffer[t] = data
        try:
            f = open(os.path.join(self.dir_datacache, tohex(t)), 'wb')
            f.write(bencode(data))
            success = True
        except:
            success = False
        try:
            f.close()
        except:
            pass
        if not success:
            self.deleteTorrentData(t)
        return success

    def deleteTorrentData(self, t):
        try:
            os.remove(os.path.join(self.dir_datacache, tohex(t)))
        except:
            pass

    def getPieceDir(self, t):
        return os.path.join(self.dir_piececache, tohex(t))


    ###### EXPIRATION HANDLING ######

    def deleteOldCacheData(self, days, still_active = [], delete_torrents = False):
        if not days:
            return
        exptime = time() - (days*24*3600)
        names = {}
        times = {}

        for f in os.listdir(self.dir_torrentcache):
            p = os.path.join(self.dir_torrentcache, f)
            f = os.path.basename(f)
            try:
                f, garbage = f.split('.')
            except:
                pass
            try:
                f = unhex(f)
                assert len(f) == 20
            except:
                continue
            if delete_torrents:
                names.setdefault(f, []).append(p)
            try:
                t = os.path.getmtime(p)
            except:
                t = time()
            times.setdefault(f, []).append(t)
        
        for f in os.listdir(self.dir_datacache):
            p = os.path.join(self.dir_datacache, f)
            try:
                f = unhex(os.path.basename(f))
                assert len(f) == 20
            except:
                continue
            names.setdefault(f, []).append(p)
            try:
                t = os.path.getmtime(p)
            except:
                t = time()
            times.setdefault(f, []).append(t)

        for f in os.listdir(self.dir_piececache):
            p = os.path.join(self.dir_piececache, f)
            try:
                f = unhex(os.path.basename(f))
                assert len(f) == 20
            except:
                continue
            for f2 in os.listdir(p):
                p2 = os.path.join(p, f2)
                names.setdefault(f, []).append(p2)
                try:
                    t = os.path.getmtime(p2)
                except:
                    t = time()
                times.setdefault(f, []).append(t)
            names.setdefault(f, []).append(p)

        for k, v in times.items():
            if max(v) < exptime and not k in still_active:
                for f in names[k]:
                    try:
                        os.remove(f)
                    except:
                        try:
                            os.removedirs(f)
                        except:
                            pass


    def deleteOldTorrents(self, days, still_active = []):
        self.deleteOldCacheData(days, still_active, True)


    ###### OTHER ######

    def getIconDir(self):
        return self.dir_icons
