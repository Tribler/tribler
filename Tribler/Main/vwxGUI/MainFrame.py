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

from threading import Thread, Event,currentThread,enumerate
import time
from traceback import print_exc, print_stack
from cStringIO import StringIO
import urllib

from Tribler.Main.Utility.utility import Utility
from Tribler.Main.Utility.constants import * #IGNORE:W0611
import Tribler.Main.vwxGUI.font as font
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.Dialogs.systray import ABCTaskBarIcon 
from Tribler.Main.notification import init as notification_init
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename
from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Video.VideoFrame import VideoFrame
from Tribler.Video.utils import videoextdefaults

from Tribler.Category.Category import Category
from Tribler.Web2.util.update import Web2Updater


from Tribler.Core.simpledefs import *
from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import show_permid

DEBUG = True


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
class MainFrame(wx.Frame):
    def __init__(self, *args):
        self.firewallStatus = None
        self.utility = None
        self.category = None
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

        # Init video player
        self.videoFrame = None
        sys.stdout.write('GUI Complete.\n')

        ##self.standardOverview.Show(True)
        self.Show(True)
        
        
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
            torrentfilename = self.params[0]
            self.startDownload(torrentfilename,cmdline=True)


    def startDownload(self,torrentfilename,destdir=None,tdef = None, cmdline = False, clicklog=None,name=None,vodmode=False):
        
        if DEBUG:
            print >>sys.stderr,"mainframe: startDownload:",torrentfilename,destdir,tdef,cmdline
        try:
            if tdef is None:
                tdef = TorrentDef.load(torrentfilename)
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()
            if destdir is not None:
                dscfg.set_dest_dir(destdir)
        
            videofiles = tdef.get_files(exts=videoextdefaults)

            if vodmode or tdef.get_live() or (cmdline and len(videofiles) > 0):
                print >>sys.stderr, 'MainFrame: startDownload: Starting in VOD mode'
                videoplayer = VideoPlayer.getInstance()
                result = videoplayer.start_and_play(tdef,dscfg)
            else:
                print >>sys.stderr, 'MainFrame: startDownload: Starting in DL mode'
                result = self.utility.session.start_download(tdef,dscfg)
                
            self.guiUtility.frame.newFile.SetLabel('New File added')
            # store result because we want to store clicklog data right after download was started, then return result
            #mypref = self.utility.session.open_dbhandler(NTFY_MYPREFERENCES)
            # mypref.addClicklogToMyPreference(tdef.get_infohash(), clicklog)
            return result  

        except DuplicateDownloadException:
            # show nice warning dialog
            dlg = wx.MessageDialog(None,
                                   self.utility.lang.get('duplicate_download_msg'),
                                   self.utility.lang.get('duplicate_download_title'),
                                   wx.OK|wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()

        except Exception,e:
            print_exc()
            self.onWarning(e)




        
    def checkVersion(self):
        guiserver = GUITaskQueue.getInstance()
        guiserver.add_task(self._checkVersion,10.0)

    def _checkVersion(self):
        # Called by GUITaskQueue thread
        my_version = self.utility.getVersion()
        try:
            curr_status = urllib.urlopen('http://tribler.org/version/').readlines()
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
            ##Web2Updater(self.utility).checkUpdate()
        except Exception,e:
            print >> sys.stderr, "Tribler: Version check failed", time.ctime(time.time()), str(e)
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
                print  >> sys.stderr,"main: onIconify(",event.Iconized()
            else:
                print  >> sys.stderr,"main: onIconify event None"
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
                print  >> sys.stderr,"main: onSize:",self.GetSize()
            else:
                print  >> sys.stderr,"main: onSize: None"
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
                    dialog = wx.MessageDialog(None, self.utility.lang.get('confirmmsg'), self.utility.lang.get('confirm'), wx.OK|wx.CANCEL)
                    result = dialog.ShowModal()
                    dialog.Destroy()
                    if result != wx.ID_OK:
                        event.Veto()
                        return
            except:
                print_exc()
            
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
            print_exc()

        if DEBUG:    
            print >>sys.stderr,"mainframe: OnCloseWindow END"

        if DEBUG:
            ts = enumerate()
            for t in ts:
                print >>sys.stderr,"mainframe: Thread still running",t.getName(),"daemon",t.isDaemon()

        if not found:
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


    def onReachable(self,event=None):
        """ Called by GUI thread """
        self.guiUtility.set_reachable()
        #if self.top_bg.firewallStatus is not None:
        #    self.top_bg.firewallStatus.setToggled(True)
        #    tt = self.top_bg.firewallStatus.GetToolTip()
        #    if tt is not None:
        #        tt.SetTip(self.utility.lang.get('reachable_tooltip'))

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
            
        #if DEBUG:
        print  >> sys.stderr,"main: Setting activity",`text`
        #self.messageField.SetLabel(text)

    def set_player_status(self,s):
        """ Called by VideoServer when using an external player """
        if self.videoFrame is not None:
            self.videoFrame.set_player_status(s)

    def set_wxapp(self,wxapp):
        self.wxapp = wxapp
        
    def quit(self):
        if self.wxapp is not None:
            self.wxapp.ExitMainLoop()
     
     
class PlayerFrame(VideoFrame):
    """
    Wrapper around VideoFrame that allows us to catch the Close event. On
    that event we should notify tribler such that it can stop any live torrents,
    and restart others that may have been stopped.
    """
    def __init__(self,parent,title,iconpath,vlcwrap,logopath):
        VideoFrame.__init__(self,parent,title,iconpath,vlcwrap,logopath)
        self.parent = parent
        self.closed = False
        
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
    
    def show_videoframe(self):
        self.closed = False
        VideoFrame.show_videoframe(self)
    
    def OnCloseWindow(self, event = None):
        
        print >>sys.stderr,"PlayerFrame: ON CLOSE WINDOW"
        if not self.closed:
            self.closed = True
            VideoFrame.OnCloseWindow(self,event)
            
            if self.parent.wxapp is not None:
                self.parent.wxapp.OnClosingVideoFrameOrExtPlayer()
            
        print >>sys.stderr,"PlayerFrame: Closing done"
        

