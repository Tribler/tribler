# Written by ABC authors and Arno Bakker 
# see LICENSE.txt for license information
import wx
import sys
import os
from threading import Event, Semaphore
from Tribler.Core.Utilities.Crypto import sha
from traceback import print_exc
from random import gauss
#from cStringIO import StringIO

from wx.lib import masked

from Tribler.Lang.lang import Lang
from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.Core.defaults import dldefaults as BTDefaults
from Tribler.Core.defaults import DEFAULTPORT
from Tribler.Core.defaults import trackerdefaults as TrackerDefaults
from Tribler.Core.defaults import tdefdefaults as TorrentDefDefaults 
from Tribler.Core.BitTornado.parseargs import parseargs
from Tribler.Core.BitTornado.zurllib import urlopen
from Tribler.Core.BitTornado.__init__ import version_id
from Tribler.Core.simpledefs import DOWNLOAD, UPLOAD

if sys.platform == 'win32':
    from Tribler.Main.Utility.regchecker import RegChecker

from Tribler.Utilities.configreader import ConfigReader
from Tribler.Main.Utility.compat import convertINI, moveOldConfigFiles
from Tribler.Main.Utility.constants import * #IGNORE:W0611

from Tribler.Core.Utilities.utilities import find_prog_in_PATH  
  
################################################################
#
# Class: Utility
#
# Generic "glue" class that contains commonly used helper
# functions and helps to keep track of objects
#
################################################################
class Utility:
    def __init__(self, abcpath, configpath):
        
        self.version = version_id
        self.abcpath = abcpath

        # Find the directory to save config files, etc.
        self.dir_root = configpath
        moveOldConfigFiles(self)

        self.setupConfig()

        # Setup language files
        self.lang = Lang(self)

        # Convert old INI file
        convertINI(self)
        
        # Make torrent directory (if needed)
        self.MakeTorrentDir()
        
        self.setupTorrentMakerConfig()
        
        self.setupTorrentList()
        
        self.torrents = { "all": [], 
                          "active": {}, 
                          "inactive": {}, 
                          "pause": {}, 
                          "seeding": {}, 
                          "downloading": {} }

                        
        self.accessflag = Event()
        self.accessflag.set()
                            
        self.invalidwinfilenamechar = ''
        for i in range(32):
            self.invalidwinfilenamechar += chr(i)
        self.invalidwinfilenamechar += '"*/:<>?\\|'
        
        self.FILESEM   = Semaphore(1)

        warned = self.config.Read('torrentassociationwarned','int')
        if (sys.platform == 'win32' and not warned):     
            self.regchecker = RegChecker(self)
            self.config.Write('torrentassociationwarned','1')
        else:
            self.regchecker = None
            
        self.lastdir = { "save" : "", 
                         "open" : "", 
                         "log": "" }

        # Is ABC in the process of shutting down?
        self.abcquitting = False
#        self.abcdonequitting = False
        
        # Keep track of the last tab that was being viewed
        self.lasttab = { "advanced" : 0, 
                         "preferences" : 0 }
                         
        self.languages = {}
        
        # Keep track of all the "ManagedList" objects in use
        self.lists = {}
        
        self.abcfileframe = None
        self.abcbuddyframe = None
        
    def getVersion(self):
        return self.version
        
   
        
#===============================================================================
#    def getNumPeers(self):
#        return self.peer_db.getNumEncounteredPeers()#, self.peer_db.size()
#
#    def getNumFiles(self):
#        return self.torrent_db.getNumMetadataAndLive()#, self.torrent_db.size()
#===============================================================================
        
    def getConfigPath(self):
        return self.dir_root
        # TODO: python 2.3.x has a bug with os.access and unicode
        #return self.dir_root.decode(sys.getfilesystemencoding())
                         
    def setupConfig(self):        
        defaults = {
            # MiscPanel
            'language_file': 'english.lang',
            'confirmonclose': '1',
            'associate' : '1',
            # DiskPanel
            'removetorrent': '0',
            'diskfullthreshold': '1',
            # RateLimitPanel
            #'maxupload': '5', 
            'maxuploadrate': '0', 
            'maxdownloadrate': '0', 
            'maxseeduploadrate': '0', 
            # SeedingOptionsPanel
            'uploadoption': '0', 
            'uploadtimeh': '0', 
            'uploadtimem': '30', 
            'uploadratio': '100', 
            #AdvancedNetworkPanel
            #AdvancedDiskPanel
            #TriblerPanel
            'torrentcollectsleep':'15', # for RSS Subscriptions
            # VideoPanel
            'videoplaybackmode':'0',
            # Misc
            'enableweb2search':'0',
            'torrentassociationwarned':'0',
            # GUI
            'window_width': '1024', 
            'window_height': '670', 
            'detailwindow_width': '800', 
            'detailwindow_height': '500', 
            'prefwindow_width': '1000', 
            'prefwindow_height': '480', 
            'prefwindow_split': '400', 
            'sash_position' : '-185',
            't4t_option': 0, # Seeding items added by Boxun
            't4t_ratio': 100, # T4T seeding ratio added by Niels
            't4t_hours': 0,
            't4t_mins': 30,
            'g2g_option': 1,
            'g2g_ratio': 75,
            'g2g_hours': 0,
            'g2g_mins': 30,
            'family_filter': 1,
            'window_x': "",
            'window_y': "",
            'popup_player': 0,
            'use_bundle_magic': 0,
            
            # WebUI
            'use_webui':0,
            'webui_port':8080,
            
            # swift reseed
            'swiftreseed':1
        }

        if sys.platform == 'win32':
            defaults['mintray'] = '2'
            # Don't use double quotes here, those are lost when this string is stored in the
            # abc.conf file in INI-file format. The code that starts the player will add quotes
            # if there is a space in this string.
            progfilesdir = os.path.expandvars('${PROGRAMFILES}')
            #defaults['videoplayerpath'] = progfilesdir+'\\VideoLAN\\VLC\\vlc.exe'
            # Path also valid on MS Vista
            defaults['videoplayerpath'] = progfilesdir+'\\Windows Media Player\\wmplayer.exe'
            defaults['videoanalyserpath'] = self.getPath()+'\\ffmpeg.exe'
        elif sys.platform == 'darwin':
            defaults['mintray'] = '0'  # tray doesn't make sense on Mac
            vlcpath = find_prog_in_PATH("vlc")
            if vlcpath is None:
                #second try
                vlcpath = "/Applications/VLC.app"
                if not os.path.exists(vlcpath):
                    vlcpath = None
            
            if vlcpath is None:
                    defaults['videoplayerpath'] = "/Applications/QuickTime Player.app"
            else:
                defaults['videoplayerpath'] = vlcpath
            ffmpegpath = find_prog_in_PATH("ffmpeg")
            if ffmpegpath is None:
                defaults['videoanalyserpath'] = "vlc/ffmpeg"
            else:
                defaults['videoanalyserpath'] = ffmpegpath
        else:
            defaults['mintray'] = '0'  # Still crashes on Linux sometimes 
            vlcpath = find_prog_in_PATH("vlc")
            if vlcpath is None:
                defaults['videoplayerpath'] = "vlc"
            else:
                defaults['videoplayerpath'] = vlcpath
            ffmpegpath = find_prog_in_PATH("ffmpeg")
            if ffmpegpath is None:
                defaults['videoanalyserpath'] = "ffmpeg"
            else:
                defaults['videoanalyserpath'] = ffmpegpath

        configfilepath = os.path.join(self.getConfigPath(), "abc.conf")
        self.config = ConfigReader(configfilepath, "ABC", defaults)

    @staticmethod
    def _convert__helper_4_1__4_2(abc_config, set_config_func, name, convert=None):
        if convert is None:
            convert = lambda x: x
        if abc_config.Exists(name):
            v = abc_config.Read(name)
            try:
                v = convert(v)
            except:
                pass
            else:
                set_config_func(v)
                abc_config.DeleteEntry(name)

    def convert__presession_4_1__4_2(self, session_config):
        bool_ = lambda x: x=="1" and True or False
        self._convert__helper_4_1__4_2(self.config, session_config.set_buddycast, "enablerecommender", bool_)
        self._convert__helper_4_1__4_2(self.config, session_config.set_buddycast_max_peers, "buddy_num", int)
        #self._convert__helper_4_1__4_2(self.config, session_config.set_download_help, "enabledlhelp", bool_)
        self._convert__helper_4_1__4_2(self.config, session_config.set_internal_tracker_url, "internaltrackerurl")
        self._convert__helper_4_1__4_2(self.config, session_config.set_listen_port, "minport", int)
        self._convert__helper_4_1__4_2(self.config, session_config.set_nickname, "myname")
        self._convert__helper_4_1__4_2(self.config, session_config.set_start_recommender, "startrecommender", bool_)
        self._convert__helper_4_1__4_2(self.config, session_config.set_stop_collecting_threshold, "stopcollectingthreshold", int)
        self._convert__helper_4_1__4_2(self.config, session_config.set_torrent_collecting, "enabledlcollecting", bool_)
        self._convert__helper_4_1__4_2(self.config, session_config.set_ip_for_tracker, "ip")
        self._convert__helper_4_1__4_2(self.config, session_config.set_bind_to_addresses, "bind", lambda x:[x])
        self._convert__helper_4_1__4_2(self.config, session_config.set_upnp_mode, "upnp_nat_access", int)

    def convert__postsession_4_1__4_2(self, session, default_download_config):

        # the mugshot was stored in icons/<hash>.jpg
        # however... what is the permid???
        safename = "%s.jpg" % sha(session.get_permid()).hexdigest()
        safepath = os.path.join(self.dir_root, "icons", safename)
        if os.path.exists(safepath):
            session.set_mugshot(open(safepath, "r").read(), "image/jpeg")        
            os.remove(safepath)

        bool_ = lambda x: x=="1" and True or False
        self._convert__helper_4_1__4_2(self.config, default_download_config.set_alloc_rate, "alloc_rate", int)
        self._convert__helper_4_1__4_2(self.config, default_download_config.set_alloc_type, "alloc_type")
        self._convert__helper_4_1__4_2(self.config, default_download_config.set_dest_dir, "defaultfolder")
        self._convert__helper_4_1__4_2(self.config, default_download_config.set_double_check_writes, "double_check", bool_)
        self._convert__helper_4_1__4_2(self.config, default_download_config.set_lock_files, "lock_files", bool_)
        self._convert__helper_4_1__4_2(self.config, default_download_config.set_lock_while_reading, "lock_while_reading", bool_)
        self._convert__helper_4_1__4_2(self.config, default_download_config.set_max_conns, "max_connections", int)
        self._convert__helper_4_1__4_2(self.config, default_download_config.set_max_files_open, "max_files_open", int)
        self._convert__helper_4_1__4_2(self.config, default_download_config.set_triple_check_writes, "trible_check", bool_)

    def setupTorrentMakerConfig(self):
        # Arno, 2008-03-27: To keep fileformat compatible
        defaults = {
            'piece_size': '0', # An index into TorrentMaker.FileInfoPanel.piece_choices
            'comment': TorrentDefDefaults['comment'], 
            'created_by': TorrentDefDefaults['created by'], 
            'announcedefault': TorrentDefDefaults['announce'], 
            'announcehistory': '', 
            'announce-list': TorrentDefDefaults['announce-list'], 
            'httpseeds': TorrentDefDefaults['httpseeds'], 
            'makehash_md5': str(TorrentDefDefaults['makehash_md5']), 
            'makehash_crc32': str(TorrentDefDefaults['makehash_crc32']), 
            'makehash_sha1': str(TorrentDefDefaults['makehash_sha1']),
            'startnow': '1', 
            'savetorrent': '1',
            'createmerkletorrent': '1',
            'createtorrentsig': '0',
            'useitracker': '1',
            'manualtrackerconfig': '0'
        }
        
        torrentmakerconfigfilepath = os.path.join(self.getConfigPath(), "maker.conf")
        self.makerconfig = ConfigReader(torrentmakerconfigfilepath, "ABC/TorrentMaker", defaults)
        
    def setupTorrentList(self):
        torrentfilepath = os.path.join(self.getConfigPath(), "torrent.list")
        self.torrentconfig = ConfigReader(torrentfilepath, "list0")
               
    # Initialization that has to be done after the wx.App object
    # has been created
    def postAppInit(self,iconpath):
        try:
            self.icon = wx.Icon(iconpath, wx.BITMAP_TYPE_ICO)
        except:
            pass
            
        #makeActionList(self)
            
    def getLastDir(self, operation = "save"):
        lastdir = self.lastdir[operation]
        
        if operation == "save":
            if not os.access(lastdir, os.F_OK):
                lastdir = self.config.Read('defaultfolder')
        
        if not os.access(lastdir, os.F_OK):
            lastdir = ""
            
        return lastdir

    def setLastDir(self, operation, dir ):
        self.lastdir[operation] = dir

    def getPath(self):
        return self.abcpath
        #return self.abcpath.decode(sys.getfilesystemencoding())
    
    def getMaxDown(self):
        maxdownloadrate = self.config.Read('maxdownloadrate', 'int')
        if maxdownloadrate == 0:
            return 'unlimited'
        return str(maxdownloadrate)
    
    def setMaxDown(self, valdown):
        if valdown == 'unlimited':
            self.ratelimiter.set_global_max_speed(DOWNLOAD, 0)
            self.config.Write('maxdownloadrate', '0')
        else:
            self.ratelimiter.set_global_max_speed(DOWNLOAD, int(valdown))
            self.config.Write('maxdownloadrate', valdown)
    
    def getMaxUp(self):
        maxuploadrate = self.config.Read('maxuploadrate', 'int')
        if maxuploadrate == -1:
            return 0        
        elif maxuploadrate == 0:
            return 'unlimited'
        return str(maxuploadrate)
        
    def setMaxUp(self, valup):
        if valup == 'unlimited':
            self.ratelimiter.set_global_max_speed(UPLOAD, 0)
            self.ratelimiter.set_global_max_seedupload_speed(0)
            self.config.Write('maxuploadrate', '0')
            self.config.Write('maxseeduploadrate', '0')
        elif valup == '0':
            self.ratelimiter.set_global_max_speed(UPLOAD, 0.0001)
            self.ratelimiter.set_global_max_seedupload_speed(0.0001)
            self.config.Write('maxuploadrate', '-1')
            self.config.Write('maxseeduploadrate', '-1')
        else: 
            self.ratelimiter.set_global_max_speed(UPLOAD, int(valup))
            self.ratelimiter.set_global_max_seedupload_speed(int(valup))
            self.config.Write('maxuploadrate', valup)
            self.config.Write('maxseeduploadrate', valup)

    def eta_value(self, n, truncate = 3):
        if n == -1:
            return '<unknown>'
        if not n:
            return ''
        n = int(n)
        week, r1 = divmod(n, 60 * 60 * 24 * 7)
        day, r2 = divmod(r1, 60 * 60 * 24)
        hour, r3 = divmod(r2, 60 * 60)
        minute, sec = divmod(r3, 60)
    
        if week > 1000:
            return '<unknown>'
    
        weekstr = '%d' % (week) + self.lang.get('l_week')
        daystr = '%d' % (day) + self.lang.get('l_day')
        hourstr = '%d' % (hour) + self.lang.get('l_hour')
        minutestr = '%d' % (minute) + self.lang.get('l_minute')
        secstr = '%02d' % (sec) + self.lang.get('l_second')
            
        if week > 0:
            text = weekstr
            if truncate > 1:
                text += ":" + daystr
            if truncate > 2:
                text += "-" + hourstr
        elif day > 0:
            text = daystr
            if truncate > 1:
                text += "-" + hourstr
            if truncate > 2:
                text += ":" + minutestr
        elif hour > 0:
            text = hourstr
            if truncate > 1:
                text += ":" + minutestr
            if truncate > 2:
                text += ":" + secstr   
        else:
            text = minutestr
            if truncate > 1:
                text += ":" + secstr

        return  text
            
    def getMetainfo(self, src, openoptions = 'rb', style = "file"):
        return getMetainfo(src,openoptions=openoptions,style=style)
        
    def speed_format(self, s, truncate = 1, stopearly = None):
        return self.size_format(s, truncate, stopearly) + "/" + self.lang.get('l_second')

    def speed_format_new(self, s):
        if s != None:
            if s < 102400:
                text = '%2.1f KB/s' % (s/1024.0)
            elif s < 1022797:
                text = '%d KB/s' % (s//1024)
            elif s < 104857600:
                text = '%2.1f MB/s' % (s/1048576.0)
            elif s < 1047527425L:
                text = '%d MB/s' % (s//1048576)
            elif s < 107374182400L:
                text = '%2.1f GB/s' % (s/1073741824.0)
            elif s < 1072668082177L:
                text = '%d GB/s' % (s//1073741824)
            else:
                text = '%2.1f TB/s' % (s//1099511627776L)
    
            return text
        return ''

    def size_format(self, s, truncate = None, stopearly = None, applylabel = True, rawsize = False, showbytes = False, labelonly = False, textonly = False):
        size = 0.0
        label = ""
        
        if truncate is None:
            truncate = 2
        
        if ((s < 1024) and showbytes and stopearly is None) or stopearly == "Byte":
            truncate = 0
            size = s
            text = "Byte"
        elif ((s < 1048576) and stopearly is None) or stopearly == "KB":
            size = (s/1024.0)
            text = "KB"
        elif ((s < 1073741824L) and stopearly is None) or stopearly == "MB":
            size = (s/1048576.0)
            text = "MB"
        elif ((s < 1099511627776L) and stopearly is None) or stopearly == "GB":
            size = (s/1073741824.0)
            text = "GB"
        else:
            size = (s/1099511627776.0)
            text = "TB"

        if textonly:
            return text
        
        label = self.lang.get(text)
        if labelonly:
            return label
            
        if rawsize:
            return size
                        
        # At this point, only accepting 0, 1, or 2
        if truncate == 0:
            text = ('%.0f' % size)
        elif truncate == 1:
            text = ('%.1f' % size)
        else:
            text = ('%.2f' % size)
            
        if applylabel:
            text += ' ' + label
            
        return text
        
    def round_range(self, x):
        returnar = set()
        for i in range(2500):
            value = int(gauss(x, 100))
            if value < 0:
                continue
    
            diff = abs(value - x)
            if diff < 2:
                pass
            elif diff < 10 and x < 50:
                value = int(round(value / 3.0) * 3)
            elif diff < 75:
                value = int(round(value / 25.0) * 25)
            elif diff < 450:
                value = int(round(value / 75.0) * 75)
            else:
                value = int(round(value / 150.0) * 150)
    
            returnar.add(value)
        returnar = list(returnar)
        returnar.sort()
        return returnar
    
    def makeNumCtrl(self, parent, value, integerWidth = 6, fractionWidth = 0, min = 0, max = None, size = wx.DefaultSize):
        if size != wx.DefaultSize:
            autoSize = False
        else:
            autoSize = True
        return masked.NumCtrl(parent, 
                              value = value, 
                              size = size, 
                              integerWidth = integerWidth, 
                              fractionWidth = fractionWidth, 
                              allowNegative = False, 
                              min = min, 
                              max = max, 
                              groupDigits = False, 
                              useFixedWidthFont = False, 
                              autoSize = autoSize)
            
    def MakeTorrentDir(self):
        torrentpath = os.path.join(self.getConfigPath(), "torrent")
        pathexists = os.access(torrentpath, os.F_OK)
        # If the torrent directory doesn't exist, create it now
        if not pathexists:
            os.mkdir(torrentpath)
            
    def RemoveEmptyDir(self, basedir, removesubdirs = True):
        # remove subdirectories
        if removesubdirs:
            for root, dirs, files in os.walk(basedir, topdown = False):
                for name in dirs:
                    dirname = os.path.join(root, name)

                    # Only try to delete if it exists
                    if os.access(dirname, os.F_OK):
                        if not os.listdir(dirname):
                            os.rmdir(dirname)
        #remove folder
        if os.access(basedir, os.F_OK):
            if not os.listdir(basedir):
                os.rmdir(basedir)
        
    def makeBitmap(self, bitmap, trans_color = wx.Colour(200, 200, 200)):
        button_bmp = wx.Bitmap(os.path.join(self.getPath(), 'icons', bitmap), wx.BITMAP_TYPE_BMP)
        button_mask = wx.Mask(button_bmp, trans_color)
        button_bmp.SetMask(button_mask)
        return button_bmp

    def makeBitmapButton(self, parent, bitmap, tooltip, event, trans_color = wx.Colour(200, 200, 200), padx=18, pady=4):
        tooltiptext = self.lang.get(tooltip)
        
        button_bmp = self.makeBitmap(bitmap, trans_color)
        
        ID_BUTTON = wx.NewId()
        button_btn = wx.BitmapButton(parent, ID_BUTTON, button_bmp, size=wx.Size(button_bmp.GetWidth()+padx, button_bmp.GetHeight()+pady))
        button_btn.SetToolTipString(tooltiptext)
        parent.Bind(wx.EVT_BUTTON, event, button_btn)
        return button_btn

    def makeBitmapButtonFit(self, parent, bitmap, tooltip, event, trans_color = wx.Colour(200, 200, 200)):
        tooltiptext = self.lang.get(tooltip)
        
        button_bmp = self.makeBitmap(bitmap, trans_color)
        
        ID_BUTTON = wx.NewId()
        button_btn = wx.BitmapButton(parent, ID_BUTTON, button_bmp, size=wx.Size(button_bmp.GetWidth(), button_bmp.GetHeight()))
        button_btn.SetToolTipString(tooltiptext)
        parent.Bind(wx.EVT_BUTTON, event, button_btn)
        return button_btn
    
    def getBTParams(self, skipcheck = False):
        # Construct BT params
        ###########################
        btparams = []
        
        btparams.append("--display_interval")
        btparams.append(self.config.Read('display_interval'))
        
        # Use single port only
        btparams.append("--minport")
        btparams.append(self.config.Read('minport'))
        btparams.append("--maxport")
        btparams.append(self.config.Read('minport'))
        
#        btparams.append("--random_port")
#        btparams.append(self.config.Read('randomport'))
        
        #if self.config.Read('ipv6') == "1":
        #    btparams.append("--ipv6_enable")
        #    btparams.append(self.config.Read('ipv6'))
        #    btparams.append("--ipv6_binds_v4")
        #    btparams.append(self.config.Read('ipv6_binds_v4'))
        
        # Fast resume
        btparams.append("--selector_enabled")
        btparams.append(self.config.Read('fastresume'))
        
        btparams.append("--auto_kick")
        btparams.append(self.config.Read('kickban'))
        btparams.append("--security")
        btparams.append(self.config.Read('notsameip'))

        btparams.append("--max_upload_rate")
        btparams.append("0")
               
        paramlist = [ "ip", 
                      "bind", 
                      "alloc_rate", 
                      "alloc_type", 
                      "double_check", 
                      "triple_check", 
                      "lock_while_reading", 
                      "lock_files", 
                      "min_peers", 
                      "max_files_open", 
                      "max_connections", 
                      "upnp_nat_access", 
                      "auto_flush",
                      "ut_pex_max_addrs_from_peer"]

        for param in paramlist:
            value = self.config.Read(param)
            if value != "":
                btparams.append("--" + param)
                btparams.append(value)

        config, args = parseargs(btparams, BTDefaults)
            
        return config

    def getTrackerParams(self):
        tconfig = {}
        for k,v,expl in TrackerDefaults:
            tconfig[k] = v
        
        tconfig['port'] = DEFAULTPORT
        dir = os.path.join(self.getConfigPath(),'itracker')
        dfile = os.path.join(dir,'tracker.db')
        tconfig['dfile'] = dfile
        tconfig['allowed_dir'] = dir
        tconfig['favicon'] = os.path.join(self.getPath(),'tribler.ico')
        #tconfig['save_dfile_interval'] = 20
        tconfig['dfile_format'] = 'pickle' # We use unicode filenames, so bencode won't work
        
        return tconfig
        


    # Check if str is a valid Windows file name (or unit name if unit is true)
    # If the filename isn't valid: returns a fixed name
    # If the filename is valid: returns an empty string
    def fixWindowsName(self, name, unit = False):        
        if unit and (len(name) != 2 or name[1] != ':'):
            return 'c:'
        if not name or name == '.' or name == '..':
            return '_'
        if unit:
            name = name[0]
        fixed = False
        if len(name) > 250:
            name = name[:250]
            fixed = True
        fixedname = ''
        spaces = 0
        for c in name:
            if c in self.invalidwinfilenamechar:
                fixedname += '_'
                fixed = True
            else:
                fixedname += c
                if c == ' ':
                    spaces += 1
        if fixed:
            return fixedname
        elif spaces == len(name):
            # contains only spaces
            return '_'
        else:
            return ''

    def checkWinPath(self, parent, pathtocheck):
        if pathtocheck and pathtocheck[-1] == '\\' and pathtocheck != '\\\\':
            pathitems = pathtocheck[:-1].split('\\')
        else:
            pathitems = pathtocheck.split('\\')
        nexttotest = 1
        if self.isPathRelative(pathtocheck):
            # Relative path
            # Empty relative path is allowed
            if pathtocheck == '':
                return True
            fixedname = self.fixWindowsName(pathitems[0])
            if fixedname:
                dlg = wx.MessageDialog(parent, 
                                       pathitems[0] + '\n' + \
                                       self.lang.get('invalidwinname') + '\n'+ \
                                       self.lang.get('suggestedname') + '\n\n' + \
                                       fixedname, 
                                       self.lang.get('error'), wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
                return False
        else:
            # Absolute path
            # An absolute path must have at least one '\'
            if not '\\' in pathtocheck:
                dlg = wx.MessageDialog(parent, pathitems[0] + '\n' + self.lang.get('errorinvalidpath'), 
                                       self.lang.get('error'), wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
                return False
            if pathtocheck[:2] != '\\\\':
                # Not a network path
                fixedname = self.fixWindowsName(pathitems[0], unit = True)
                if fixedname:
                    dlg = wx.MessageDialog(parent, 
                                           pathitems[0] + '\n' + \
                                           self.lang.get('invalidwinname') + \
                                           fixedname, 
                                           self.lang.get('error'), wx.ICON_ERROR)
                    dlg.ShowModal()
                    dlg.Destroy()
                    return False
            else:
                # Network path
                nexttotest = 2

        for name in pathitems[nexttotest:]:
            fixedname = self.fixWindowsName(name)
            if fixedname:
                dlg = wx.MessageDialog(parent, name + '\n' + self.lang.get('errorinvalidwinname') + fixedname, 
                                       self.lang.get('error'), wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
                return False

        return True

    def isPathRelative(self, path):
        if len(path) < 2 or path[1] != ':' and path[:2] != '\\\\':
            return True
        return False

    # Get a dictionary with information about a font
    def getInfoFromFont(self, font):
        default = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        
        try:
            if font.Ok():
                font_to_use = font
            else:
                font_to_use = default
        
            fontname = font_to_use.GetFaceName()
            fontsize = font_to_use.GetPointSize()
            fontstyle = font_to_use.GetStyle()
            fontweight = font_to_use.GetWeight()
                
            fontinfo = {'name': fontname, 
                        'size': fontsize, 
                        'style': fontstyle, 
                        'weight': fontweight }
        except:
            fontinfo = {'name': "", 
                        'size': 8, 
                        'style': wx.FONTSTYLE_NORMAL, 
                        'weight': wx.FONTWEIGHT_NORMAL }
    
        return fontinfo

            
    def getFontFromInfo(self, fontinfo):
        size = fontinfo['size']
        name = fontinfo['name']
        style = fontinfo['style']        
        weight = fontinfo['weight']
                
        try:
            font = wx.Font(size, wx.DEFAULT, style, weight, faceName = name)
        except:
            font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        
        return font

    # Make an entry for a popup menu
    def makePopup(self, menu, event = None, label = "", extralabel = "", bindto = None, type="normal", status=""):
        text = ""
        if label != "":
            text = self.lang.get(label)
        text += extralabel
        
        newid = wx.NewId()        
        if event is not None:
            if bindto is None:
                bindto = menu
            bindto.Bind(wx.EVT_MENU, event, id = newid)
        
        if type == "normal":    
            menu.Append(newid, text)
        elif type == "checkitem":
            menu.AppendCheckItem(newid, text)
            if status == "active":
                menu.Check(newid,True)
        
        if event is None:
            menu.Enable(newid, False)
        
        return newid


def printTorrent(torrent, pre = ''):
    for key, value in torrent.items():
        if type(value) == dict:
            printTorrent(value, pre+' '+key)
        elif key.lower() not in ['pieces', 'thumbnail', 'preview']:
            print '%s | %s: %s' % (pre, key, value)
            
def getMetainfo(src, openoptions = 'rb', style = "file"):
    if src is None:
        return None
    
    metainfo = None
    try:
        metainfo_file = None
        # We're getting a url
        if style == "rawdata":
            return bdecode(src)
        elif style == "url":
            metainfo_file = urlopen(src)
        # We're getting a file that exists
        elif os.access(src, os.R_OK):
            metainfo_file = open(src, openoptions)
        
        if metainfo_file is not None:
            metainfo = bdecode(metainfo_file.read())
            metainfo_file.close()
    except:
        print_exc()
        if metainfo_file is not None:
            try:
                metainfo_file.close()
            except:
                pass
        metainfo = None
    return metainfo

def copyTorrent(torrent):
    # make a copy of a torrent, to check if any of its "basic" props has been changed
    # NB: only copies basic properties
    basic_keys =  ['infohash', 'num_seeders','num_leechers',
                   'myDownloadHistory','web2', 'preview', 'simRank']
    if torrent is None:
        return None
    ntorrent = {}
    for key in basic_keys:
        value = torrent.get(key)
        if not value is None:
            ntorrent[key] = value
    return ntorrent

def similarTorrent(t1, t2):
    # make a copy of a torrent, to check if any of its "basic" props has been changed
    # NB: only copies basic properties
    basic_keys =  ['infohash', 'num_seeders','num_leechers',
                   'myDownloadHistory','web2', 'preview', 'simRank']
    
    if (t1 is None or t2 is None):
        return (t1 is None and t2 is None)

    for key in basic_keys:
        v1 = t1.get(key)
        v2 = t2.get(key)
        if v1 != v2:
            return False
    return True

def copyPeer(peer):
    # make a copy of a peer, to check if any of its "basic" props has been changed
    # NB: only copies basic properties
    basic_keys =  ['permid', 'last_connected', 'simRank', 'similarity', 'name', 'friend', 
                   'num_peers', 'num_torrents', 'num_prefs', 'num_queries']
    if peer is None:
        return None
    npeer = {}
    for key in basic_keys:
        value = peer.get(key)
        if not value is None:
            npeer[key] = value
    return npeer

def similarPeer(t1, t2):
    # make a copy of a peer, to check if any of its "basic" props has been changed
    # NB: only copies basic properties
    basic_keys =  ['permid', 'last_connected', 'simRank', 'similarity', 'name', 'friend', 
                   'num_peers', 'num_torrents', 'num_prefs', 'num_queries']
    
    if (t1 is None or t2 is None):
        return (t1 is None and t2 is None)

    for key in basic_keys:
        v1 = t1.get(key)
        v2 = t2.get(key)
        if v1 != v2:
            return False
    return True


