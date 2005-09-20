import wx
import sys
import os
import socket

from shutil import copyfile, move
from lang.lang import Lang
from string import join as stjoin, find
from threading import Event, Thread, Semaphore
from time import time, sleep
from traceback import print_exc
from cStringIO import StringIO
from urlparse import urlsplit, urlunsplit

from wx.lib import masked

from BitTornado.zurllib import urlopen, quote, unquote
from BitTornado.bencode import *

if (sys.platform == 'win32'):
    from Utility.regchecker import RegChecker
from Utility.guimanager import GUIManager
from Utility.configreader import ConfigReader

def getClientSocket(host, port):
    s = None
    
    for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        try:
            s = socket.socket(af, socktype, proto)
        except socket.error:
            s = None
            continue

        try:
            s.connect(sa)
        except socket.error:
            s.close()
            s = None
            continue
        break
        
    return s
    
def getServerSocket(host, port):
    s = None

    for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
        af, socktype, proto, canonname, sa = res
        try:
            s = socket.socket(af, socktype, proto)
        except socket.error:
            s = None
            continue
        try:
            s.bind(sa)
            s.listen(1)
        except socket.error:
            s.close()
            s = None
            continue
        break

    return s

def getSocket(host, port, sockettype = "client", attempt = 5):
    s = None

    tries = 0

    while s is None and tries < attempt:
        if sockettype == "server":
            s = getServerSocket(host, port)
        else:
            s = getClientSocket(host, port)
            
        if s is None:
            # Try several times, increase in time each try
            sleep(0.01 * tries)
            tries += 1
            
    return s

class Utility:
    def __init__(self, app, abcpath):
        self.abcpath = abcpath
        self.app = app

        self.setupConfig()
        self.setupWebConfig()
        self.setupTorrentList()
                            
        self.lang = Lang(self)

        GUIManager(self)
        
        self.FILESEM   = Semaphore(1)

        if (sys.platform == 'win32'):        
            self.regchecker = RegChecker(self)

        self.lastdir = { "save" : self.config.Read('defaultfolder'), 
                         "open" : "",
                         "log": "" }

        # Is ABC in the process of shutting down?
        self.abcquitting = False
        self.abcdonequitting = False
        
        # Keep track of the last tab that was being viewed
        self.lasttab = { "advanced" : 0, 
                         "preferences" : 0 }
                         
        self.languages = {}
                         
    def setupConfig(self):
        defaults = {
            'minport': '10000', 
            'maxport': '60000', 
            'maxupload': '5', 
            'maxuploadrate': '0', 
            'maxdownloadrate': '0', 
            'maxseeduploadrate': '0', 
            'numsimdownload': '2', 
            'uploadoption': '2', 
            'uploadtimeh': '0', 
            'uploadtimem': '30', 
            'uploadratio': '100', 
            'removetorrent': '1', 
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
            'urmmaxtorrent': '5', 
            'urmupthreshold': '2', 
            'urmlowpriority': '0', 
            'urmdelay': '60', 
#            'dynmaxuprate': '0',
            'upfromdownA': '0.1', 
            'upfromdownB': '3.0', 
            'upfromdownC': '0.12', 
            'upfromdownD': '10.0', 
#            'urmstartdelay': '180',
#            'urmtorrentstartdelay': '60',
            'stripedlist': '1', 
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
            'column5_width': '160', 
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
            'column12_width': '150', 
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
            'forcenewdir': '1', 
            'upnp_nat_access': '0', 
            'buffer_write' : '4', 
            'buffer_read' : '1', 
            'auto_flush' : '0', 
            'associate' : '1', 
            'movecompleted': '0'
        }

        configfilepath = os.path.join(self.abcpath, "abc.conf")
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

        webconfigfilepath = os.path.join(self.abcpath, "webservice.conf")
        self.webconfig = ConfigReader(webconfigfilepath, "ABC/Webservice", defaults)
#        self.webconfig = ConfigReader(webconfigfilepath, "ABC/Webservice")
#        self.webconfig.defaults = defaults
        
    def setupTorrentList(self):        
        torrentfilepath = os.path.join(self.abcpath, "torrent.list")
        self.torrentconfig = ConfigReader(torrentfilepath, "dummygroup")
        
    # Initialization that has to be done after the wx.App object
    # has been created
    def postAppInit(self):
        try:
            self.icon = wx.Icon(os.path.join(self.getPath(), 'icon_abc.ico'), wx.BITMAP_TYPE_ICO)
        except:
            pass
            
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
        if n == 0:
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
                text += ":" + hourstr
        elif day > 0:
            text = daystr
            if truncate > 1:
                text += ":" + hourstr
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
            
    def getMetainfo(self, src, openoptions = 'rb', url = False):
        if src is None:
            return None
        
        metainfo = None
        try:
            metainfo_file = None
            # We're getting a url
            if (url):
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
                              
    def AddTorrentURL(self, url, caller=""):
        self.utility = self
        # Strip any leading/trailing spaces from the URL
        url = url.strip()
        
        # Check to see if the url starts with http
        #########################################
        if not url.startswith("http://"):
            if caller != "web":
                dialog = wx.MessageDialog(None, self.utility.lang.get('startwithhttp'), 
                                          self.utility.lang.get('error'), wx.ICON_ERROR)
                dialog.ShowModal()
                dialog.Destroy()
                return
            else:
                return "Error=Torrent doesn't start with http"
        
        # Copy file from web and call addnewproc
        #########################################
        try:
            url_splitted=urlsplit(url)
            h = urlopen(urlunsplit([url_splitted[0], url_splitted[1], quote(unquote(url_splitted[2])), url_splitted[3], url_splitted[4]]))
            
            btmetafile = h.read()
            h.close()
        except :
            if caller != "web":
                #display error can't connect to server
                dialog = wx.MessageDialog(None, self.utility.lang.get('cantgettorrentfromurl') + ":\n" + url, 
                                      self.utility.lang.get('error'), wx.ICON_ERROR)
                dialog.ShowModal()
                dialog.Destroy()
                return
            return "Error=Can't get torrent from URL"

        # Backup metainfo from URL to local directory
        filename = os.path.split(stjoin([unquote(url_splitted[2]), url_splitted[3]], ''))[1]
        # If the filename is blank, then don't continue
        if filename == "":
            if caller != "web":
                dialog = wx.MessageDialog(None, self.utility.lang.get('failedinvalidtorrent') + ":\n" + url, 
                                      self.utility.lang.get('error'), wx.ICON_ERROR)
                dialog.ShowModal()
                dialog.Destroy()
                return
            else:
                return "Error=Invalid torrent file"
            
        torrentsrc = os.path.join(self.utility.getPath(), "torrent", filename)
#        dotTorrentDuplicate = False

        fileexists = os.access(torrentsrc, os.R_OK)

        if not fileexists:
            # Make torrent directory if necessary
            self.MakeTorrentDir()

            f = open(torrentsrc, "wb")
            f.write(btmetafile)
            f.close()
        
        # Torrent either already existed or should exist now
        dotTorrentDuplicate = True
        
        return self.AddTorrentFromFile(torrentsrc, False, dotTorrentDuplicate, caller = caller)
    
    def AddTorrentLink(self, event):
        self.utility = self
        dialog = wx.TextEntryDialog(None, 
                                    self.utility.lang.get('enterurl'), 
                                    self.utility.lang.get('addtorrenturl_short'))

        result = dialog.ShowModal()
        btlink = dialog.GetValue()
        dialog.Destroy()
        
        if result != wx.ID_OK:
            return
        
        if btlink != "":
            self.AddTorrentURL(btlink)

    def AddTorrentNoneDefault(self, event):
        self.AddTorrentFile(event, True)
            
    def AddTorrentFile(self, event, forceasklocation = False):
        self.utility = self
        dialog = wx.FileDialog(None, self.utility.lang.get('choosetorrentfile'), self.getLastDir("open"), '', '*.torrent', wx.OPEN|wx.MULTIPLE)
        result = dialog.ShowModal()
        dialog.Destroy()
        if result != wx.ID_OK:
            return
        
        filelocation = dialog.GetPaths()

        for filepath in filelocation:
            self.AddTorrentFromFile(filepath, forceasklocation)
            
    def AddTorrentFromFile(self, filepath, forceasklocation = False, dotTorrentDuplicate = False, caller = ""):
        self.utility = self
        # Check to make sure that the source file exists
        sourcefileexists = os.access(filepath, os.R_OK)
        
        if not sourcefileexists:
            if caller != "web":
                dlg = wx.MessageDialog(None, filepath + '\n' +
                                                    self.utility.lang.get('failedtorrentmissing'), self.utility.lang.get('error'), wx.OK|wx.ICON_ERROR)
                result = dlg.ShowModal()
                dlg.Destroy()
            # What do we do if the source file doesn't exist?
            # Just return if the source file doesn't exist?
            return "Error=The source file for this torrent doesn't exist"

        # Make torrent directory if necessary
        self.MakeTorrentDir()
      
        torrentpath = os.path.join(self.utility.getPath(), "torrent")    
        filename     = os.path.split(filepath)[1]
        torrentsrc   = os.path.join(torrentpath, filename)
        dontremove = False

        fileexists = os.access(torrentsrc, os.R_OK)
        if fileexists and not dotTorrentDuplicate:
            if caller != "web":
                # ignore if the src and dest files are the same
                # this means that files in the torrent directory
                # will only give a duplicate torrent error if
                # they are already loaded in the list
                # (dotTorrentDuplicate stays False and the check to
                #  see if it's in the list is performed in addNewProc)
                ##############################################
                if (filepath == torrentsrc):
                    # If addNewProc finds that the torrent is already in the proctab,
                    # we don't want to remove it otherwise the torrent that is running
                    # will be in trouble
                    dontremove = True
                else:
                    # There is a duplicate .torrent file in /torrent
                    dialog = wx.MessageDialog(None, self.utility.lang.get('duplicatetorrentmsg') , self.utility.lang.get('duplicatetorrent'), wx.YES_NO|wx.ICON_EXCLAMATION)
                    result = dialog.ShowModal()
                    dialog.Destroy()
                    if(result == wx.ID_NO):
                        return "Error=This torrent is duplicate"
                    else:
                        dotTorrentDuplicate = True
            else:
                return "Error=This torrent is duplicate"
        else:
            # Either:
            # dotTorrentDuplicate was False and the file didn't exist (no change)
            # dotTorrentDuplicate was True before when coming from AddTorrentURL (still need to check the list)
            dotTorrentDuplicate = False

        # No need to copy if we're just copying the file onto itself
        if (filepath != torrentsrc):
            copyfile(filepath, torrentsrc)
        success, mesg, ABCTorrent = self.utility.queue.addNewProc(torrentsrc, 
                                                                  forceasklocation = forceasklocation, 
                                                                  dotTorrentDuplicate = dotTorrentDuplicate, 
                                                                  dontremove = dontremove, 
                                                                  caller = caller)
        if success:
            return "OK"
        else:
            return "Error="+mesg
            
    def MakeTorrentDir(self):
        torrentpath = os.path.join(self.utility.getPath(), "torrent")
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
                        if len(os.listdir(dirname)) == 0:
                            os.rmdir(dirname)
        #remove folder
        if os.access(basedir, os.F_OK):
            if len(os.listdir(basedir)) == 0:
                os.rmdir(basedir)
        
    def makeBitmap(self, bitmap, trans_color = wx.Colour(200, 200, 200)):
        button_bmp = wx.Bitmap(os.path.join(self.getPath(), 'icons', bitmap), wx.BITMAP_TYPE_BMP)
        button_mask = wx.Mask(button_bmp, trans_color)
        button_bmp.SetMask(button_mask)
        return button_bmp