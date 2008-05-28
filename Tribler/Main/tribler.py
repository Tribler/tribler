#!/usr/bin/python

#########################################################################
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

# Arno: M2Crypto overrides the method for https:// in the
# standard Python libraries. This causes msnlib to fail and makes Tribler
# freakout when "http://www.tribler.org/version" is redirected to
# "https://www.tribler.org/version/" (which happened during our website
# changeover) Until M2Crypto 0.16 is patched I'll restore the method to the
# original, as follows.
#
# This must be done in the first python file that is started.
#


import os,sys
import urllib
original_open_https = urllib.URLopener.open_https
import M2Crypto
urllib.URLopener.open_https = original_open_https

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

from threading import Thread, Event,currentThread,enumerate
from time import time, ctime, sleep
from traceback import print_exc, print_stack
from cStringIO import StringIO
import urllib
import webbrowser

if (sys.platform == 'win32'):
        from Tribler.Main.Dialogs.regdialog import RegCheckDialog

from Tribler.Main.Utility.utility import Utility
from Tribler.Main.Utility.constants import * #IGNORE:W0611
import Tribler.Main.vwxGUI.font as font
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
import Tribler.Main.vwxGUI.updateXRC as updateXRC
from Tribler.Main.vwxGUI.TasteHeart import set_tasteheart_bitmaps
from Tribler.Main.vwxGUI.perfBar import set_perfBar_bitmaps
from Tribler.Main.vwxGUI.MainMenuBar import MainMenuBar
from Tribler.Main.vwxGUI.font import *
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.Dialogs.systray import ABCTaskBarIcon 
from Tribler.Main.notification import init as notification_init
from Tribler.Category.Category import Category
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.Video.VideoPlayer import VideoPlayer,return_feasible_playback_modes,PLAYBACKMODE_INTERNAL
from Tribler.Video.VideoServer import VideoHTTPServer
from Tribler.Web2.util.update import Web2Updater
from Tribler.Policies.RateManager import UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager
from Tribler.Utilities.Instance2Instance import *
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename

from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import show_permid

I2I_LISTENPORT = 57891
VIDEOHTTP_LISTENPORT = 6878

DEBUG = False
ALLOW_MULTIPLE = False


################################################################
#
# Class: FileDropTarget
#
# To enable drag and drop for ABC list in main menu
#
################################################################
class FileDropTarget(wx.FileDropTarget): 
    def __init__(self, abcframe):
        # Initialize the wsFileDropTarget Object 
        wx.FileDropTarget.__init__(self) 
        # Store the Object Reference for dropped files 
        self.abcframe = abcframe
      
    def OnDropFiles(self, x, y, filenames):
        for filename in filenames:
            self.abcframe.startDownload(filename)
        return True



# Custom class loaded by XRC
class ABCFrame(wx.Frame):
    def __init__(self, *args):
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
        
        #wx.Frame.__init__(self, None, ID, title, position, size, style = style)
        
        self.doneflag = Event()

        dragdroplist = FileDropTarget(self)
        self.SetDropTarget(dragdroplist)

        self.tbicon = None

        # Arno: see ABCPanel
        #self.abc_sb = ABCStatusBar(self,self.utility)
        #self.SetStatusBar(self.abc_sb)

        """
        # Add status bar
        statbarbox = wx.BoxSizer(wx.HORIZONTAL)
        self.sb_buttons = ABCStatusButtons(self,self.utility)
        statbarbox.Add(self.sb_buttons, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
        self.abc_sb = ABCStatusBar(self,self.utility)
        statbarbox.Add(self.abc_sb, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
        #colSizer.Add(statbarbox, 0, wx.ALL|wx.EXPAND, 0)
        self.SetStatusBar(statbarbox)
        """
        
        
        try:
            self.SetIcon(self.utility.icon)
        except:
            pass

        # Don't update GUI as often when iconized
        self.GUIupdate = True

        # Start the scheduler before creating the ListCtrl
        #self.utility.queue  = ABCScheduler(self.utility)
        #self.window = ABCPanel(self)
        #self.abc_sb = self.window.abc_sb
        
        
        self.oldframe = None
        #self.oldframe = ABCOldFrame(-1, self.params, self.utility)
        #self.oldframe.Refresh()
        #self.oldframe.Layout()
        #self.oldframe.Show(True)
        
        self.window = self.GetChildren()[0]
        self.window.utility = self.utility
        
        """
        self.list = ABCList(self.window)
        self.list.Show(False)
        self.utility.list = self.list
        print self.window.GetName()
        self.window.list = self.list
        self.utility.window = self.window
        """
        #self.window.sb_buttons = ABCStatusButtons(self,self.utility)
        
        #self.utility.window.postponedevents = []
        
        # Menu Options
        ############################
        #menuBar = ABCMenuBar(self)
        #if sys.platform == "darwin":
        #    wx.App.SetMacExitMenuItemId(wx.ID_CLOSE)
        #self.SetMenuBar(menuBar)
        
        #self.tb = ABCToolBar(self) # new Tribler gui has no toolbar
        #self.SetToolBar(self.tb)
        
        self.buddyFrame = None
        self.fileFrame = None
        self.buddyFrame_page = 0
        self.buddyFrame_size = (800, 500)
        self.buddyFrame_pos = None
        self.fileFrame_size = (800, 500)
        self.fileFrame_pos = None
        
        # Menu Events 
        ############################

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
#        self.Bind(wx.EVT_MENU, self.OnMenuExit, id = wx.ID_CLOSE)

        # leaving here for the time being:
        # wxMSW apparently sends the event to the App object rather than
        # the top-level Frame, but there seemed to be some possibility of
        # change
        self.Bind(wx.EVT_QUERY_END_SESSION, self.OnCloseWindow)
        self.Bind(wx.EVT_END_SESSION, self.OnCloseWindow)
        
        try:
            self.tbicon = ABCTaskBarIcon(self)
        except:
            print_exc()
        self.Bind(wx.EVT_ICONIZE, self.onIconify)
        self.Bind(wx.EVT_SET_FOCUS, self.onFocus)
        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_MAXIMIZE, self.onSize)
        #self.Bind(wx.EVT_IDLE, self.onIdle)


        

        # If the user passed a torrentfile on the cmdline, load it.
        if DEBUG:
            print >>sys.stderr,"abc: wxFrame: params is",self.params

        if self.params[0] != "":
            torrentfilename = self.params[0]
            self.startDownload(torrentfilename)

        # Init video player
        self.videoFrame = None
        feasible = return_feasible_playback_modes(self.utility.getPath())
        if PLAYBACKMODE_INTERNAL in feasible:
            # This means vlc is available
            from Tribler.Video.EmbeddedPlayer import VideoFrame
            iconpath = os.path.join(self.utility.getPath(),'Tribler','Images','tribler.ico')
            self.videoFrame = VideoFrame(self,'Tribler Video',iconpath)

            #self.videores = xrc.XmlResource("Tribler/vwxGUI/MyPlayer.xrc")
            #self.videoframe = self.videores.LoadFrame(None, "MyPlayer")
            #self.videoframe.Show()
            
            videoplayer = VideoPlayer.getInstance()
            videoplayer.set_parentwindow(self.videoFrame)
        else:
            videoplayer = VideoPlayer.getInstance()
            videoplayer.set_parentwindow(self)

        
        sys.stdout.write('GUI Complete.\n')

        self.Show(True)
        
        
        # Just for debugging: add test permids and display top 5 peers from which the most is downloaded in bartercastdb
#        bartercastdb = BarterCastDBHandler.getInstance()
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
        
        
        # Check to see if ABC is associated with torrents
        #######################################################
        if (sys.platform == 'win32'):
            if self.utility.config.Read('associate', "boolean"):
                if self.utility.regchecker and not self.utility.regchecker.testRegistry():
                    dialog = RegCheckDialog(self)
                    dialog.ShowModal()
                    dialog.Destroy()

        self.checkVersion()


    def startDownload(self,torrentfilename,destdir=None,tdef = None):
        try:
            if tdef is None:
                tdef = TorrentDef.load(torrentfilename)
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()
            if destdir is not None:
                dscfg.set_dest_dir(destdir)
        
            self.utility.session.start_download(tdef,dscfg)

        except Exception,e:
            self.onWarning(e)

        
    def checkVersion(self):
        guiserver = GUITaskQueue.getInstance()
        guiserver.add_task(self._checkVersion,10.0)

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
            _curr_status = line1.split()
            self.curr_version = _curr_status[0]
            if self.newversion(self.curr_version, my_version):
                # Arno: we are a separate thread, delegate GUI updates to MainThread
                self.upgradeCallback()
            
            # Also check new version of web2definitions for youtube etc. search
            Web2Updater(self.utility).checkUpdate()
        except Exception,e:
            print >> sys.stderr, "Tribler: Version check failed", ctime(time()), str(e)
            #print_exc()
            
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

    def onFocus(self, event = None):
        if event is not None:
            event.Skip()
        #self.window.getSelectedList(event).SetFocus()
        
    def setGUIupdate(self, update):
        oldval = self.GUIupdate
        self.GUIupdate = update
        
        if self.GUIupdate and not oldval:
            # Force an update of all torrents
            for torrent in self.utility.torrents["all"]:
                torrent.updateColumns()
                torrent.updateColor()


    def taskbarCallback(self):
        wx.CallAfter(self.onTaskBarActivate)


    #######################################
    # minimize to tray bar control
    #######################################
    def onTaskBarActivate(self, event = None):
        self.Iconize(False)
        self.Show(True)
        self.Raise()
        
        if self.tbicon is not None:
            self.tbicon.updateIcon(False)

        #self.window.list.SetFocus()

        # Resume updating GUI
        self.setGUIupdate(True)

    def onIconify(self, event = None):
        # This event handler is called both when being minimalized
        # and when being restored.
        if DEBUG:
            if event is not None:
                print  >> sys.stderr,"abc: onIconify(",event.Iconized()
            else:
                print  >> sys.stderr,"abc: onIconify event None"
        if event.Iconized():                                                                                                               
            if (self.utility.config.Read('mintray', "int") > 0
                and self.tbicon is not None):
                self.tbicon.updateIcon(True)
                self.Show(False)

            # Don't update GUI while minimized
            self.setGUIupdate(False)
        else:
            self.setGUIupdate(True)
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
                print  >> sys.stderr,"abc: onSize:",self.GetSize()
            else:
                print  >> sys.stderr,"abc: onSize: None"
        self.setGUIupdate(True)
        if event is not None:
            if event.GetEventType() == wx.EVT_MAXIMIZE:
                self.window.SetClientSize(self.GetClientSize())
            event.Skip()
        

        # Refresh subscreens
        self.refreshNeeded = True
        self.guiUtility.refreshOnResize()
        
    def onIdle(self, event = None):
        """
        Only refresh screens (especially detailsPanel) when resizes are finished
        This gives less flickering, but doesnt look pretty, so i commented it out
        """
        if self.refreshNeeded:
            self.guiUtility.refreshOnResize()
            self.refreshNeeded = False
        
    def getWindowSettings(self):
        width = self.utility.config.Read("window_width")
        height = self.utility.config.Read("window_height")
        try:
            size = wx.Size(int(width), int(height))
        except:
            size = wx.Size(710, 400)

        x = self.utility.config.Read("window_x")
        y = self.utility.config.Read("window_y")
        if (x == "" or y == ""):
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
        if event != None:
            nr = event.GetEventType()
            lookup = { wx.EVT_CLOSE.evtType[0]: "EVT_CLOSE", wx.EVT_QUERY_END_SESSION.evtType[0]: "EVT_QUERY_END_SESSION", wx.EVT_END_SESSION.evtType[0]: "EVT_END_SESSION" }
            if nr in lookup: nr = lookup[nr]
            print "Closing due to event ",nr
            print >>sys.stderr,"Closing due to event ",nr
        else:
            print "Closing untriggered by event"
        
        # Don't do anything if the event gets called twice for some reason
        if self.utility.abcquitting:
            return

        # Check to see if we can veto the shutdown
        # (might not be able to in case of shutting down windows)
        if event is not None:
            try:
                if event.CanVeto() and self.utility.config.Read('confirmonclose', "boolean") and not event.GetEventType() == wx.EVT_QUERY_END_SESSION.evtType[0]:
                    dialog = wx.MessageDialog(None, self.utility.lang.get('confirmmsg'), self.utility.lang.get('confirm'), wx.OK|wx.CANCEL)
                    result = dialog.ShowModal()
                    dialog.Destroy()
                    if result != wx.ID_OK:
                        event.Veto()
                        return
            except:
                data = StringIO()
                print_exc(file = data)
                sys.stderr.write(data.getvalue())
                pass
            
        self.utility.abcquitting = True
        self.GUIupdate = False
        
        self.guiUtility.guiOpen.clear()
        
        try:
            # Restore the window before saving size and position
            # (Otherwise we'll get the size of the taskbar button and a negative position)
            self.onTaskBarActivate()
            self.saveWindowSettings()
        except:
            print_exc()

        try:
            if self.buddyFrame is not None:
                self.buddyFrame.Destroy()
            if self.fileFrame is not None:
                self.fileFrame.Destroy()
            if self.videoFrame is not None:
                self.videoFrame.Destroy()
        except:
            pass

        try:
            if self.tbicon is not None:
                self.tbicon.RemoveIcon()
                self.tbicon.Destroy()
            self.Destroy()
        except:
            data = StringIO()
            print_exc(file = data)
            sys.stderr.write(data.getvalue())
            pass

        #tribler_done(self.utility.getConfigPath())            
        
        if DEBUG:    
            print >>sys.stderr,"abc: OnCloseWindow END"

        if DEBUG:
            ts = enumerate()
            for t in ts:
                print >>sys.stderr,"abc: Thread still running",t.getName(),"daemon",t.isDaemon()



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


    def onReachable(self,event=None):
        """ Called by GUI thread """
        if self.firewallStatus is not None:
            self.firewallStatus.setToggled(True)
            tt = self.firewallStatus.GetToolTip()
            if tt is not None:
                tt.SetTip(self.utility.lang.get('reachable_tooltip'))

    def setActivity(self,type,msg=u'', utility=None):
        
        if utility is None:
            utility = self.utility
            
        if currentThread().getName() != "MainThread":
            print  >> sys.stderr,"abc: setActivity thread",currentThread().getName(),"is NOT MAIN THREAD"
            print_stack()
    
        if type == NTFY_ACT_NONE:
            prefix = u''
            msg = u''
        elif type == NTFY_ACT_UPNP:
            prefix = utility.lang.get('act_upnp')
        elif type == NTFY_ACT_REACHABLE:
            prefix = utility.lang.get('act_reachable')
        elif type == NTFY_ACT_GET_EXT_IP_FROM_PEERS:
            prefix = utility.lang.get('act_get_ext_ip_from_peers')
        elif type == NTFY_ACT_MEET:
            prefix = utility.lang.get('act_meet')
        elif type == NTFY_ACT_GOT_METADATA:
            prefix = utility.lang.get('act_got_metadata')
        elif type == NTFY_ACT_RECOMMEND:
            prefix = utility.lang.get('act_recommend')
        elif type == NTFY_ACT_DISK_FULL:
            prefix = utility.lang.get('act_disk_full')   
        elif type == NTFY_ACT_NEW_VERSION:
            prefix = utility.lang.get('act_new_version')   
        if msg == u'':
            text = prefix
        else:
            text = unicode( prefix+u' '+msg)
            
        if DEBUG:
            print  >> sys.stderr,"abc: Setting activity",`text`,"EOT"
        self.messageField.SetLabel(text)

    def set_player_status(self,s):
        """ Called by VideoServer when using an external player """
        if self.videoFrame is not None:
            self.videoFrame.set_player_status(status)

    def set_wxapp(self,wxapp):
        self.wxapp = wxapp
        
    def quit(self):
        if self.wxapp is not None:
            self.wxapp.ExitMainLoop()
        

##############################################################
#
# Class : ABCApp
#
# Main ABC application class that contains ABCFrame Object
#
##############################################################
class ABCApp(wx.App):
    def __init__(self, x, params, single_instance_checker, installdir):
        self.params = params
        self.single_instance_checker = single_instance_checker
        self.installdir = installdir
        self.error = None
            
        wx.App.__init__(self, x)
        
        
    def OnInit(self):
        try:
            self.utility = Utility(self.installdir)
            self.utility.app = self

            self.postinitstarted = False
            """
            Hanging self.OnIdle to the onidle event doesnot work under linux (ubuntu). The images in xrc files
            will not load in any but the filespanel.
            """
            #self.Bind(wx.EVT_IDLE, self.OnIdle)
            
        
            # Set locale to determine localisation
            #locale.setlocale(locale.LC_ALL, '')

            sys.stdout.write('Client Starting Up.\n')
            sys.stdout.write('Build: ' + self.utility.lang.get('build') + '\n')

            bm = wx.Bitmap(os.path.join(self.utility.getPath(),'Tribler','Images','splash.jpg'),wx.BITMAP_TYPE_JPEG)
            #s = wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN
            #s = wx.SIMPLE_BORDER|wx.FRAME_NO_TASKBAR|wx.FRAME_FLOAT_ON_PARENT
            self.splash = wx.SplashScreen(bm, wx.SPLASH_CENTRE_ON_SCREEN|wx.SPLASH_TIMEOUT, 1000, None, -1)
            
            # Arno: Do heavy startup on GUI thread after splash screen has been
            # painted.
            self.splash.Show()
            "Replacement for self.Bind(wx.EVT_IDLE, self.OnIdle)"
            wx.CallAfter(self.PostInit)    
            return True
            
        except Exception,e:
            print_exc()
            self.error = e
            self.onError()
            return False

    def OnIdle(self,event=None):
        if not self.postinitstarted:
            self.postinitstarted = True
            wx.CallAfter(self.PostInit)
            # Arno: On Linux I sometimes have to move the mouse into the splash
            # for the rest of Tribler to start. H4x0r
            if event is not None:
                event.RequestMore(True)
                event.Skip()


    def PostInit(self):
        try:
            # On Linux: allow painting of splash screen first.
            wx.Yield()
            
            # Initialise fonts
            font.init()

            #tribler_init(self.utility.getConfigPath(),self.utility.getPath(),self.db_exception_handler)
            
            self.utility.postAppInit(os.path.join(self.installdir,'Tribler','Images','tribler.ico'))
            
            # Singleton for executing tasks that are too long for GUI thread and
            # network thread
            self.guiserver = GUITaskQueue.getInstance()
            self.guiserver.register()
    
            # H4x0r a bit
            set_tasteheart_bitmaps(self.utility.getPath())
            set_perfBar_bitmaps(self.utility.getPath())

            cat = Category.getInstance(self.utility.getPath())
            cat.init_from_main(self.utility)
            
            # Put it here so an error is shown in the startup-error popup
            # Start server for instance2instance communication
            self.i2is = Instance2InstanceServer(I2I_LISTENPORT,self.i2icallback) 
            self.i2is.start()
            
            self.videoplayer = VideoPlayer.getInstance()
            self.videoplayer.register(self.utility)
            # Start HTTP server for serving video to player widget
            self.videoserv = VideoHTTPServer.getInstance(VIDEOHTTP_LISTENPORT) # create
            self.videoserv.background_serve()
            self.videoserv.register(self.videoserver_error_callback,self.videoserver_set_status_callback)

            notification_init( self.utility )

            #
            # Read and create GUI from .xrc files
            #
            #self.frame = ABCFrame(-1, self.params, self.utility)
            self.guiUtility = GUIUtility.getInstance(self.utility, self.params)
            updateXRC.main([os.path.join(self.utility.getPath(),'Tribler','Main','vwxGUI')])
            self.res = xrc.XmlResource(os.path.join(self.utility.getPath(),'Tribler', 'Main','vwxGUI','MyFrame.xrc'))
            self.guiUtility.xrcResource = self.res
            self.frame = self.res.LoadFrame(None, "MyFrame")
            self.guiUtility.frame = self.frame
            
            self.guiUtility.scrollWindow = xrc.XRCCTRL(self.frame, "level0")
            self.guiUtility.mainSizer = self.guiUtility.scrollWindow.GetSizer()
            self.frame.topBackgroundRight = xrc.XRCCTRL(self.frame, "topBG3")
            self.guiUtility.scrollWindow.SetScrollbars(1,1,1024,768)
            self.guiUtility.scrollWindow.SetScrollRate(15,15)
            self.frame.mainButtonPersons = xrc.XRCCTRL(self.frame, "mainButtonPersons")

            self.frame.numberPersons = xrc.XRCCTRL(self.frame, "numberPersons")
            numperslabel = xrc.XRCCTRL(self.frame, "persons")
            self.frame.numberFiles = xrc.XRCCTRL(self.frame, "numberFiles")
            numfileslabel = xrc.XRCCTRL(self.frame, "files")
            self.frame.messageField = xrc.XRCCTRL(self.frame, "messageField")
            self.frame.firewallStatus = xrc.XRCCTRL(self.frame, "firewallStatus")
            tt = self.frame.firewallStatus.GetToolTip()
            if tt is not None:
                tt.SetTip(self.utility.lang.get('unknownreac_tooltip'))
            
            if sys.platform == "linux2":
                self.frame.numberPersons.SetFont(wx.Font(9,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
                self.frame.numberFiles.SetFont(wx.Font(9,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
                self.frame.messageField.SetFont(wx.Font(9,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
                numperslabel.SetFont(wx.Font(9,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
                numfileslabel.SetFont(wx.Font(9,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))

            self.menubar = MainMenuBar(self.frame,self.utility)
            self.frame.set_wxapp(self)

            # Make sure self.utility.frame is set
            self.startAPI()
            
            #self.frame.Refresh()
            #self.frame.Layout()
            self.frame.Show(True)
            self.setDBStats()
            
            self.Bind(wx.EVT_QUERY_END_SESSION, self.frame.OnCloseWindow)
            self.Bind(wx.EVT_END_SESSION, self.frame.OnCloseWindow)
            
            # Arno, 2007-05-03: wxWidgets 2.8.3.0 and earlier have the MIME-type for .bmp 
            # files set to 'image/x-bmp' whereas 'image/bmp' is the official one.
            try:
                bmphand = None
                hands = wx.Image.GetHandlers()
                for hand in hands:
                    #print "Handler",hand.GetExtension(),hand.GetType(),hand.GetMimeType()
                    if hand.GetMimeType() == 'image/x-bmp':
                        bmphand = hand
                        break
                #wx.Image.AddHandler()
                if bmphand is not None:
                    bmphand.SetMimeType('image/bmp')
            except:
                # wx < 2.7 don't like wx.Image.GetHandlers()
                print_exc()
            
            # Must be after ABCLaunchMany is created
            self.torrentfeed = TorrentFeedThread.getInstance()
            self.torrentfeed.register(self.utility)
            self.torrentfeed.start()
            
            #print "DIM",wx.GetDisplaySize()
            #print "MM",wx.GetDisplaySizeMM()

            wx.CallAfter(self.startWithRightView)            
            
        except Exception,e:
            print_exc()
            self.error = e
            self.onError()
            return False

        return True

    def startAPI(self):
        
        # Start Tribler Session
        state_dir = Session.get_default_state_dir()
        
        cfgfilename = Session.get_default_config_filename(state_dir)
        if DEBUG:
            print >>sys.stderr,"main: Session config",cfgfilename
        try:
            self.sconfig = SessionStartupConfig.load(cfgfilename)
        except:
            print_exc()
            self.sconfig = SessionStartupConfig()
            self.sconfig.set_state_dir(state_dir)
            # Set default Session params here
            torrcolldir = os.path.join(get_default_dest_dir(),STATEDIR_TORRENTCOLL_DIR)
            self.sconfig.set_torrent_collecting_dir(torrcolldir)
            
            # rename old collected torrent directory
            try:
                old_collected_torrent_dir = os.path.join(state_dir, 'torrent2')
                if not os.path.exists(torrcolldir) and os.path.isdir(old_collected_torrent_dir):
                    os.rename(old_collected_torrent_dir, torrcolldir)
                    print >>sys.stderr,"main: Moved dir with old collected torrents to", torrcolldir
            except:
                print_exc()
        
        s = Session(self.sconfig)
        self.utility.session = s

        
        s.add_observer(self.sesscb_ntfy_reachable,NTFY_REACHABLE,[NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_activities,NTFY_ACTIVITIES,[NTFY_INSERT])
        
        
        # ARNOCOMMENT: Not yet working as Jie's sqlDB stuff was not yet 
        # instrumented with notifier calls.
        s.add_observer(self.sesscb_ntfy_dbstats,NTFY_TORRENTS,[NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_dbstats,NTFY_PEERS,[NTFY_INSERT])

        # Load the default DownloadStartupConfig
        dlcfgfilename = get_default_dscfg_filename(s)
        try:
            defaultDLConfig = DefaultDownloadStartupConfig.load(dlcfgfilename)
        except:
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            print_exc()
            defaultdestdir = os.path.join(get_default_dest_dir())
            defaultDLConfig.set_dest_dir(defaultdestdir)

        #print >>sys.stderr,"main: Read dlconfig",defaultDLConfig.dlconfig

        s.set_coopdlconfig(defaultDLConfig)
        
        # Load all other downloads
        # TODO: reset all saved DownloadConfig to new default?
        s.load_checkpoint()

        # Create global rate limiter
        self.ratelimiter = UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager()
        self.rateadjustcount = 0 
        maxup = self.utility.config.Read('maxuploadrate', "int")
        maxdown = self.utility.config.Read('maxdownloadrate', "int")
        maxupseed = self.utility.config.Read('maxseeduploadrate', "int")
        self.ratelimiter.set_global_max_speed(UPLOAD,maxup)
        self.ratelimiter.set_global_max_speed(DOWNLOAD,maxdown)
        self.ratelimiter.set_global_max_seedupload_speed(maxupseed)
        self.utility.ratelimiter = self.ratelimiter
 
        # Only allow updates to come in after we defined ratelimiter
        s.set_download_states_callback(self.sesscb_states_callback)
 

    def sesscb_states_callback(self,dslist):
        """ Called by SessionThread """
        wx.CallAfter(self.gui_states_callback,dslist)
        return(1.0,False)
        
    def gui_states_callback(self,dslist):
        """ Called by MainThread  """
        if DEBUG:
            print >>sys.stderr,"main: Stats:"
        try:
            # Pass DownloadStates to libaryView
            try:
                # Jelle: libraryMode only exists after user clicked button
                modedata = self.guiUtility.standardOverview.data['libraryMode']
                gm = modedata['grid'].gridManager
                gm.download_state_network_callback(dslist)
            except KeyError:
                pass
            except:
                print_exc()
            
            # Adjust speeds once every 4 seconds
            adjustspeeds = False
            if self.rateadjustcount % 4 == 0:
                adjustspeeds = True
            self.rateadjustcount += 1
    
            if adjustspeeds:
                self.ratelimiter.add_downloadstatelist(dslist)
                self.ratelimiter.adjust_speeds()
                
            # Update stats in lower right overview box
            self.guiUtility.refreshTorrentStats(dslist)
                
        except:
            print_exc()


    def sesscb_states_callback(self,dslist):
        """ Called by SessionThread """
        wx.CallAfter(self.gui_states_callback,dslist)
        return(1.0,False)
        
    def gui_states_callback(self,dslist):
        """ Called by MainThread  """
        try:
            # Pass DownloadStates to libaryView
            try:
                # Jelle: libraryMode only exists after user clicked button
                modedata = self.guiUtility.standardOverview.data['libraryMode']
                gm = modedata['grid'].gridManager
                gm.download_state_network_callback(dslist)
            except KeyError:
                pass
            except AttributeError:
                pass
            except:
                print_exc()
            
            # Adjust speeds once every 4 seconds
            adjustspeeds = False
            if self.rateadjustcount % 4 == 0:
                adjustspeeds = True
            self.rateadjustcount += 1
    
            if adjustspeeds:
                self.ratelimiter.add_downloadstatelist(dslist)
                self.ratelimiter.adjust_speeds()
                
            # Update stats in lower right overview box
            self.guiUtility.refreshTorrentStats(dslist)
                
        except:
            print_exc()


    def sesscb_ntfy_dbstats(self,subject,changeType,objectID,*args):
        """ Called by SessionCallback thread """
        wx.CallAfter(self.setDBStats)
        
        
    def setDBStats(self):
        """ Set total # peers and torrents discovered """
        
        # Arno: GUI thread accessing database
        peer_db = self.utility.session.open_dbhandler(NTFY_PEERS)
        npeers = peer_db.getNumberPeers()
        torrent_db = self.utility.session.open_dbhandler(NTFY_TORRENTS)
        nfiles = torrent_db.getNumberTorrents()
        # Arno: not closing db connections, assuming main thread's will be 
        # closed at end.
                
        self.frame.numberPersons.SetLabel('%d' % npeers)
        self.frame.numberFiles.SetLabel('%d' % nfiles)
        

        
    def sesscb_ntfy_activities(self,subject,changeType,objectID,msg):
        # Called by SessionCallback thread
        #print >>sys.stderr,"main: sesscb_ntfy_activities called:",subject,changeType,objectID,msg
        wx.CallAfter(self.frame.setActivity,objectID,msg, self.utility)

    def sesscb_ntfy_reachable(self,subject,changeType,objectID,msg):
        wx.CallAfter(self.frame.onReachable)


    def videoserver_error_callback(self,e,url):
        """ Called by HTTP serving thread """
        wx.CallAfter(self.videoserver_error_guicallback,e,url)
        
    def videoserver_error_guicallback(self,e,url):
        print >>sys.stderr,"main: Video server reported error",str(e)
        #    self.show_error(str(e))
        pass

    def videoserver_set_status_callback(self,status):
        """ Called by HTTP serving thread """
        wx.CallAfter(self.videoserver_set_status_guicallback,status)

    def videoserver_set_status_guicallback(self,status):
        # TODO:
        if self.frame is not None:
            self.frame.set_player_status(status)


    def onError(self,source=None):
        # Don't use language independence stuff, self.utility may not be
        # valid.
        msg = "Unfortunately, Tribler ran into an internal error:\n\n"
        if source is not None:
            msg += source
        msg += str(self.error.__class__)+':'+str(self.error)
        msg += '\n'
        msg += 'Please see the FAQ on www.tribler.org on how to act.'
        dlg = wx.MessageDialog(None, msg, "Tribler Fatal Error", wx.OK|wx.ICON_ERROR)
        result = dlg.ShowModal()
        print_exc()
        dlg.Destroy()

    def MacOpenFile(self,filename):
        self.utility.queue.addtorrents.AddTorrentFromFile(filename)

    def OnExit(self):
        print >>sys.stderr,"main: ONEXIT"
        
        self.torrentfeed.shutdown()

        self.utility.session.shutdown()
        
        if not ALLOW_MULTIPLE:
            del self.single_instance_checker
        return 0
    
    def db_exception_handler(self,e):
        if DEBUG:
            print >> sys.stderr,"abc: Database Exception handler called",e,"value",e.args,"#"
        try:
            if e.args[1] == "DB object has been closed":
                return # We caused this non-fatal error, don't show.
            if self.error is not None and self.error.args[1] == e.args[1]:
                return # don't repeat same error
        except:
            print >> sys.stderr, "abc: db_exception_handler error", e, type(e)
            print_exc()
            #print_stack()
        self.error = e
        onerror_lambda = lambda:self.onError(source="The database layer reported:  ") 
        wx.CallAfter(onerror_lambda)
    
    def getConfigPath(self):
        return self.utility.getConfigPath()

    def startWithRightView(self):
        if self.params[0] != "":
            self.guiUtility.standardLibraryOverview()
 
 
    def i2icallback(self,cmd,param):
        """ Called by Instance2Instance thread """
        
        print >>sys.stderr,"abc: Another instance called us with cmd",cmd,"param",param
        
        if cmd == 'START':
            torrentfilename = None
            if param.startswith('http:'):
                # Retrieve from web 
                f = tempfile.NamedTemporaryFile()
                n = urllib2.urlopen(url)
                data = n.read()
                f.write(data)
                f.close()
                n.close()
                torrentfilename = f.name
            else:
                torrentfilename = param
                
            # Switch to GUI thread
            start_download_lambda = lambda:self.frame.startDownload(torrentfilename)
            wx.CallAfter(start_download_lambda)
    
        
class DummySingleInstanceChecker:
    
    def __init__(self,basename):
        pass

    def IsAnotherRunning(self):
        "Uses pgrep to find other tribler.py processes"
        # If no pgrep available, it will always start tribler
        progressInfo = commands.getoutput('pgrep -fl "tribler\.py" | grep -v pgrep')
        numProcesses = len(progressInfo.split('\n'))
        if DEBUG:
            print 'ProgressInfo: %s, num: %d' % (progressInfo, numProcesses)
        return numProcesses > 1
                
        
##############################################################
#
# Main Program Start Here
#
##############################################################
def run(params = None):
    if params is None:
        params = [""]
    
    if len(sys.argv) > 1:
        params = sys.argv[1:]
    
    # Create single instance semaphore
    # Arno: On Linux and wxPython-2.8.1.1 the SingleInstanceChecker appears
    # to mess up stderr, i.e., I get IOErrors when writing to it via print_exc()
    #
    if sys.platform != 'linux2':
        single_instance_checker = wx.SingleInstanceChecker("tribler-" + wx.GetUserId())
    else:
        single_instance_checker = DummySingleInstanceChecker("tribler-")

    if not ALLOW_MULTIPLE and single_instance_checker.IsAnotherRunning():
        #Send  torrent info to abc single instance
        if params[0] != "":
            torrentfilename = params[0]
            i2ic = Instance2InstanceClient(I2I_LISTENPORT,'START',torrentfilename)
    else:
        arg0 = sys.argv[0].lower()
        if arg0.endswith('.exe'):
            installdir = os.path.abspath(os.path.dirname(sys.argv[0]))
        else:
            installdir = os.getcwd()  
        # Arno: don't chdir to allow testing as other user from other dir.
        #os.chdir(installdir)

        # Launch first abc single instance
        app = ABCApp(0, params, single_instance_checker, installdir)
        configpath = app.getConfigPath()
        app.MainLoop()

    print "Client shutting down. Sleeping for a few seconds to allow other threads to finish"
    sleep(1)

    # This is the right place to close the database, unfortunately Linux has
    # a problem, see ABCFrame.OnCloseWindow
    #
    #if sys.platform != 'linux2':
    #    tribler_done(configpath)
    #os._exit(0)

if __name__ == '__main__':
    run()

