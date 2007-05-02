#!/usr/bin/python

#########################################################################
#
# Author : Choopan RATTANAPOKA, Jie Yang, Arno Bakker
#
# Description : Main ABC [Yet Another Bittorrent Client] python script.
#               you can run from source code by using
#               >python abc.py
#               need Python, WxPython in order to run from source code.
#########################################################################

# Arno: G*dd*mn M2Crypto overrides the method for https:// in the
# standard Python libraries. This causes msnlib to fail and makes Tribler
# freakout when "http://www.tribler.org/version" is redirected to
# "https://www.tribler.org/version/" (which happened during our website
# changeover) Until M2Crypto 0.16 is patched I'll restore the method to the
# original, as follows.
#
# This must be done in the first python file that is started.
#
import urllib
original_open_https = urllib.URLopener.open_https
import M2Crypto
urllib.URLopener.open_https = original_open_https

import sys, locale
import os
import wx
from wx import xrc
#import hotshot

from threading import Thread, Timer, Event,currentThread
from time import time, ctime, sleep
from traceback import print_exc, print_stack
from cStringIO import StringIO
import urllib

from interconn import ServerListener, ClientPassParam
from launchmanycore import ABCLaunchMany

from ABC.Toolbars.toolbars import ABCBottomBar2, ABCStatusBar, ABCStatusButtons, ABCMenuBar, ABCToolBar
from ABC.GUI.menu import ABCMenu
from ABC.Scheduler.scheduler import ABCScheduler

from webservice import WebListener

if (sys.platform == 'win32'):
    from Dialogs.regdialog import RegCheckDialog

from ABC.GUI.list import ManagedList
from Utility.utility import Utility
from Utility.constants import * #IGNORE:W0611

from Tribler.__init__ import tribler_init, tribler_done
from Tribler.Dialogs.ContentFrontPanel import *
from BitTornado.__init__ import product_name
from safeguiupdate import DelayedInvocation,FlaglessDelayedInvocation
import webbrowser
from Tribler.Dialogs.MugshotManager import MugshotManager
from Tribler.vwxGUI.GuiUtility import GUIUtility
import Tribler.vwxGUI.updateXRC as updateXRC
from Tribler.Video.VideoPlayer import VideoPlayer,return_feasible_playback_modes,PLAYBACKMODE_INTERNAL
from Tribler.Video.VideoServer import VideoHTTPServer
from Tribler.Dialogs.GUIServer import GUIServer
from Tribler.vwxGUI.TasteHeart import set_tasteheart_bitmaps
from Tribler.vwxGUI.perfBar import set_perfBar_bitmaps

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
    def __init__(self, utility):
        # Initialize the wsFileDropTarget Object 
        wx.FileDropTarget.__init__(self) 
        # Store the Object Reference for dropped files 
        self.utility = utility
      
    def OnDropFiles(self, x, y, filenames):
        for filename in filenames:
            self.utility.queue.addtorrents.AddTorrentFromFile(filename)
        return True


##############################################################
#
# Class : ABCList
#
# ABC List class that contains the torrent list
#
############################################################## 
class ABCList(ManagedList):
    def __init__(self, parent):
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        
        prefix = 'column'
        minid = 4
        maxid = 26
        exclude = []
        rightalign = [COL_PROGRESS, 
                      COL_SIZE, 
                      COL_DLSPEED, 
                      COL_ULSPEED, 
                      COL_RATIO, 
                      COL_PEERPROGRESS, 
                      COL_DLSIZE, 
                      COL_ULSIZE, 
                      COL_TOTALSPEED]

        ManagedList.__init__(self, parent, style, prefix, minid, maxid, exclude, rightalign)
        
        dragdroplist = FileDropTarget(self.utility)
        self.SetDropTarget(dragdroplist)
        
        self.lastcolumnsorted = -1
        self.reversesort = 0

        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColLeftClick)

        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnItemSelected)
        
        # Bring up advanced details on left double click
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        
        # Bring up local settings on middle double click
        self.Bind(wx.EVT_MIDDLE_DCLICK, self.utility.actions[ACTION_LOCALUPLOAD].action)

    # Do thing when keys are pressed down
    def OnKeyDown(self, event):
        keycode = event.GetKeyCode()
        if event.CmdDown():
            if keycode == ord('a') or keycode == ord('A'):
                # Select all files (CTRL-A)
                self.selectAll()
            elif keycode == ord('x') or keycode == ord('X'):
                # Invert file selection (CTRL-X)
                self.invertSelection()
        elif keycode == wx.WXK_RETURN or keycode == wx.WXK_NUMPAD_ENTER:
            # Open advanced details (Enter)
            self.utility.actions[ACTION_DETAILS].action()
        elif keycode == wx.WXK_SPACE:
            # Open local settings (Space)
            self.utility.actions[ACTION_LOCALUPLOAD].action()
        elif keycode == 399:
            # Open right-click menu (windows menu key)
            self.OnItemSelected()
        
        event.Skip()
        
    def OnColLeftClick(self, event):
        rank = event.GetColumn()
        colid = self.columns.getIDfromRank(rank)
        if colid == self.lastcolumnsorted:
            self.reversesort = 1 - self.reversesort
        else:
            self.reversesort = 0
        self.lastcolumnsorted = colid
        self.utility.queue.sortList(colid, self.reversesort)       
        
    def selectAll(self):
        self.updateSelected(select = range(0, self.GetItemCount()))

    def updateSelected(self, unselect = None, select = None):
        if unselect is not None:
            for index in unselect:
                self.SetItemState(index, 0, wx.LIST_STATE_SELECTED)
        if select is not None:
            for index in select:
                self.Select(index)
        self.SetFocus()

    def getTorrentSelected(self, firstitemonly = False, reverse = False):
        queue = self.utility.queue
        
        torrentselected = []
        for index in self.getSelected(firstitemonly, reverse):
            ABCTorrentTemp = queue.getABCTorrent(index = index)
            if ABCTorrentTemp is not None:
                torrentselected.append(ABCTorrentTemp)
        return torrentselected

    def OnItemSelected(self, event = None):
        selected = self.getTorrentSelected()
        if not selected:
            return

        popupmenu = ABCMenu(self.utility, 'menu_listrightclick')

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        if event is None:
            # use the position of the first selected item (key event)
            ABCTorrentTemp = selected[0]
            position = self.GetItemPosition(ABCTorrentTemp.listindex)
        else:
            # use the cursor position (mouse event)
            position = event.GetPosition()
        
        self.PopupMenu(popupmenu, position)

    def OnLeftDClick(self, event):
        event.Skip()
        try:
            self.utility.actions[ACTION_DETAILS].action()
        except:
            print_exc()


##############################################################
#
# Class : ABCPanel
#
# Main ABC Panel class
#
############################################################## 
class ABCPanel(wx.Panel):
    def __init__(self, parent):
        style = wx.CLIP_CHILDREN
        wx.Panel.__init__(self, parent, -1, style = style)

        #Debug Output.
        sys.stdout.write('Preparing GUI.\n');
        
        self.utility    = parent.utility
        self.utility.window = self
        self.queue = self.utility.queue
               
        # List of deleting torrents events that occur when the RateManager is active
        # Such events are processed after the RateManager finishes
        # postponedevents is a list of tupples : each tupple contains the method of ABCPanel to be called to
        # deal with the event and the event.
        self.postponedevents = []

        #Manual Bittorrent Adding UI
        ##############################
        colSizer = wx.BoxSizer(wx.VERTICAL)
        
        #buddyCastEnabled = int(self.utility.config.Read('enablerecommender'))
        buddyCastEnabled = False
        if (buddyCastEnabled):
            split = ABCSplitterWindow(self, -1)
            self.list = ABCList(split)
            self.utility.list = self.list
            self.contentPanel = ContentFrontPanel(split)
            split.SplitHorizontally(self.list, self.contentPanel, 100) #  module dependent
        
            colSizer.Add(split, 1, wx.ALL|wx.EXPAND, 3)
        
        else: # buddycast disabled
            self.list = ABCList(self)
            self.utility.list = self.list
            colSizer.Add(self.list, 1, wx.ALL|wx.EXPAND, 3)
            
        # Add status bar
        statbarbox = wx.BoxSizer(wx.HORIZONTAL)
        self.sb_buttons = ABCStatusButtons(self,self.utility)
        statbarbox.Add(self.sb_buttons, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
        self.abc_sb = ABCStatusBar(self,self.utility)
        statbarbox.Add(self.abc_sb, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
        colSizer.Add(statbarbox, 0, wx.ALL|wx.EXPAND, 0)

        
        #colSizer.Add(self.contentPanel, 1, wx.ALL|wx.EXPAND, 3)
        self.SetSizer(colSizer)
        self.SetAutoLayout(True)
        
        self.list.SetFocus()
        
        
    def getSelectedList(self, event = None):
        return self.list

    ######################################
    # Update ABC on-the-fly
    ######################################
    def updateColumns(self, force = False):
        # Update display in column for inactive torrent
        for ABCTorrentTemp in self.utility.torrents["all"]:
            ABCTorrentTemp.updateColumns(force = force)
 
      
##############################################################
#
# Class : ABCTaskBarIcon
#
# Task Bar Icon
#
############################################################## 
class ABCTaskBarIcon(wx.TaskBarIcon):
    def __init__(self, parent):
        wx.TaskBarIcon.__init__(self)
        
        self.utility = parent.utility
        
        self.TBMENU_RESTORE = wx.NewId()

        # setup a taskbar icon, and catch some events from it
        self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, parent.onTaskBarActivate)
        self.Bind(wx.EVT_MENU, parent.onTaskBarActivate, id = self.TBMENU_RESTORE)
               
        self.updateIcon(False)
        
    def updateIcon(self,iconifying = False):
        remove = True
        
        mintray = self.utility.config.Read('mintray', "int")
        if (mintray >= 2) or ((mintray >= 1) and iconifying):
            remove = False
        
        if remove and self.IsIconInstalled():
            self.RemoveIcon()
        elif not remove and not self.IsIconInstalled():
            self.SetIcon(self.utility.icon, product_name)
        
    def CreatePopupMenu(self):        
        menu = wx.Menu()
        
        self.utility.actions[ACTION_STOPALL].addToMenu(menu, bindto = self)
        self.utility.actions[ACTION_UNSTOPALL].addToMenu(menu, bindto = self)
        menu.AppendSeparator()
        menu.Append(self.TBMENU_RESTORE, self.utility.lang.get('showabcwindow'))
        self.utility.actions[ACTION_EXIT].addToMenu(menu, bindto = self)
        return menu


##############################################################
#
# Class : ABColdFrame
#
# Main ABC Frame class that contains menu and menu bar management
# and contains ABCPanel
#
############################################################## 
class ABCOldFrame(wx.Frame,FlaglessDelayedInvocation):
    def __init__(self, ID, params, utility):
        self.utility = utility
        #self.utility.frame = self
        
        title = "Old Interface"
        # Get window size and position from config file
        size = (400,400)
        style = wx.DEFAULT_FRAME_STYLE | wx.CLIP_CHILDREN
        
        wx.Frame.__init__(self, None, ID, title, size = size, style = style)
        
        FlaglessDelayedInvocation.__init__(self)

        self.GUIupdate = True

        self.window = ABCPanel(self)
        self.Bind(wx.EVT_SET_FOCUS, self.onFocus)
            
    def onFocus(self, event = None):
        if event is not None:
            event.Skip()
        self.window.getSelectedList(event).SetFocus()


# Custom class loaded by XRC
class ABCFrame(wx.Frame, DelayedInvocation):
    def __init__(self, *args):
        if len(args) == 0:
            pre = wx.PreFrame()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Frame.__init__(self, args[0], args[1], args[2], args[3])
            self._PostInit()
        
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
        
        title = self.utility.lang.get('title') + \
                " " + \
                self.utility.lang.get('version')
        
        # Get window size and position from config file
        size, position = self.getWindowSettings()
        style = wx.DEFAULT_FRAME_STYLE | wx.CLIP_CHILDREN
        
        self.SetSize(size)
        self.SetPosition(position)
        self.SetTitle(title)
        #wx.Frame.__init__(self, None, ID, title, position, size, style = style)
        
        self.doneflag = Event()
        DelayedInvocation.__init__(self)

        self.tbicon = None

        # Arno: see ABCPanel
        self.abc_sb = ABCStatusBar(self,self.utility)
        self.SetStatusBar(self.abc_sb)
        
        try:
            self.SetIcon(self.utility.icon)
        except:
            pass

        # Don't update GUI as often when iconized
        self.GUIupdate = True

        # Start the scheduler before creating the ListCtrl
        self.utility.queue  = ABCScheduler(self.utility)
        #self.window = ABCPanel(self)
        #self.abc_sb = self.window.abc_sb
        
        
        self.oldframe = ABCOldFrame(-1, self.params, self.utility)
        self.oldframe.Refresh()
        self.oldframe.Layout()
        self.oldframe.Show(True)
        
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
        self.window.sb_buttons = ABCStatusButtons(self.abc_sb,self.utility)
        
        self.utility.window.postponedevents = []
        
        # Menu Options
        ############################
        menuBar = ABCMenuBar(self)
        if sys.platform == "darwin":
            wx.App.SetMacExitMenuItemId(wx.ID_CLOSE)
        self.SetMenuBar(menuBar)
        
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
            pass
        self.Bind(wx.EVT_ICONIZE, self.onIconify)
        self.Bind(wx.EVT_SET_FOCUS, self.onFocus)
        self.Bind(wx.EVT_SIZE, self.onSize)
        #self.Bind(wx.EVT_IDLE, self.onIdle)
        
        # Start up the controller
        self.utility.controller = ABCLaunchMany(self.utility)
        self.utility.controller.start()
        
        #if server start with params run it
        #####################################
        
        if DEBUG:
            print >>sys.stderr,"abc: wxFrame: params is",self.params
        
        if self.params[0] != "":
            success, msg, ABCTorrentTemp = self.utility.queue.addtorrents.AddTorrentFromFile(self.params[0],caller=CALLER_ARGV)

        self.utility.queue.postInitTasks(self.params)

        if self.params[0] != "":
            # Update torrent.list, but after having read the old list of torrents, otherwise we get interference
            ABCTorrentTemp.torrentconfig.writeSrc(False)
            self.utility.torrentconfig.Flush()

        self.videoFrame = None
        try:
            feasible = return_feasible_playback_modes()
            if PLAYBACKMODE_INTERNAL in feasible:
                # This means vlc is available
                from Tribler.Video.EmbeddedPlayer import VideoFrame
                self.videoFrame = VideoFrame(self)

                #self.videores = xrc.XmlResource("Tribler/vwxGUI/MyPlayer.xrc")
                #self.videoframe = self.videores.LoadFrame(None, "MyPlayer")
                #self.videoframe.Show()
                
                videoplayer = VideoPlayer.getInstance()
                videoplayer.set_parentwindow(self.videoFrame)
        except:
            print_exc()

        sys.stdout.write('GUI Complete.\n')

        self.Show(True)
        
        # Check to see if ABC is associated with torrents
        #######################################################
        if (sys.platform == 'win32'):
            if self.utility.config.Read('associate', "boolean"):
                if not self.utility.regchecker.testRegistry():
                    dialog = RegCheckDialog(self)
                    dialog.ShowModal()
                    dialog.Destroy()

        self.checkVersion()

        
    def checkVersion(self):
        t = Timer(2.0, self._checkVersion)
        t.start()
        
    def _checkVersion(self):
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
        except Exception,e:
            print >> sys.stderr, "Version check failed", ctime(time()), str(e)
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
        self.invokeLater(self.OnUpgrade)    
    
    def OnUpgrade(self, event=None):
        s = self.utility.lang.get('upgradeabc')
        title = self.utility.lang.get('upgradeabctitle')
        mainpage = self.utility.lang.get('mainpage')
        dlg = wx.MessageDialog(self, s,
                               title + self.curr_version,
                               wx.YES_NO|wx.ICON_EXCLAMATION
                               #wx.OK | wx.ICON_INFORMATION |
                               #wx.YES_NO | wx.NO_DEFAULT | wx.CANCEL | wx.ICON_INFORMATION
                               )
        result = dlg.ShowModal()
        dlg.Destroy()
        if result == wx.ID_YES:
            t = Timer(0.1, self.openBrowserForUpgrade)
            t.start()
            
    def openBrowserForUpgrade(self):
        webbrowser.open_new(self.update_url)
            
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
        self.invokeLater(self.onTaskBarActivate,[])


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
                print "abc: onIconify(",event.Iconized()
            else:
                print "abc: onIconify event None"
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
                print "abc: onSize:",event.GetSize()
            else:
                print "abc: onSize: None"
        self.setGUIupdate(True)
        if event is not None:
            #self.window.SetSize(self.GetSize())
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
            self.refreshNeeder = False
        
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
            position = wx.DefaultPosition
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
        
        # Don't do anything if the event gets called twice for some reason
        if self.utility.abcquitting:
            return

        # Check to see if we can veto the shutdown
        # (might not be able to in case of shutting down windows)
        if event is not None:
            try:
                if event.CanVeto() and self.utility.config.Read('confirmonclose', "boolean"):
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
        
        # Close the Torrent Maker
        self.utility.actions[ACTION_MAKETORRENT].closeWin()

        try:
            self.utility.webserver.stop()
        except:
            data = StringIO()
            print_exc(file = data)
            sys.stderr.write(data.getvalue())
            pass

        try:
            # tell scheduler to close all active thread
            self.utility.queue.clearScheduler()
        except:
            data = StringIO()
            print_exc(file = data)
            sys.stderr.write(data.getvalue())
            pass

        try:
            # Restore the window before saving size and position
            # (Otherwise we'll get the size of the taskbar button and a negative position)
            self.onTaskBarActivate()
            self.saveWindowSettings()
        except:
            #print_exc(file=sys.stderr)
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

        self.oldframe.Destroy()

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

        # Arno: at the moment, Tribler gets a segmentation fault when the
        # tray icon is always enabled. This SEGV occurs in the wx mainloop
        # which is entered as soon as we leave this method. Hence I placed
        # tribler_done() here, so the database are closed properly
        # before the crash.
        #
        # Arno, 2007-02-28: Preferably this should be moved to the main 
        # run() method below, that waits a while to allow threads to finish.
        # Ideally, the database should still be open while they finish up.
        # Because of the crash problem with the icontray this is the safer
        # place.
        # 
        # TODO: Check if icon-tray problem is Linux only
        if sys.platform == 'linux2':
            tribler_done(self.utility.getConfigPath())            
        
        if DEBUG:    
            print >>sys.stderr,"abc: OnCloseWindow END"


    def onWarning(self,exc):
        msg = self.utility.lang.get('tribler_startup_nonfatalerror')
        msg += str(exc.__class__)+':'+str(exc)
        dlg = wx.MessageDialog(None, msg, self.utility.lang.get('tribler_warning'), wx.OK|wx.ICON_WARNING)
        result = dlg.ShowModal()
        dlg.Destroy()

    def onUPnPError(self,upnp_type,listenport,error_type,exc=None):

        if error_type == 0:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' ')+self.utility.lang.get('tribler_upnp_error1')
        elif error_type == 1:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' ')+self.utility.lang.get('tribler_upnp_error2')+unicode(str(exc))+self.utility.lang.get('tribler_upnp_error2_postfix')
        elif error_type == 2:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' ')+self.utility.lang.get('tribler_upnp_error3')
        else:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' Unknown error')

        msg = self.utility.lang.get('tribler_upnp_error_intro')
        msg += str(listenport)
        msg += self.utility.lang.get('tribler_upnp_error_intro_postfix')
        msg += errormsg
        msg += self.utility.lang.get('tribler_upnp_error_extro') 

        dlg = wx.MessageDialog(None, msg, self.utility.lang.get('tribler_warning'), wx.OK|wx.ICON_WARNING)
        result = dlg.ShowModal()
        dlg.Destroy()

    def onReachable(self,event=None):
        """ Called by GUI thread """
        self.window.sb_buttons.setReachable(True)
        GUIUtility.getInstance().isReachable = True


##############################################################
#
# Class : ABCApp
#
# Main ABC application class that contains ABCFrame Object
#
##############################################################
class ABCApp(wx.App,FlaglessDelayedInvocation):
    def __init__(self, x, params, single_instance_checker, abcpath):
        self.params = params
        self.single_instance_checker = single_instance_checker
        self.abcpath = abcpath
        wx.App.__init__(self, x)
        
    def OnInit(self):
        try:
            self.utility = Utility(self.abcpath)
            # Set locale to determine localisation
            locale.setlocale(locale.LC_ALL, '')

            sys.stdout.write('Client Starting Up.\n')
            sys.stdout.write('Build: ' + self.utility.lang.get('build') + '\n')

            tribler_init(self.utility.getConfigPath(),self.utility.getPath(),self.db_exception_handler)
            self.utility.setTriblerVariables()
            self.utility.postAppInit()
            
            # Singleton for executing tasks that are too long for GUI thread and
            # network thread
            self.guiserver = GUIServer.getInstance()
            self.guiserver.register()
    
            # Singleton for management of user's mugshots (i.e. icons/display pictures)
            self.mm = MugshotManager.getInstance()
            self.mm.register(self.utility.getConfigPath(),self.utility.getPath())

            # H4x0r a bit
            set_tasteheart_bitmaps(self.utility.getPath())
            set_perfBar_bitmaps(self.utility.getPath())
    
            # Put it here so an error is shown in the startup-error popup
            self.serverlistener = ServerListener(self.utility)
            
            # Check webservice for autostart webservice
            #######################################################
            WebListener(self.utility)
            if self.utility.webconfig.Read("webautostart", "boolean"):
                self.utility.webserver.start()
                
            # Start single instance server listenner
            ############################################
            self.serverthread   = Thread(target = self.serverlistener.start)
            self.serverthread.setDaemon(False)
            self.serverthread.start()
    
            self.videoplayer = VideoPlayer.getInstance()
            self.videoplayer.register(self.utility)
            self.videoserver = VideoHTTPServer.getInstance()
            self.videoserver.background_serve()
    
            #self.frame = ABCFrame(-1, self.params, self.utility)
            self.guiUtility = GUIUtility.getInstance(self.utility, self.params)
            updateXRC.main(['Tribler/vwxGUI/'])
            self.res = xrc.XmlResource("Tribler/vwxGUI/MyFrame.xrc")
            self.guiUtility.xrcResource = self.res
            self.frame = self.res.LoadFrame(None, "MyFrame")
            self.guiUtility.frame = self.frame
            self.scrollWindow = xrc.XRCCTRL(self.frame, "level0")
            self.guiUtility.mainSizer = self.scrollWindow.GetSizer()
            self.frame.topBackgroundRight = xrc.XRCCTRL(self.frame, "topBG3")
            self.scrollWindow.SetScrollbars(1,1,1024,768)
            self.frame.mainButtonPersons = xrc.XRCCTRL(self.frame, "mainButtonPersons")
            
            
            self.frame.Refresh()
            self.frame.Layout()
            self.frame.Show(True)
            # GUI start
            # - load myFrame 
            # - load standardGrid
            # - gui utility > button mainButtonFiles = clicked
        

            self.Bind(wx.EVT_QUERY_END_SESSION, self.frame.OnCloseWindow)
            self.Bind(wx.EVT_END_SESSION, self.frame.OnCloseWindow)
        except Exception,e:
            print "THREAD",currentThread().getName()
            print_exc(file=sys.stderr)
            self.error = e
            self.onError()
            return False

        return True

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
        if not ALLOW_MULTIPLE:
            del self.single_instance_checker
        ClientPassParam("Close Connection")
        return 0
    
    def db_exception_handler(self,e):
        if DEBUG:
            print "abc: Database Exception handler called"
        self.error = e
        self.invokeLater(self.onError,[],{'source':"The database layer reported: "})
    
    def getConfigPath(self):
        return self.utility.getConfigPath()
    
        
class DummySingleInstanceChecker:
    
    def __init__(self,basename):
        pass

    def IsAnotherRunning(self):
        return False
        
        
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
    # TEMPORARILY DISABLED on Linux
    if sys.platform != 'linux2':
        single_instance_checker = wx.SingleInstanceChecker("tribler-" + wx.GetUserId())
    else:
        single_instance_checker = DummySingleInstanceChecker("tribler-")

    if not ALLOW_MULTIPLE and single_instance_checker.IsAnotherRunning():
        #Send  torrent info to abc single instance
        ClientPassParam(params[0])
    else:
        abcpath = os.path.abspath(os.path.dirname(sys.argv[0]))
        # Arno: don't chdir to allow testing as other user from other dir.
        #os.chdir(abcpath)

        # Launch first abc single instance
        app = ABCApp(0, params, single_instance_checker, abcpath)
        configpath = app.getConfigPath()
        app.MainLoop()

        print "Client shutting down. Sleeping for a few seconds to allow other threads to finish"
        sleep(4)

        # This is the right place to close the database, unfortunately Linux has
        # a problem, see ABCFrame.OnCloseWindow
        #
        if sys.platform != 'linux2':
            tribler_done(configpath)
        #os._exit(0)

if __name__ == '__main__':
    run()

