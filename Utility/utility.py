import wx
import sys
import os
import socket
import random

from Lang.lang import Lang
from threading import Event, Semaphore
from time import sleep
#from traceback import print_exc
#from cStringIO import StringIO

from wx.lib import masked

from BitTornado.ConfigDir import ConfigDir
from BitTornado.bencode import bdecode
from BitTornado.download_bt1 import defaults as BTDefaults
from BitTornado.parseargs import parseargs
from BitTornado.zurllib import urlopen

from ABC.Actions.actions import makeActionList

if (sys.platform == 'win32'):
    from Utility.regchecker import RegChecker

from Utility.configreader import ConfigReader
from Utility.compat import convertINI, moveOldConfigFiles
from Utility.constants import * #IGNORE:W0611

  
################################################################
#
# Class: Utility
#
# Generic "glue" class that contains commonly used helper
# functions and helps to keep track of objects
#
################################################################
class Utility:
    def __init__(self, abcpath):
        self.abcpath = abcpath

        # Find the directory to save config files, etc.
        self.setupConfigPath()
        moveOldConfigFiles(self)

        self.setupConfig()

        # Setup language files
        self.lang = Lang(self)

        # Convert old INI file
        convertINI(self)
        
        # Make torrent directory (if needed)
        self.MakeTorrentDir()
        
        self.setupWebConfig()
        
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

        if (sys.platform == 'win32'):        
            self.regchecker = RegChecker(self)

        self.lastdir = { "save" : self.config.Read('defaultfolder'), 
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
        
    def setupConfigPath(self):
        configdir = ConfigDir()
        self.dir_root = configdir.dir_root        
        
    def getConfigPath(self):
        return self.dir_root
                         
    def setupConfig(self):        
        defaults = {
            'defrentorwithdest': '1', 
            'minport': str(random.randint(10000, 60000)), 
            'maxport': '50000', 
            'maxupload': '5', 
            'maxuploadrate': '0', 
            'maxdownloadrate': '0', 
            'maxseeduploadrate': '0', 
            'numsimdownload': '2', 
            'uploadoption': '2', 
            'uploadtimeh': '0', 
            'uploadtimem': '30', 
            'uploadratio': '100', 
            'removetorrent': '0', 
            'setdefaultfolder': '0', 
            'defaultfolder': 'c:\\', 
            'defaultmovedir': 'c:\\', 
            'mintray': '0', 
            'trigwhenfinishseed': '1', 
            'confirmonclose': '1', 
            'kickban': '1', 
            'notsameip': '1', 
            'ipv6': '0', 
            'ipv6_binds_v4': '1', 
            'min_peers': '20', 
            'max_initiate': '40', 
            'alloc_type': 'normal', 
            'alloc_rate': '2', 
            'max_files_open': '50', 
            'max_connections': '0', 
            'lock_files': '1', 
            'lock_while_reading': '0', 
            'double_check': '1', 
            'triple_check': '0', 
            'timeouttracker': '15', 
            'timeoutdownload': '30', 
            'timeoutupload': '1', 
            'scrape': '0', 
            'defaultpriority': '2', 
            'failbehavior': '0', 
            'language_file': 'english.lang', 
            'urm': '0', 
            'urmupthreshold': '10', 
            'urmdelay': '60', 
            'stripedlist': '0', 
#            'mode': '1',
            'window_width': '710', 
            'window_height': '400', 
            'detailwindow_width': '610', 
            'detailwindow_height': '500', 
            'prefwindow_width': '530', 
            'prefwindow_height': '400', 
            'prefwindow_split': '130', 
            'column4_rank': '0', # Title
            'column4_width': '150', 
            'column5_rank': '1', # Progress
            'column5_width': '60', 
            'column6_rank': '2', # BT Status
            'column6_width': '100', 
            'column7_rank': '8', # Priority
            'column7_width': '50', 
            'column8_rank': '5', # ETA
            'column8_width': '85', 
            'column9_rank': '6', # Size
            'column9_width': '75', 
            'column10_rank': '3', # DL Speed
            'column10_width': '65', 
            'column11_rank': '4', # UL Speed
            'column11_width': '60', 
            'column12_rank': '7', # %U/D Size
            'column12_width': '60', 
            'column13_rank': '9', # Error Message
            'column13_width': '60', 
            'column14_rank': '-1', # #Connected Seed
            'column14_width': '60', 
            'column15_rank': '-1', # #Connected Peer
            'column15_width': '60', 
            'column16_rank': '-1', # #Seeing Copies
            'column16_width': '60', 
            'column17_rank': '-1', # Peer Avg Progress
            'column17_width': '60', 
            'column18_rank': '-1', # Download Size
            'column18_width': '75', 
            'column19_rank': '-1', # Upload Size
            'column19_width': '75', 
            'column20_rank': '-1', # Total Speed
            'column20_width': '80', 
            'column21_rank': '-1', # Torrent Name
            'column21_width': '150', 
            'column22_rank': '-1', # Destination
            'column22_width': '150', 
            'column23_rank': '-1', # Seeding Time
            'column23_width': '85', 
            'column24_rank': '-1', # Connections
            'column24_width': '60', 
            'column25_rank': '-1', # Seeding Option
            'column25_width': '80', 
            'fastresume': '1', 
            'randomport': '1', 
            'savecolumnwidth': '1', 
#            'forcenewdir': '1', 
            'upnp_nat_access': '0', 
            'buffer_write' : '4', 
            'buffer_read' : '1', 
            'auto_flush' : '0', 
            'associate' : '1', 
            'movecompleted': '0', 
            'spew0_rank': '0', # Optimistic Unchoke
            'spew0_width': '24', 
            'spew1_rank': '1', # IP
            'spew1_width': '132', 
            'spew2_rank': '2', # Local / Remote
            'spew2_width': '24', 
            'spew3_rank': '3', # Upload Rate
            'spew3_width': '72', 
            'spew4_rank': '4', # Interested
            'spew4_width': '24', 
            'spew5_rank': '5', # Choking
            'spew5_width': '24', 
            'spew6_rank': '6', # Download Rate
            'spew6_width': '72', 
            'spew7_rank': '7', # Interesting
            'spew7_width': '24', 
            'spew8_rank': '8', # Choked
            'spew8_width': '24', 
            'spew9_rank': '9', # Snubbed
            'spew9_width': '24', 
            'spew10_rank': '10', # Downloaded
            'spew10_width': '84', 
            'spew11_rank': '11', # Uploaded
            'spew11_width': '84', 
            'spew12_rank': '12', # Peer Progress
            'spew12_width': '72', 
            'spew13_rank': '-1', # Peer Download Speed
            'spew13_width': '72', 
            'spew14_rank': '13', # Peer PermID
            'spew14_width': '72', 
            'fileinfo0_rank': '0', # Filename
            'fileinfo0_width': '300', 
            'fileinfo1_rank': '1', # Size
            'fileinfo1_width': '100', 
            'fileinfo2_rank': '2', # Progress
            'fileinfo2_width': '60', 
            'fileinfo3_rank': '3', # MD5 Hash
            'fileinfo3_width': '200', 
            'fileinfo4_rank': '-1', # CRC32 Hash
            'fileinfo4_width': '200', 
            'fileinfo5_rank': '-1', # SHA1 Hash
            'fileinfo5_width': '200', 
            'fileinfo6_rank': '-1', # ED2K Hash
            'fileinfo6_width': '200', 
            'color_startup': '000000000', 
            'color_disconnected': '100100100', 
            'color_noconnections': '200000000', 
            'color_noincoming': '150150000', 
            'color_nocomplete': '000000150', 
            'color_good': '000150000', 
            'color_stripe': '245245245', 
            'display_interval': '0.8', 
            'listfont': '', 
            'diskfullthreshold': '0', 
            'updatepeers_interval': '5',
            'update_preference_interval': '36000',     # 
#            'showmenuicons': '1',
            'icons_toolbarbottom': [ACTION_MOVEUP, 
                                    ACTION_MOVEDOWN, 
                                    ACTION_MOVETOP, 
                                    ACTION_MOVEBOTTOM, 
                                    -1, 
                                    ACTION_CLEARCOMPLETED, 
                                    -1, 
                                    ACTION_PAUSEALL, 
                                    ACTION_STOPALL, 
                                    ACTION_UNSTOPALL, 
                                    -1], 
            'icons_toolbartop': [ACTION_ADDTORRENT, 
                                 ACTION_ADDTORRENTNONDEFAULT, 
                                 ACTION_ADDTORRENTURL, 
                                 -1, 
                                 ACTION_RESUME, 
                                 ACTION_PAUSE, 
                                 ACTION_STOP, 
                                 ACTION_QUEUE, 
                                 ACTION_REMOVE, 
                                 -1, 
                                 ACTION_SCRAPE, 
                                 ACTION_DETAILS,
                                 -1,
                                 ACTION_MAKEFRIENDS,
                                 ACTION_BUDDIES,
                                 ACTION_FILES
                                 ], 
            'menu_listrightclick': [ACTION_RESUME, 
                                    ACTION_STOP, 
                                    ACTION_PAUSE, 
                                    ACTION_QUEUE, 
                                    ACTION_HASHCHECK, 
                                    -1, 
                                    ACTION_REMOVE, 
                                    ACTION_REMOVEFILE, 
                                    ACTION_EXPORTMENU, 
                                    ACTION_CLEARMESSAGE, 
                                    -1, 
                                    ACTION_LOCALUPLOAD, 
                                    ACTION_CHANGEPRIO, 
                                    -1, 
                                    ACTION_OPENFILEDEST, 
                                    ACTION_OPENDEST, 
                                    ACTION_CHANGEDEST, 
                                    -1, 
                                    ACTION_SCRAPE, 
                                    ACTION_DETAILS],
             'enablerecommender': '1',
             'enabledlhelp': '1',  
             'minport': '6881',
#            'skipcheck': '0'
        }

        configfilepath = os.path.join(self.getConfigPath(), "abc.conf")
        self.config = ConfigReader(configfilepath, "ABC", defaults)
#        self.config = ConfigReader(configfilepath, "ABC")
#        self.config.defaults = defaults
        
    def setupWebConfig(self):
        defaults = {
            'webID': 'yourkeyword', 
            'webIP': '127.0.0.1', 
            'webport': '56667', 
            'webautostart': '0', 
            'allow_query': '1', 
            'allow_delete': '1', 
            'allow_clearcompleted': '1', 
            'allow_add': '1', 
            'allow_setparam': '0', 
            'allow_getparam': '0', 
            'allow_queue': '1', 
            'allow_pause': '1', 
            'allow_stop': '1', 
            'allow_resume': '1', 
            'allow_setprio': '1', 
        }

        webconfigfilepath = os.path.join(self.getConfigPath(), "webservice.conf")
        self.webconfig = ConfigReader(webconfigfilepath, "ABC/Webservice", defaults)

    def setupTorrentMakerConfig(self):
        defaults = {
            'piece_size': '0', 
            'comment': '', 
            'created_by': '', 
            'announcedefault': '', 
            'announcehistory': '', 
            'announce-list': '', 
            'httpseeds': '', 
            'makehash_md5': '0', 
            'makehash_crc32': '0', 
            'makehash_sha1': '0', 
            'startnow': '0', 
            'savetorrent': '2',
            'createmerkletorrent': '0',
            'createtorrentsig': '0'
        }

        torrentmakerconfigfilepath = os.path.join(self.getConfigPath(), "maker.conf")
        self.makerconfig = ConfigReader(torrentmakerconfigfilepath, "ABC/TorrentMaker", defaults)
        
    def setupTorrentList(self):
        torrentfilepath = os.path.join(self.getConfigPath(), "torrent.list")
        self.torrentconfig = ConfigReader(torrentfilepath, "list0")
               
    # Initialization that has to be done after the wx.App object
    # has been created
    def postAppInit(self):
        try:
            self.icon = wx.Icon(os.path.join(self.getPath(), 'icon_abc.ico'), wx.BITMAP_TYPE_ICO)
        except:
            pass
            
        makeActionList(self)
            
    def getLastDir(self, operation = "save"):
        lastdir = self.lastdir[operation]
        
        if operation == "save":
            if not os.access(lastdir, os.F_OK):
                lastdir = self.config.Read('defaultfolder')
        
        if not os.access(lastdir, os.F_OK):
            lastdir = ""
            
        return lastdir

    def getPath(self):
        return self.abcpath

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
        minutestr = '%02d' % (minute) + self.lang.get('l_minute')
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
            if metainfo_file is not None:
                try:
                    metainfo_file.close()
                except:
                    pass
            metainfo = None
        return metainfo
        
    def speed_format(self, s, truncate = 1, stopearly = None):
        return self.size_format(s, truncate, stopearly) + "/" + self.lang.get('l_second')

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

    def makeBitmapButton(self, parent, bitmap, tooltip, event, trans_color = wx.Colour(200, 200, 200)):
        tooltiptext = self.lang.get(tooltip)
        
        button_bmp = self.makeBitmap(bitmap, trans_color)
        
        ID_BUTTON = wx.NewId()
        button_btn = wx.BitmapButton(parent, ID_BUTTON, button_bmp, size=wx.Size(button_bmp.GetWidth()+18, button_bmp.GetHeight()+4))
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
                      "auto_flush" ]
        for param in paramlist:
            value = self.config.Read(param)
            if value != "":
                btparams.append("--" + param)
                btparams.append(value)

        config, args = parseargs(btparams, BTDefaults)
            
        return config

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
    def makePopup(self, menu, event = None, label = "", extralabel = "", bindto = None):
        text = ""
        if label != "":
            text = self.lang.get(label)
        text += extralabel
        
        newid = wx.NewId()
        if event is not None:
            if bindto is None:
                bindto = menu
            bindto.Bind(wx.EVT_MENU, event, id = newid)
        menu.Append(newid, text)
        return newid