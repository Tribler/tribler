#!/usr/bin/python

#########################################################################
#
# Author : Choopan RATTANAPOKA
#
# Description : Main ABC [Yet Another Bittorrent Client] python script.
#               you can run from source code by using
#               >python abc.py
#               need Python, WxPython in order to run from source code.
#########################################################################
import sys, locale
import os
import wx
#import hotshot

from threading import Thread

from traceback import print_exc, print_stack
from cStringIO import StringIO
import urllib

from interconn import ServerListener, ClientPassParam
from launchmanycore import ABCLaunchMany

from ABC.Toolbars.toolbars import ABCBottomBar2, ABCStatusBar, ABCMenuBar, ABCToolBar
from ABC.GUI.menu import ABCMenu
from ABC.Scheduler.scheduler import ABCScheduler

from webservice import WebListener

if (sys.platform == 'win32'):
    from Dialogs.regdialog import RegCheckDialog

from ABC.GUI.list import ManagedList
from Utility.utility import Utility
from Utility.constants import * #IGNORE:W0611

from Tribler.__init__ import tribler_init, tribler_done

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
        self.reversesort = False

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
            self.reversesort = not self.reversesort
        else:
            self.reversesort = False
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
        self.utility.actions[ACTION_DETAILS].action()


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

        # List Control Display UI
        ###############################
        self.list = ABCList(self)
        self.utility.list = self.list

        colSizer.Add(self.list, 1, wx.EXPAND|wx.ALL, 2)

        self.utility.bottomline2 = ABCBottomBar2(self)

        colSizer.Add(self.utility.bottomline2, 0, wx.ALL|wx.EXPAND, 3)
        
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
               
        self.updateIcon()
        
    def updateIcon(self):
        remove = True
        
        mintray = self.utility.config.Read('mintray', "int")
        if (mintray >= 2) or ((mintray >= 1) and self.utility.frame.IsIconized()):
            remove = False
        
        if remove and self.IsIconInstalled():
            self.RemoveIcon()
        elif not remove and not self.IsIconInstalled():
            self.SetIcon(self.utility.icon, "ABC")
        
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
# Class : ABCFrame
#
# Main ABC Frame class that contains menu and menu bar management
# and contains ABCPanel
#
############################################################## 
class ABCFrame(wx.Frame):
    def __init__(self, ID, params, utility):
        self.utility = utility
        self.utility.frame = self
        
        title = self.utility.lang.get('title') + \
                " " + \
                self.utility.lang.get('version')
        
        # Get window size and position from config file
        size, position = self.getWindowSettings()
        style = wx.DEFAULT_FRAME_STYLE | wx.CLIP_CHILDREN
        wx.Frame.__init__(self, None, ID, title, position, size, style = style)
        
        self.tbicon = None

        self.abc_sb = ABCStatusBar(self)
        self.SetStatusBar(self.abc_sb)

        try:
            self.SetIcon(self.utility.icon)
        except:
            pass

        # Don't update GUI as often when iconized
        self.GUIupdate = True

        # Start the scheduler before creating the ListCtrl
        self.utility.queue  = ABCScheduler(self.utility)
        
        self.window = ABCPanel(self)
        
        # Menu Options
        ############################
        menuBar = ABCMenuBar(self)
        self.SetMenuBar(menuBar)
        
        self.tb = ABCToolBar(self)
        self.SetToolBar(self.tb)
        
        self.buddyFrame = None
        self.fileFrame = None
        
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
        
        # Check webservice for autostart webservice
        #######################################################
        WebListener(self.utility)
        if self.utility.webconfig.Read("webautostart", "boolean"):
            self.utility.webserver.start()
            
        # Start up the controller
        self.utility.controller = ABCLaunchMany(self.utility)
        #self.utility.controller.start() # done by ABCLaunchMany parent
        
        self.utility.queue.postInitTasks()

        # Start single instance server listenner
        ############################################
        self.serverlistener = ServerListener(self.utility)
        self.serverthread   = Thread(target = self.serverlistener.start)
        self.serverthread.setDaemon(False)
        self.serverthread.start()

        #if server start with params run it
        #####################################
        if params[0] != "":
            ClientPassParam(params[0])

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
        #TODO: check version
        
    def checkVersion(self):
        my_version = self.utility.getVersion()
        try:
            curr_status = urllib.urlopen('http://tribler.org/version').read()
            _curr_status = curr_status.split()
            curr_version = float(_curr_status[0])
            if curr_version > my_version:
                print >> sys.stderr, "Your software is outdated.  Would you like to upgrade Tribler?", curr_version, my_version
                self.OnUpgrade()
        except:
            print >> sys.stderr, "check version failed"
            print_exc()
            
    def OnUpgrade(self, event=None):
        str = "Your software is outdated.\nWould you like to upgrade Tribler?"
        dlg = wx.MessageDialog(self, str,
                               'Click and Download',
                               wx.YES_NO|wx.ICON_EXCLAMATION
                               #wx.OK | wx.ICON_INFORMATION |
                               #wx.YES_NO | wx.NO_DEFAULT | wx.CANCEL | wx.ICON_INFORMATION
                               )
        result = dlg.ShowModal()
        dlg.Destroy()
        if(result == wx.ID_YES):
            import wx.lib.hyperlink as hl
            self._hyper = hl.HyperLinkCtrl(self, wx.ID_ANY, "Tribler Main Page",
                                        URL="http://tribler.org/")
            self._hyper.GotoURL("http://tribler.org/",True, True)
            
    def onFocus(self, event = None):
        if event is not None:
            event.Skip()
        self.window.getSelectedList(event).SetFocus()
        
    def setGUIupdate(self, update):
        oldval = self.GUIupdate
        self.GUIupdate = update
        
        if self.GUIupdate and not oldval:
            # Force an update of all torrents
            for torrent in self.utility.torrents["all"]:
                torrent.updateColumns()
                torrent.updateColor()

    #######################################
    # minimize to tray bar control
    #######################################
    def onTaskBarActivate(self, event = None):
        self.Iconize(False)
        self.Show(True)
        self.Raise()
        
        if self.tbicon is not None:
            self.tbicon.updateIcon()

        self.window.list.SetFocus()

        # Resume updating GUI
        self.setGUIupdate(True)

    def onIconify(self, event = None):
        if (self.utility.config.Read('mintray', "int") > 0
            and self.tbicon is not None):
            self.tbicon.updateIcon()
            self.Show(False)
        
        if event is not None:
            event.Skip()

        # Don't update GUI while minimized
        self.setGUIupdate(not self.GUIupdate)
        
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
            data = StringIO()
            print_exc(file = data)
            sys.stderr.write(data.getvalue())
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
            
        try:
            if self.buddyFrame is not None:
                self.buddyFrame.Destroy()
            if self.fileFrame is not None:
                self.fileFrame.Destroy()
        except:
            pass


##############################################################
#
# Class : ABCApp
#
# Main ABC application class that contains ABCFrame Object
#
##############################################################
class ABCApp(wx.App):
    def __init__(self, x, params, single_instance_checker, abcpath):
        self.params = params
        self.single_instance_checker = single_instance_checker

        self.utility = Utility(abcpath)
        tribler_init(self.utility.getConfigPath())
        self.utility.setTriblerVariables()
        
        # Set locale to determine localisation
        locale.setlocale(locale.LC_ALL, '')

        sys.stdout.write('Client Starting Up.\n')
        sys.stdout.write('Build: ' + self.utility.lang.get('build') + '\n')

        wx.App.__init__(self, x)
        
    def OnInit(self):
        self.utility.postAppInit()
        self.frame = ABCFrame(-1, self.params, self.utility)

        self.Bind(wx.EVT_QUERY_END_SESSION, self.frame.OnCloseWindow)
        self.Bind(wx.EVT_END_SESSION, self.frame.OnCloseWindow)
        
        return True

    def OnExit(self):
        del self.single_instance_checker
        ClientPassParam("Close Connection")
        
        return 0
        
    def __del__(self):
        tribler_done(self.utility.getConfigPath())
        
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
    single_instance_checker = wx.SingleInstanceChecker("pingpong-abc" + wx.GetUserId())

    if single_instance_checker.IsAnotherRunning():
        #Send  torrent info to abc single instance
        ClientPassParam(params[0])
    else:
        abcpath = os.path.abspath(os.path.dirname(sys.argv[0]))
        # Arno: don't chdir to allow testing as other user from other dir.
        #os.chdir(abcpath)

        # Launch first abc single instance
        app = ABCApp(0, params, single_instance_checker, abcpath)
        app.MainLoop()

        
if __name__ == '__main__':
    run()

