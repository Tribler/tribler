#
# Author : Choopan RATTANAPOKA, Jie Yang, Arno Bakker
#
# Description : Main ABC [Yet Another Bittorrent Client] python script.
#               you can run from source code by using
#               >python abc.py
#               need Python, WxPython in order to run from source code.
#
# see LICENSE.txt for license information
#########################################################################

import os,sys

# TODO: cleanup imports

# Arno, 2008-03-21: see what happens when we disable this locale thing. Gives
# errors on Vista in "Regional and Language Settings Options" different from 
# "English[United Kingdom]" 
#import locale
import signal
import commands
import pickle

try:
    import wxversion
    wxversion.select('2.8')
except:
    pass
import wx
from wx import xrc
#import hotshot

import subprocess
import atexit
import re
import urlparse

from threading import Thread, Event,currentThread,enumerate
import time
from traceback import print_exc, print_stack
from cStringIO import StringIO
import urllib

from Tribler.Main.Utility.utility import Utility
from Tribler.Main.Utility.constants import * #IGNORE:W0611
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.Dialogs.systray import ABCTaskBarIcon 
from Tribler.Main.notification import init as notification_init
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename
from Tribler.Main.vwxGUI.SRstatusbar import SRstatusbar
from Tribler.Video.defs import *
from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Video.utils import videoextdefaults

from Tribler.Category.Category import Category


from Tribler.Core.simpledefs import *
from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import show_permid

DEBUG = False


################################################################
#
# Class: FileDropTarget
#
# To enable drag and drop for ABC list in main menu
#
################################################################
class FileDropTarget(wx.FileDropTarget): 
    def __init__(self, frame):
        # Initialize the wsFileDropTarget Object 
        wx.FileDropTarget.__init__(self) 
        # Store the Object Reference for dropped files 
        self.frame = frame
      
    def OnDropFiles(self, x, y, filenames):
        for filename in filenames:
            try:
                self.FixTorrent(filename)
                self.frame.startDownload(filename)
            except IOError:
                dlg = wx.MessageDialog(None,
                           self.frame.utility.lang.get("filenotfound"),
                           self.frame.utility.lang.get("tribler_warning"),
                           wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
        return True

    def FixTorrent(self, filename):
        f = open(filename,"rb")
        bdata = f.read()
        f.close()
        
        #Check if correct bdata
        try:
            bdecode(bdata)
        except ValueError:
            #Try reading using sloppy
            try:
                bdata = bencode(bdecode(bdata, 1))
                #Overwrite with non-sloppy torrent
                f = open(filename,"wb")
                f.write(bdata)
                f.close()
            except:
                pass

# Custom class loaded by XRC
class MainFrame(wx.Frame):
    def __init__(self, *args):
        self.ready = False
        
        if len(args) == 0:
            pre = wx.PreFrame()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Frame.__init__(self, args[0], args[1], args[2], args[3])
            self._PostInit()
        self.wxapp = None
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.params = self.guiUtility.params
        self.utility.frame = self
        self.torrentfeed = None
        self.category = Category.getInstance()
        self.shutdown_and_upgrade_notes = None
        
        self.guiserver = GUITaskQueue.getInstance()
        title = self.utility.lang.get('title') + \
                " " + \
                self.utility.lang.get('version')
        
        # Get window size and position from config file
        size, position = self.getWindowSettings()
        style = wx.DEFAULT_FRAME_STYLE | wx.CLIP_CHILDREN
        
        self.SetSize(size)
        self.SetPosition(position)
        self.SetTitle(title)
        tt = self.GetToolTip()
        if tt is not None:
            tt.SetTip('')
            
        self.SRstatusbar = SRstatusbar(self)
        self.SetStatusBar(self.SRstatusbar)

        dragdroplist = FileDropTarget(self)
        self.SetDropTarget(dragdroplist)

        self.tbicon = None

        try:
            self.SetIcon(self.utility.icon)
        except:
            pass

        # Don't update GUI as often when iconized
        self.oldframe = None
        self.window = self.GetChildren()[0]
        self.window.utility = self.utility
        
        # Menu Events 
        ############################

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

        # leaving here for the time being:
        # wxMSW apparently sends the event to the App object rather than
        # the top-level Frame, but there seemed to be some possibility of
        # change
        self.Bind(wx.EVT_QUERY_END_SESSION, self.OnCloseWindow)
        self.Bind(wx.EVT_END_SESSION, self.OnCloseWindow)
        
        
        findId = wx.NewId()
        quitId = wx.NewId()
        homeId = wx.NewId()
        endId = wx.NewId()
        
        self.Bind(wx.EVT_MENU, self.OnFind, id = findId)
        self.Bind(wx.EVT_MENU, lambda event: self.Close(), id = quitId)
        self.Bind(wx.EVT_MENU, lambda event: self.guiUtility.OnList(False), id = homeId)
        self.Bind(wx.EVT_MENU, lambda event: self.guiUtility.OnList(True), id = endId)
        
        accelerators = [(wx.ACCEL_CTRL, ord('f'), findId)]
        accelerators.append((wx.ACCEL_NORMAL, wx.WXK_HOME, homeId))
        accelerators.append((wx.ACCEL_NORMAL, wx.WXK_END, endId))
        
        if sys.platform == 'linux2':
            accelerators.append((wx.ACCEL_CTRL, ord('q'), quitId))
            accelerators.append((wx.ACCEL_CTRL, ord('/'), findId))
        self.SetAcceleratorTable(wx.AcceleratorTable(accelerators))
        
        try:
            self.tbicon = ABCTaskBarIcon(self)
        except:
            print_exc()
        self.Bind(wx.EVT_ICONIZE, self.onIconify)
        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_MAXIMIZE, self.onSize)

        # Init video player
        sys.stdout.write('GUI Complete.\n')

        self.Show(True)
        self.ready = True
        
        # Just for debugging: add test permids and display top 5 peers from which the most is downloaded in bartercastdb
#        bartercastdb = self.utility.session.open_dbhandler(NTFY_BARTERCAST)
#        mypermid = bartercastdb.my_permid
#        
#        if DEBUG:
#            
#            top = bartercastdb.getTopNPeers(5)['top']
#    
#            print 'My Permid: ', show_permid(mypermid)
#            
#            print 'Top 5 BarterCast peers:'
#            print '======================='
#    
#            i = 1
#            for (permid, up, down) in top:
#                print '%2d: %15s  -  %10d up  %10d down' % (i, bartercastdb.getName(permid), up, down)
#                i += 1
        
        self.checkVersion()

        # If the user passed a torrentfile on the cmdline, load it.
        wx.CallAfter(self.startCMDLineTorrent)
        
    def startCMDLineTorrent(self):
        if self.params[0] != "":
            if self.params[0].startswith("magnet:"):
                self.startDownloadFromMagnet(self.params[0])
            else:
                torrentfilename = self.params[0]
                self.startDownload(torrentfilename,cmdline=True,vodmode=True)
                self.guiUtility.standardLibraryOverview(refresh=True)

    def startDownloadFromMagnet(self, url):
        def torrentdef_retrieved(tdef):
            print >> sys.stderr, "_" * 80
            print >> sys.stderr, "Retrieved metadata for:", tdef.get_name()
            self.startDownload(tdef=tdef, cmdline=True, vodmode=True)

        if not TorrentDef.retrieve_from_magnet(url, torrentdef_retrieved):
            print >> sys.stderr, "MainFrame.startDownloadFromMagnet() Can not use url to retrieve torrent"

    def startDownload(self,torrentfilename=None,destdir=None,tdef = None,cmdline=False,clicklog=None,name=None,vodmode=False):
        
        if DEBUG:
            print >>sys.stderr,"mainframe: startDownload:",torrentfilename,destdir,tdef
        try:
            if tdef is None:
                tdef = TorrentDef.load(torrentfilename)
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()
            if destdir is not None:
                dscfg.set_dest_dir(destdir)
        
            videofiles = tdef.get_files(exts=videoextdefaults)
            if vodmode and len(videofiles) == 0:
                vodmode = False

            if vodmode or tdef.get_live():
                print >>sys.stderr, 'MainFrame: startDownload: Starting in VOD mode'
                videoplayer = VideoPlayer.getInstance()
                result = videoplayer.start_and_play(tdef,dscfg)

                # 02/03/09 boudewijn: feedback to the user when there
                # are no playable files in the torrent
                if not result:
                    dlg = wx.MessageDialog(None,
                               self.utility.lang.get("invalid_torrent_no_playable_files_msg"),
                               self.utility.lang.get("invalid_torrent_no_playable_files_title"),
                               wx.OK|wx.ICON_ERROR)
                    dlg.ShowModal()
                    dlg.Destroy()
            else:
                print >>sys.stderr, 'MainFrame: startDownload: Starting in DL mode'
                result = self.utility.session.start_download(tdef,dscfg)
            
            if result:
                self.show_saved()
            
            # store result because we want to store clicklog data
            # right after download was started, then return result
            if clicklog is not None:
                mypref = self.utility.session.open_dbhandler(NTFY_MYPREFERENCES)
                mypref.addClicklogToMyPreference(tdef.get_infohash(), clicklog)

            return result  

        except DuplicateDownloadException:
            # show nice warning dialog
            dlg = wx.MessageDialog(None,
                                   self.utility.lang.get('duplicate_download_msg'),
                                   self.utility.lang.get('duplicate_download_title'),
                                   wx.OK|wx.ICON_ERROR)
            result = dlg.ShowModal()
            dlg.Destroy()
            
            # If there is something on the cmdline, all other torrents start
            # in STOPPED state. Restart
            if cmdline:
                dlist = self.utility.session.get_downloads()
                for d in dlist:
                    if d.get_def().get_infohash() == tdef.get_infohash():
                        d.restart()
                        break
        except Exception,e:
            print_exc()
            self.onWarning(e)
        return None


    def show_saved(self):
        self.guiUtility.frame.top_bg.Notify("Download started", wx.ART_INFORMATION)
       
    def checkVersion(self):
        guiserver = GUITaskQueue.getInstance()
        guiserver.add_task(self._checkVersion, 5.0)

    def _checkVersion(self):
        # Called by GUITaskQueue thread
        my_version = self.utility.getVersion()
        try:
            curr_status = urllib.urlopen('http://tribler.org/version').readlines()
            line1 = curr_status[0]
            if len(curr_status) > 1:
                self.update_url = curr_status[1].strip()
            else:
                self.update_url = 'http://tribler.org'

            info = {}
            if len(curr_status) > 2:
                # the version file contains additional information in
                # "KEY:VALUE\n" format
                pattern = re.compile("^\s*(?<!#)\s*([^:\s]+)\s*:\s*(.+?)\s*$")
                for line in curr_status[2:]:
                    match = pattern.match(line)
                    if match:
                        key, value = match.group(1, 2)
                        if key in info:
                            info[key] += "\n" + value
                        else:
                            info[key] = value

            _curr_status = line1.split()
            self.curr_version = _curr_status[0]
            if self.newversion(self.curr_version, my_version):
                # Arno: we are a separate thread, delegate GUI updates to MainThread
                self.upgradeCallback()

                # Boudewijn: start some background downloads to
                # upgrade on this seperate thread
                ##self._upgradeVersion(my_version, self.curr_version, info)
            
            # Also check new version of web2definitions for youtube etc. search
            ##Web2Updater(self.utility).checkUpdate()
        except Exception,e:
            print >> sys.stderr, "Tribler: Version check failed", time.ctime(time.time()), str(e)
            #print_exc()

    def _upgradeVersion(self, my_version, latest_version, info):
        # check if there is a .torrent for our OS
        torrent_key = "torrent-%s" % sys.platform
        notes_key = "notes-txt-%s" % sys.platform
        if torrent_key in info:
            print >> sys.stderr, "-- Upgrade", my_version, "->", latest_version
            notes = []
            if "notes-txt" in info:
                notes.append(info["notes-txt"])
            if notes_key in info:
                notes.append(info[notes_key])
            notes = "\n".join(notes)
            if notes:
                for line in notes.split("\n"):
                    print >> sys.stderr, "-- Notes:", line
            else:
                notes = "No release notes found"
            print >> sys.stderr, "-- Downloading", info[torrent_key], "for upgrade"

            # prepare directort and .torrent file
            location = os.path.join(self.utility.session.get_state_dir(), "upgrade")
            if not os.path.exists(location):
                os.mkdir(location)
            print >> sys.stderr, "-- Dir:", location
            filename = os.path.join(location, os.path.basename(urlparse.urlparse(info[torrent_key])[2]))
            print >> sys.stderr, "-- File:", filename
            if not os.path.exists(filename):
                urllib.urlretrieve(info[torrent_key], filename)

            # torrent def
            tdef = TorrentDef.load(filename)
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()

            # figure out what file to start once download is complete
            files = tdef.get_files_as_unicode()
            executable = None
            for file_ in files:
                if sys.platform == "win32" and file_.endswith(u".exe"):
                    print >> sys.stderr, "-- exe:", file_
                    executable = file_
                    break

                elif sys.platform == "linux2" and file_.endswith(u".deb"):
                    print >> sys.stderr, "-- deb:", file_
                    executable = file_
                    break

                elif sys.platform == "darwin" and file_.endswith(u".dmg"):
                    print >> sys.stderr, "-- dmg:", file_
                    executable = file_
                    break

            if not executable:
                print >> sys.stderr, "-- Abort upgrade: no file found"
                return
                
            # start download
            try:
                download = self.utility.session.start_download(tdef)

            except DuplicateDownloadException:
                print >> sys.stderr, "-- Duplicate download"
                download = None
                for random_download in self.utility.session.get_downloads():
                    if random_download.get_def().get_infohash() == tdef.get_infohash():
                        download = random_download
                        break

            # continue until download is finished
            if download:
                def start_upgrade():
                    """
                    Called by python when everything is shutdown.  We
                    can now start the downloaded file that will
                    upgrade tribler.
                    """
                    executable_path = os.path.join(download.get_dest_dir(), executable)

                    if sys.platform == "win32":
                        args = [executable_path]

                    elif sys.platform == "linux2":
                        args = ["gdebi-gtk", executable_path]

                    elif sys.platform == "darwin":
                        args = ["open", executable_path]
                    
                    print >> sys.stderr, "-- Tribler closed, starting upgrade"
                    print >> sys.stderr, "-- Start:", args
                    subprocess.Popen(args)

                def wxthread_upgrade():
                    """
                    Called on the wx thread when the .torrent file is
                    downloaded.  Will ask the user if Tribler can be
                    shutdown for the upgrade now.
                    """
                    if self.Close():
                        atexit.register(start_upgrade)
                    else:
                        self.shutdown_and_upgrade_notes = None

                def state_callback(state):
                    """
                    Called every n seconds with an update on the
                    .torrent download that we need to upgrade
                    """
                    if DEBUG: print >> sys.stderr, "-- State:", dlstatus_strings[state.get_status()], state.get_progress()
                    # todo: does DLSTATUS_STOPPED mean it has completely downloaded?
                    if state.get_status() == DLSTATUS_SEEDING:
                        self.shutdown_and_upgrade_notes = notes
                        wx.CallAfter(wxthread_upgrade)
                        return (0.0, False)
                    return (1.0, False)

                download.set_state_callback(state_callback)
            
    def newversion(self, curr_version, my_version):
        curr = curr_version.split('.')
        my = my_version.split('.')
        if len(my) >= len(curr):
            nversion = len(my)
        else:
            nversion = len(curr)
        for i in range(nversion):
            if i < len(my):
                my_v = int(my[i])
            else:
                my_v = 0
            if i < len(curr):
                curr_v = int(curr[i])
            else:
                curr_v = 0
            if curr_v > my_v:
                return True
            elif curr_v < my_v:
                return False
        return False

    def upgradeCallback(self):
        wx.CallAfter(self.OnUpgrade)    
        # TODO: warn multiple times?
    
    def OnUpgrade(self, event=None):
        self.setActivity(NTFY_ACT_NEW_VERSION)
        guiserver = GUITaskQueue.getInstance()
        guiserver.add_task(self.upgradeCallback,10.0)

    #Force restart of Tribler
    def Restart(self):
        path = os.getcwd()
        if sys.platform == "win32":
            executable = "tribler.exe"
        elif sys.platform == "linux2":
            executable = "tribler.sh"
        elif sys.platform == "darwin":
            executable = "?"
        
        executable = os.path.join(path, executable)
        print >> sys.stderr, executable
        def start_tribler():
            subprocess.Popen(executable)

        atexit.register(start_tribler)
        self.guiUtility.frame.OnCloseWindow()
    
    def OnFind(self, event):
        self.guiUtility.frame.top_bg.SearchFocus()


    #######################################
    # minimize to tray bar control
    #######################################
    def onTaskBarActivate(self, event = None):
        self.Iconize(False)
        self.Show(True)
        self.Raise()
        
        if self.tbicon is not None:
            self.tbicon.updateIcon(False)

    def onIconify(self, event = None):
        # This event handler is called both when being minimalized
        # and when being restored.
        # Arno, 2010-01-15: on Win7 with wxPython2.8-win32-unicode-2.8.10.1-py26
        # there is no event on restore :-(
        if DEBUG:
            if event is not None:
                print  >> sys.stderr,"main: onIconify(",event.Iconized()
            else:
                print  >> sys.stderr,"main: onIconify event None"
        if event.Iconized():                                                                                                               
            videoplayer = VideoPlayer.getInstance()
            videoplayer.videoframe.get_videopanel().Pause() # when minimzed pause playback

            if (self.utility.config.Read('mintray', "int") > 0
                and self.tbicon is not None):
                self.tbicon.updateIcon(True)
                self.Show(False)
        else:
            videoplayer = VideoPlayer.getInstance()
            embed = videoplayer.videoframe.get_videopanel()
            if embed.GetState() == MEDIASTATE_PAUSED:
                embed.ppbtn.setToggled(False)
                embed.vlcwin.setloadingtext('')
                embed.vlcwrap.resume()
        if event is not None:
            event.Skip()

    def onSize(self, event = None):
        # Arno: On Windows when I enable the tray icon and then change
        # virtual desktop (see MS DeskmanPowerToySetup.exe)
        # I get a onIconify(event.Iconized()==True) event, but when
        # I switch back, I don't get an event. As a result the GUIupdate
        # remains turned off. The wxWidgets wiki on the TaskBarIcon suggests
        # catching the onSize event. 
        if DEBUG:
            if event is not None:
                print  >> sys.stderr,"main: onSize:",self.GetSize()
            else:
                print  >> sys.stderr,"main: onSize: None"
        if event is not None:
            if event.GetEventType() == wx.EVT_MAXIMIZE:
                self.window.SetClientSize(self.GetClientSize())
            event.Skip()
        
    def getWindowSettings(self):
        width = self.utility.config.Read("window_width")
        height = self.utility.config.Read("window_height")
        #try:
            #size = wx.Size(int(width), int(height))
        #except:
        size = wx.Size(1024, 670)
        
        x = self.utility.config.Read("window_x")
        y = self.utility.config.Read("window_y")
        if (x == "" or y == "" or x == 0 or y == 0):
            #position = wx.DefaultPosition

            # On Mac, the default position will be underneath the menu bar, so lookup (top,left) of
            # the primary display
            primarydisplay = wx.Display(0)
            dsize = primarydisplay.GetClientArea()
            position = dsize.GetTopLeft()

            # Decrease size to fit on screen, if needed
            width = min( size.GetWidth(), dsize.GetWidth() )
            height = min( size.GetHeight(), dsize.GetHeight() )
            size = wx.Size( width, height )
        else:
            position = wx.Point(int(x), int(y))

        return size, position     
        
    def saveWindowSettings(self):
        width, height = self.GetSizeTuple()
        x, y = self.GetPositionTuple()
        self.utility.config.Write("window_width", width)
        self.utility.config.Write("window_height", height)
        self.utility.config.Write("window_x", x)
        self.utility.config.Write("window_y", y)

        self.utility.config.Flush()
       
    ##################################
    # Close Program
    ##################################
               
    def OnCloseWindow(self, event = None):
        found = False
        if event != None:
            nr = event.GetEventType()
            lookup = { wx.EVT_CLOSE.evtType[0]: "EVT_CLOSE", wx.EVT_QUERY_END_SESSION.evtType[0]: "EVT_QUERY_END_SESSION", wx.EVT_END_SESSION.evtType[0]: "EVT_END_SESSION" }
            if nr in lookup: 
                nr = lookup[nr]
                found = True
                
            print "mainframe: Closing due to event ",nr,`event`
            print >>sys.stderr,"mainframe: Closing due to event ",nr,`event`
        else:
            print "mainframe: Closing untriggered by event"
        
        
        # Don't do anything if the event gets called twice for some reason
        if self.utility.abcquitting:
            return

        # Check to see if we can veto the shutdown
        # (might not be able to in case of shutting down windows)
        if event is not None:
            try:
                if isinstance(event,wx.CloseEvent) and event.CanVeto() and self.utility.config.Read('confirmonclose', "boolean") and not event.GetEventType() == wx.EVT_QUERY_END_SESSION.evtType[0]:
                    if self.shutdown_and_upgrade_notes:
                        confirmmsg = self.utility.lang.get('confirmupgrademsg') + "\n\n" + self.shutdown_and_upgrade_notes
                        confirmtitle = self.utility.lang.get('confirmupgrade')
                    else:
                        confirmmsg = self.utility.lang.get('confirmmsg')
                        confirmtitle = self.utility.lang.get('confirm')

                    dialog = wx.MessageDialog(None, confirmmsg, confirmtitle, wx.OK|wx.CANCEL)
                    result = dialog.ShowModal()
                    dialog.Destroy()
                    if result != wx.ID_OK:
                        event.Veto()
                        return
            except:
                print_exc()
            
        self.utility.abcquitting = True
        
        videoplayer = VideoPlayer.getInstance()
        videoplayer.stop_playback()
        
        self.guiUtility.guiOpen.clear()

        try:
            # Restore the window before saving size and position
            # (Otherwise we'll get the size of the taskbar button and a negative position)
            self.onTaskBarActivate()
            self.saveWindowSettings()
        except:
            print_exc()

        try:
            if self.videoframe is not None:
                self.videoframe.Destroy()
        except:
            print_exc()
        
        try:
            if self.tbicon is not None:
                self.tbicon.RemoveIcon()
                self.tbicon.Destroy()
            self.Destroy()
        except:
            print_exc()

        if DEBUG:    
            print >>sys.stderr,"mainframe: OnCloseWindow END"

        if DEBUG:
            ts = enumerate()
            for t in ts:
                print >>sys.stderr,"mainframe: Thread still running",t.getName(),"daemon",t.isDaemon()

        if not found or sys.platform =="darwin":
            # On Linux with wx 2.8.7.1 this method gets sometimes called with
            # a CommandEvent instead of EVT_CLOSE, wx.EVT_QUERY_END_SESSION or
            # wx.EVT_END_SESSION
            self.quit()
        
    def onWarning(self,exc):
        msg = self.utility.lang.get('tribler_startup_nonfatalerror')
        msg += str(exc.__class__)+':'+str(exc)
        dlg = wx.MessageDialog(None, msg, self.utility.lang.get('tribler_warning'), wx.OK|wx.ICON_WARNING)
        result = dlg.ShowModal()
        dlg.Destroy()

    def onUPnPError(self,upnp_type,listenport,error_type,exc=None,listenproto='TCP'):

        if error_type == 0:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' ')+self.utility.lang.get('tribler_upnp_error1')
        elif error_type == 1:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' ')+self.utility.lang.get('tribler_upnp_error2')+unicode(str(exc))+self.utility.lang.get('tribler_upnp_error2_postfix')
        elif error_type == 2:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' ')+self.utility.lang.get('tribler_upnp_error3')
        else:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' Unknown error')

        msg = self.utility.lang.get('tribler_upnp_error_intro')
        msg += listenproto+' '
        msg += str(listenport)
        msg += self.utility.lang.get('tribler_upnp_error_intro_postfix')
        msg += errormsg
        msg += self.utility.lang.get('tribler_upnp_error_extro') 

        dlg = wx.MessageDialog(None, msg, self.utility.lang.get('tribler_warning'), wx.OK|wx.ICON_WARNING)
        result = dlg.ShowModal()
        dlg.Destroy()



    def setActivity(self,type,msg=u'',arg2=None):
        
        #print >>sys.stderr,"MainFrame: setActivity: t",type,"m",msg,"a2",arg2
        
        if self.utility is None:
            if DEBUG:
                print >>sys.stderr,"MainFrame: setActivity: Cannot display: t",type,"m",msg,"a2",arg2
            return
            
        if currentThread().getName() != "MainThread":
            if DEBUG:
                print  >> sys.stderr,"main: setActivity thread",currentThread().getName(),"is NOT MAIN THREAD"
                print_stack()
    
        if type == NTFY_ACT_NONE:
            prefix = msg
            msg = u''
        elif type == NTFY_ACT_ACTIVE:
            prefix = u""
            if msg == "no network":
                text = "No network - last activity: %.1f seconds ago" % arg2
                self.SetTitle(text)
                print  >> sys.stderr,"main: Activity",`text`
            elif self.GetTitle().startswith("No network"):
                title = self.utility.lang.get('title') + \
                        " " + \
                        self.utility.lang.get('version')
                self.SetTitle(title)
                
                
        elif type == NTFY_ACT_UPNP:
            prefix = self.utility.lang.get('act_upnp')
        elif type == NTFY_ACT_REACHABLE:
            prefix = self.utility.lang.get('act_reachable')
        elif type == NTFY_ACT_GET_EXT_IP_FROM_PEERS:
            prefix = self.utility.lang.get('act_get_ext_ip_from_peers')
        elif type == NTFY_ACT_MEET:
            prefix = self.utility.lang.get('act_meet')
        elif type == NTFY_ACT_GOT_METADATA:
            prefix = self.utility.lang.get('act_got_metadata')
            
            if self.category.family_filter_enabled() and arg2 == 7: # XXX category
                if DEBUG:
                    print >>sys.stderr,"MainFrame: setActivity: Hiding XXX torrent",msg
                return
            
        elif type == NTFY_ACT_RECOMMEND:
            prefix = self.utility.lang.get('act_recommend')
        elif type == NTFY_ACT_DISK_FULL:
            prefix = self.utility.lang.get('act_disk_full')   
        elif type == NTFY_ACT_NEW_VERSION:
            prefix = self.utility.lang.get('act_new_version')   
        if msg == u'':
            text = prefix
        else:
            text = unicode( prefix+u' '+msg)
            
        if DEBUG:
            print  >> sys.stderr,"main: Activity",`text`
        #self.messageField.SetLabel(text)

    def set_player_status(self,s):
        """ Called by VideoServer when using an external player """
        if self.videoframe is not None:
            self.videoframe.set_player_status(s)

    def set_wxapp(self,wxapp):
        self.wxapp = wxapp
        
    def quit(self):
        if self.wxapp is not None:
            self.wxapp.ExitMainLoop()

     
     
