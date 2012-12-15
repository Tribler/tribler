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
import traceback

from wx.html import HtmlWindow

from Tribler.Main.vwxGUI.TopSearchPanel import TopSearchPanel,\
    TopSearchPanelStub
from Tribler.Main.vwxGUI.home import Home, Stats
from Tribler.Main.vwxGUI.list import SearchList, ChannelList,\
    LibraryList, ActivitiesList
from Tribler.Main.vwxGUI.channel import SelectedChannelList, Playlist,\
    ManageChannel


from Tribler.Main.Dialogs.FeedbackWindow import FeedbackWindow
from Tribler.Main.vwxGUI import DEFAULT_BACKGROUND, SEPARATOR_GREY, forceAndReturnWxThread
from Tribler.Main.Utility.GuiDBHandler import startWorker

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
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.Dialogs.systray import ABCTaskBarIcon
from Tribler.Main.Dialogs.SaveAs import SaveAs
from Tribler.Main.Dialogs.ThreadSafeProgressDialog import ThreadSafeProgressDialog
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
        destdir = None
        for filename in filenames:
            if not filename.endswith(".torrent"):
                #lets see if we can find a .torrent in this directory
                head, _ = os.path.split(filename)
                files = os.listdir(head)
                
                found = False
                for file in files:
                    if file.endswith(".torrent"): #this is the .torrent, use head as destdir to start seeding
                        filename = os.path.join(head, file)
                        destdir = head
                        
                        found = True        
                        break
                
                if not found:
                    dlg = wx.FileDialog(None, "Tribler needs a .torrent file to start seeding, please select the associated .torrent file.", wildcard = "torrent (*.torrent)|*.torrent", style = wx.FD_OPEN)
                    if dlg.ShowModal() == wx.ID_OK:
                        filename = dlg.GetPath()
                        
                        destdir = head
                        found = True
                    dlg.Destroy()
                if not found:
                    break
            try:
                self.frame.startDownload(filename, destdir = destdir, fixtorrent = True)
            except IOError:
                dlg = wx.MessageDialog(None,
                           self.frame.utility.lang.get("filenotfound"),
                           self.frame.utility.lang.get("tribler_warning"),
                           wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
        return True

class MainFrame(wx.Frame):
    def __init__(self, parent, channelonly, internalvideo, progress):
        # Do all init here
        self.ready = False
        self.guiUtility = GUIUtility.getInstance()
        self.guiUtility.frame = self
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
        
        # Get window size and (sash) position from config file
        size, position, sashpos = self.getWindowSettings()
        style = wx.DEFAULT_DIALOG_STYLE|wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.NO_FULL_REPAINT_ON_RESIZE|wx.CLIP_CHILDREN
            
        wx.Frame.__init__(self, parent, wx.ID_ANY, title, position, size, style)
        if sys.platform == 'linux2':
            font = self.GetFont()
            if font.GetPointSize() > 9:
                font.SetPointSize(9)
                self.SetFont(font)
                
        self.Freeze()
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour(DEFAULT_BACKGROUND)
         
        themeColour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
        r, g, b = themeColour.Get(False)
        if r > 190 or g > 190 or b > 190: #Grey == 190,190,190
            self.SetForegroundColour(wx.BLACK)

        if internalvideo:
            self.videoparentpanel = wx.Panel(self)
            self.videoparentpanel.Hide()
        else:
            self.videoparentpanel = None
            
        #Create all components        
        progress('Creating panels')
        if not channelonly:
            self.actlist = ActivitiesList(self)
            self.top_bg = TopSearchPanel(self)
            self.home = Home(self)

            self.splitter = wx.SplitterWindow(self, style=wx.SP_NOBORDER)
            self.splitter.SetMinimumPaneSize(1)
            self.splitter.SetForegroundColour(self.GetForegroundColour())
            self.splitter_top_window = wx.Panel(self.splitter, style=wx.NO_BORDER)
            self.splitter_top_window.SetForegroundColour(self.GetForegroundColour())
            self.splitter_top = wx.BoxSizer(wx.HORIZONTAL)
            self.splitter_top_window.SetSizer(self.splitter_top)
            self.splitter_bottom_window = wx.Panel(self.splitter)
            self.splitter_bottom_window.SetMinSize((-1,25))
            self.splitter_bottom_window.SetForegroundColour(self.GetForegroundColour())
            self.splitter_bottom_window.OnChange = lambda: self.splitter_bottom.Layout()
            self.splitter_bottom_window.parent_list = self.splitter_bottom_window
            self.splitter_bottom = wx.BoxSizer(wx.HORIZONTAL)
            self.splitter_bottom_window.SetSizer(self.splitter_bottom)
            self.splitter.SetSashGravity(0.8)
            self.splitter.SplitHorizontally(self.splitter_top_window, self.splitter_bottom_window, sashpos)
            self.splitter.Show(False)
            # Reset the sash position after the splitter has been made visible
            def OnShowSplitter(event):
                wx.CallAfter(self.splitter.SetSashPosition, sashpos)
                self.splitter.Unbind(wx.EVT_SHOW)
                event.Skip()
            self.splitter.Bind(wx.EVT_SHOW, OnShowSplitter)

            self.searchlist = SearchList(self.splitter_top_window)
            self.searchlist.Show(False)
            self.librarylist = LibraryList(self.splitter_top_window)
            self.librarylist.Show(False)
            self.channellist = ChannelList(self.splitter_top_window)
            self.channellist.Show(False)
            self.selectedchannellist = SelectedChannelList(self.splitter_top_window)
            self.selectedchannellist.Show(False)
            self.playlist = Playlist(self.splitter_top_window)
            self.playlist.Show(False)
        else:
            self.actlist = None
            self.top_bg = None
            
            self.guiUtility.guiPage = 'selectedchannel'
            self.home = None
            self.searchlist = None
            self.librarylist = LibraryList(self)
            self.librarylist.Show(False)
            self.channellist = None
            self.selectedchannellist = SelectedChannelList(self)
            self.selectedchannellist.Show(True)
            self.playlist = Playlist(self)
            self.playlist.Show(False)
        
        self.stats = Stats(self)
        self.stats.Show(False)
        self.managechannel = ManageChannel(self)
        self.managechannel.Show(False)
        
        progress('Positioning')
        
        if not channelonly:
            #position all elements            
            vSizer = wx.BoxSizer(wx.VERTICAL)
            
            vSizer.Add(self.top_bg, 0, wx.EXPAND)
            
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            vSizer.Add(hSizer, 1, wx.EXPAND)
            
            hSizer.Add(self.actlist, 0, wx.EXPAND)
            separator = wx.Panel(self, size=(1,-1))
            separator.SetBackgroundColour(SEPARATOR_GREY)
            hSizer.Add(separator, 0, wx.EXPAND)
            hSizer.Add(self.home, 1, wx.EXPAND)
            hSizer.Add(self.stats, 1, wx.EXPAND)
            hSizer.Add(self.splitter, 1, wx.EXPAND)
        else:
            vSizer = wx.BoxSizer(wx.VERTICAL) 
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            vSizer.Add(hSizer, 1, wx.EXPAND|wx.ALL, 5)
            
            self.top_bg = TopSearchPanelStub()
            
        hSizer.Add(self.managechannel, 1, wx.EXPAND)
        
        if self.videoparentpanel:
            hSizer.Add(self.videoparentpanel, 1, wx.EXPAND)
        
        self.SetSizer(vSizer)
        
        #set sizes
        if not channelonly:
            self.top_bg.SetMinSize((-1,45))
            self.actlist.SetMinSize((180,-1))
        
        self.SRstatusbar = SRstatusbar(self)
        self.SetStatusBar(self.SRstatusbar)
        
        def preload_data():
            if not channelonly:
                self.guiUtility.showChannelCategory('All', False)
            self.guiUtility.showLibrary(False)
        startWorker(None, preload_data, delay = 1.5, workerType = "guiTaskQueue")
        
        if channelonly:
            self.guiUtility.showChannelFromDispCid(channelonly)
            if not self.guiUtility.useExternalVideo:
                self.guiUtility.ShowPlayer()

        if sys.platform != 'darwin':
            dragdroplist = FileDropTarget(self)
            self.SetDropTarget(dragdroplist)
        try:
            self.SetIcon(self.utility.icon)
        except:
            pass
        
        self.tbicon = None        
        try:
            self.tbicon = ABCTaskBarIcon(self)
        except:
            print_exc()

        # Don't update GUI as often when iconized
        self.GUIupdate = True
        self.window = self.GetChildren()[0]
        self.window.utility = self.utility

        progress('Binding events')        
        # Menu Events 
        ############################
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

        # leaving here for the time being:
        # wxMSW apparently sends the event to the App object rather than
        # the top-level Frame, but there seemed to be some possibility of
        # change
        self.Bind(wx.EVT_QUERY_END_SESSION, self.OnCloseWindow)
        self.Bind(wx.EVT_END_SESSION, self.OnCloseWindow)
        self.Bind(wx.EVT_ICONIZE, self.onIconify)
        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_MAXIMIZE, self.onSize)
        
        findId = wx.NewId()
        quitId = wx.NewId()
        nextId = wx.NewId()
        prevId = wx.NewId()
        dispId = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnFind, id = findId)
        self.Bind(wx.EVT_MENU, lambda event: self.Close(), id = quitId)
        self.Bind(wx.EVT_MENU, self.OnNext, id = nextId)
        self.Bind(wx.EVT_MENU, self.OnPrev, id = prevId)
        self.Bind(wx.EVT_MENU, lambda evt: self.guiUtility.ShowPage('stats'), id = dispId)
        

        accelerators = [(wx.ACCEL_CTRL, ord('f'), findId)]
        accelerators.append((wx.ACCEL_CTRL, ord('d'), dispId))
        accelerators.append((wx.ACCEL_CTRL, wx.WXK_TAB, nextId))
        accelerators.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, wx.WXK_TAB, prevId))
        
        if sys.platform == 'linux2':
            accelerators.append((wx.ACCEL_CTRL, ord('q'), quitId))
            accelerators.append((wx.ACCEL_CTRL, ord('/'), findId))
        self.SetAcceleratorTable(wx.AcceleratorTable(accelerators))
        
        # Init video player
        sys.stdout.write('GUI Complete.\n')
        self.Thaw()
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
        
        
        def post():
            self.checkVersion()
            self.startCMDLineTorrent()

        # If the user passed a torrentfile on the cmdline, load it.
        wx.CallAfter(post)
        
        # ProxyService 90s Test_
#        from Tribler.Core.Session import Session
#        session = Session.get_instance()
#        session.uch.notify(NTFY_GUI_STARTED, NTFY_INSERT, None, None)
        # _ProxyService 90s Test
        
    def startCMDLineTorrent(self):
        if self.params[0] != "" and not self.params[0].startswith("--"):
            vod = False
            url_filename = self.params[0]
            selectedFiles = [self.params[1]] if len(self.params) == 2 else []
            if selectedFiles:
                _, ext = os.path.splitext(selectedFiles[0])
                if ext != '' and ext[0] == '.':
                    ext = ext[1:]
                if ext.lower() in videoextdefaults:
                    vod = True
            
            if url_filename.startswith("magnet:"):
                self.startDownloadFromMagnet(self.params[0], cmdline=True, selectedFiles = selectedFiles, vodmode = vod)
            elif url_filename.startswith("http"):
                self.startDownloadFromUrl(self.params[0], cmdline=True, selectedFiles = selectedFiles, vodmode = vod)
            else:
                self.startDownload(url_filename, cmdline=True, selectedFiles = selectedFiles, vodmode = vod)

    def startDownloadFromMagnet(self, url, destdir = None, cmdline=False, selectedFiles = [], vodmode = False):
        def torrentdef_retrieved(tdef):
            print >> sys.stderr, "Retrieved metadata for:", tdef.get_name()
            wx.CallAfter(self.startDownload, cdef = tdef, cmdline=cmdline, destdir = destdir, selectedFiles = selectedFiles, vodmode = vodmode)
                
        if not TorrentDef.retrieve_from_magnet(url, torrentdef_retrieved):
            print >> sys.stderr, "MainFrame.startDownloadFromMagnet() Can not use url to retrieve torrent"
            self.guiUtility.Notify("Download from magnet failed", icon = wx.ART_WARNING)
            return False
        
        print >> sys.stderr, "Trying to retrieve metadata for:", url
        return True
    
    def startDownloadFromSwift(self, url, destdir = None):
        cdef = SwiftDef.load_from_url(url)
        cdef.set_name("Unnamed video - "+time.strftime("%d-%m-%Y at %H:%M", time.localtime()))
        wx.CallAfter(self.startDownload, cdef = cdef, destdir = destdir)
        return True
    
    def startDownloadFromUrl(self, url, destdir = None, cmdline=False, selectedFiles = [], vodmode = False):
        try:
            tdef = TorrentDef.load_from_url(url)
            if tdef:
                wx.CallAfter(self.startDownload, cdef=tdef, cmdline=cmdline, destdir = destdir, selectedFiles = selectedFiles, vodmode = vodmode)
                return True
        except:
            print_exc()
        self.guiUtility.Notify("Download from url failed", icon = wx.ART_WARNING)
        return False

    def startDownload(self,torrentfilename=None,destdir=None,cdef=None,cmdline=False,clicklog=None,name=None,vodmode=False,doemode=None,fixtorrent=False,selectedFiles=None,correctedFilename=None,hidden=False):
        if True or DEBUG:
            print >>sys.stderr,"mainframe: startDownload:",torrentfilename, destdir,cdef,vodmode,selectedFiles
        
        if fixtorrent and torrentfilename:
            self.fixTorrent(torrentfilename)
            
        #Niels: if you call startdownload with both a Swift cdef and a torrentfilename, we allow Swift to download the file in the first X seconds
        if cdef and cdef.get_def_type() == 'swift' and torrentfilename:
            monitorSwiftProgress = True
        else:
            monitorSwiftProgress = False
            
        try:
            if cdef is None:
                cdef = tdef = TorrentDef.load(torrentfilename)
            elif cdef.get_def_type() == 'torrent':
                tdef = cdef
            elif torrentfilename:
                tdef = TorrentDef.load(torrentfilename)
            else:
                tdef = None
                
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()
            
            cancelDownload = False
            useDefault = not dscfg.get_show_saveas()
            if not useDefault and not destdir:
                defaultname = correctedFilename
                if not correctedFilename and tdef and tdef.is_multifile_torrent():
                    defaultname = tdef.get_name_as_unicode()
                
                if wx.Thread_IsMain():
                    dlg = SaveAs(self, tdef, dscfg.get_dest_dir(), defaultname, os.path.join(self.utility.session.get_state_dir(), 'recent_download_history'), selectedFiles)
                    dlg.CenterOnParent()
                    
                    if dlg.ShowModal() == wx.ID_OK:
                        #for multifile we enabled correctedFilenames, use split to remove the filename from the path
                        if tdef and tdef.is_multifile_torrent():
                            destdir, correctedFilename = os.path.split(dlg.GetPath())
                            selectedFiles = dlg.GetSelectedFiles()
                        else:
                            destdir = dlg.GetPath()
                    else:
                        cancelDownload = True
                    dlg.Destroy()
                else:
                    raise Exception("cannot create dialog, not on wx thread")
                    
            if not cancelDownload:
                if destdir is not None:
                    dscfg.set_dest_dir(destdir)
                    
                if correctedFilename:
                    dscfg.set_corrected_filename(correctedFilename)
                
                if selectedFiles and len(selectedFiles) == 1:
                    #we should filter files to see if they are all playable
                    videofiles = selectedFiles
                    
                elif tdef and not selectedFiles:
                    videofiles = tdef.get_files(exts=videoextdefaults)
                    
                else:
                    videofiles = []
                
                #disable vodmode if no videofiles
                if vodmode and len(videofiles) == 0:
                    vodmode = False
                
                vodmode = vodmode or cdef.get_live()
                
                selectedFile = None
                if vodmode:
                    print >>sys.stderr, 'MainFrame: startDownload: Starting in VOD mode'
                    if len(videofiles) == 1:
                        selectedFile = videofiles[0]
                    else:
                        selectedFile = None
                    
                    #Swift requires swarmname to be part of the selectedfile
                    if cdef.get_def_type() == 'swift' and tdef:
                        swift_selectedFile = tdef.get_name_as_unicode()+"/"+selectedFile
                    else:
                        swift_selectedFile = selectedFile
                    
                    videoplayer = VideoPlayer.getInstance()
                    result = videoplayer.start_and_play(cdef, dscfg, swift_selectedFile)
                    
                else:
                    if selectedFiles:
                        if cdef.get_def_type() == 'swift' and tdef:
                            swift_selectedFiles = []
                            for selectedFile in selectedFiles:
                                swift_selectedFiles.append(tdef.get_name_as_unicode()+"/"+selectedFile)
                            dscfg.set_selected_files(swift_selectedFiles)
                            
                        else:
                            dscfg.set_selected_files(selectedFiles)
                    
                    print >>sys.stderr, 'MainFrame: startDownload: Starting in DL mode'
                    result = self.utility.session.start_download(cdef, dscfg, hidden=hidden)
                
                if result and not hidden:
                    dlname = ''
                    if tdef:
                        dlname = tdef.get_name_as_unicode()
                    elif cdef: 
                        dlname = cdef.get_name()
                    self.show_saved(dlname)
                    
                    if monitorSwiftProgress:
                        state_lambda = lambda ds, vodmode=vodmode, torrentfilename=torrentfilename, dscfg=dscfg, selectedFile=selectedFile: self.monitorSwiftProgress(ds, vodmode, torrentfilename, dscfg, selectedFile)
                        result.set_state_callback(state_lambda, getpeerlist=False, delay=15.0)

                if clicklog is not None:
                    mypref = self.utility.session.open_dbhandler(NTFY_MYPREFERENCES)
                    startWorker(None, mypref.addClicklogToMyPreference, wargs= (cdef.get_id(), clicklog))

                return result  

        except DuplicateDownloadException,e:
            # If there is something on the cmdline, all other torrents start
            # in STOPPED state. Restart
            if cmdline and cdef.get_def_type() == 'torrent':
                dlist = self.utility.session.get_downloads()
                for d in dlist:
                    if d.get_def().get_infohash() == cdef.get_infohash():
                        d.restart()
                        break
            
            if wx.Thread_IsMain():
                # show nice warning dialog
                dlg = wx.MessageDialog(None,
                                       self.utility.lang.get('duplicate_download_msg'),
                                       self.utility.lang.get('duplicate_download_title'),
                                       wx.OK|wx.ICON_ERROR)
                result = dlg.ShowModal()
                dlg.Destroy()
                
            else:
                print_exc()
                self.onWarning(e)
            
        except Exception,e:
            print_exc()
            self.onWarning(e)
            
        return None
    
    def startReseedSwiftDownload(self, tdef, storagepath, sdef):
        # Arno, 2012-05-07:
        print >>sys.stderr,"main: frame: startReseedSwift",tdef, storagepath, sdef
        
        # 1. Tell library_manager that we have a 'swift_hash' for this infohash
        self.guiUtility.library_manager.updateTorrent(tdef.get_infohash(), sdef.get_roothash())
        
        # 2. Start swift download reseeding BitTorrent content
        self.startDownload(destdir=storagepath,cdef=sdef,hidden=True)
                
        # 3. Checkpoint Session
        self.utility.session.checkpoint()
    
    def modifySelection(self, download, selectedFiles):
        tdef = download.get_def()
        dscfg = DownloadStartupConfig(download.dlconfig)
        try:
            dscfg.set_selected_files(selectedFiles)
            
        except ValueError:
            #upon valueerror, change downloadmode to normal, retry
            dscfg.set_mode(DLMODE_NORMAL)
            dscfg.set_selected_files(selectedFiles)
        
        self.guiUtility.library_manager.deleteTorrentDownload(download, None, removestate = False)
        self.utility.session.start_download(tdef, dscfg)
    
    def fixTorrent(self, filename):
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
                return False
        
        return True
    
    def monitorSwiftProgress(self, ds, vodmode, torrentfilename, dscfg, selectedFile):
        if ds.get_progress() == 0:
            if ds.get_status() == DLSTATUS_ALLOCATING_DISKSPACE:
                return (5.0, True)
            
            download = ds.get_download()
            self.utility.session.remove_download(download)
            
            #pause for swift file release
            time.sleep(1)
            
            print >> sys.stderr, "Switching to Bittorrent"
            cdef = TorrentDef.load(torrentfilename)
            if vodmode:
                videoplayer = VideoPlayer.getInstance()
                wx.CallAfter(videoplayer.start_and_play, cdef, dscfg, selectedFile)
            else:
                self.utility.session.start_download(cdef, dscfg)
        return (0, False)
                
    @forceWxThread
    def show_saved(self, torrentname):
        if self.ready and self.librarylist.isReady:
            self.guiUtility.Notify("Download started", "Torrent '%s' has been added to the download queue." % torrentname, icon = wx.ART_INFORMATION)
            
            print >> sys.stderr, "Allowing refresh in 3 seconds", long(time.time() + 3)
            self.librarylist.GetManager().prev_refresh_if = time.time() - 27
            
    def checkVersion(self):
        self.guiserver.add_task(self._checkVersion, 5.0)

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
                # upgrade on this separate thread
                if len(info) > 0:
                    self._upgradeVersion(my_version, self.curr_version, info)
                else:
                    self._manualUpgrade(my_version, self.curr_version, self.update_url)
            
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
    
    @forceWxThread
    def _manualUpgrade(self, my_version, latest_version, url):
        dialog = wx.MessageDialog(self, 'There is a new version of Tribler.\nYour version:\t\t\t\t%s\nLatest version:\t\t\t%s\n\nPlease visit %s to upgrade.'%(my_version, latest_version, url), 'New version of Tribler is available', wx.OK|wx.ICON_INFORMATION)
        dialog.ShowModal()
            
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

    @forceWxThread
    def upgradeCallback(self):
        self.setActivity(NTFY_ACT_NEW_VERSION)
        wx.CallLater(6000, self.upgradeCallback)

    #Force restart of Tribler
    @forceWxThread
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
            try:
                subprocess.Popen(executable)
            except:
                print_exc()

        atexit.register(start_tribler)
        self.Close(force = True)
    
    def OnFind(self, event):
        self.top_bg.SearchFocus()
    
    def OnNext(self, event):
        self.actlist.NextPage()
    
    
    def OnPrev(self, event):
        self.actlist.PrevPage()


    #######################################
    # minimize to tray bar control
    #######################################
    def onTaskBarActivate(self, event = None):
        if not self.GUIupdate:
            self.Iconize(False)
            self.Show(True)
            self.Raise()
            
            if self.tbicon is not None:
                self.tbicon.updateIcon(False)
                
            self.GUIupdate = True

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
            #Niels, 2011-06-17: why pause the video? This does not make any sense                                                                                                               
            #videoplayer = VideoPlayer.getInstance()
            #videoplayer.pause_playback() # when minimzed pause playback
            
            if self.utility.config.Read('mintray', "int") == 1:
                self.tbicon.updateIcon(True)
                self.Show(False)
                
            self.GUIupdate = False
        else:
            #Niels, 2011-06-17: why pause the video? This does not make any sense
            #at least make it so, that it will only resume if it was actually paused by the minimize action
            
            #videoplayer = VideoPlayer.getInstance()
            #videoplayer.resume_playback()
                
            self.GUIupdate = True
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
        self.GUIupdate = True
        if event is not None:
            if event.GetEventType() == wx.EVT_MAXIMIZE:
                self.window.SetClientSize(self.GetClientSize())
            event.Skip()
        
    def getWindowSettings(self):
        width = self.utility.config.Read("window_width")
        height = self.utility.config.Read("window_height")
        try:
            size = wx.Size(int(width), int(height))
        except:
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
        sashpos = self.utility.config.Read("sash_position")
        try:
            sashpos = int(sashpos)
        except:
            sashpos = -185

        return size, position, sashpos
        
    def saveWindowSettings(self):
        width, height = self.GetSizeTuple()
        x, y = self.GetPositionTuple()
        self.utility.config.Write("window_width", width)
        self.utility.config.Write("window_height", height)
        self.utility.config.Write("window_x", x)
        self.utility.config.Write("window_y", y)
        
        if self.splitter.IsShownOnScreen() and self.splitter.IsSplit():
            self.utility.config.Write("sash_position", self.splitter.GetSashPosition())

        self.utility.config.Flush()
       
    ##################################
    # Close Program
    ##################################
               
    def OnCloseWindow(self, event = None, force = False):
        found = False
        if event != None:
            nr = event.GetEventType()
            lookup = { wx.EVT_CLOSE.evtType[0]: "EVT_CLOSE", wx.EVT_QUERY_END_SESSION.evtType[0]: "EVT_QUERY_END_SESSION", wx.EVT_END_SESSION.evtType[0]: "EVT_END_SESSION" }
            if nr in lookup: 
                nr = lookup[nr]
                found = True
                
            print >>sys.stderr, "mainframe: Closing due to event ",nr,`event`
        else:
            print >>sys.stderr, "mainframe: Closing untriggered by event"
        
        
        # Don't do anything if the event gets called twice for some reason
        if self.utility.abcquitting:
            print 
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

                    dialog = wx.MessageDialog(self, confirmmsg, confirmtitle, wx.OK|wx.CANCEL|wx.ICON_QUESTION)
                    result = dialog.ShowModal()
                    dialog.Destroy()
                    if result != wx.ID_OK:
                        event.Veto()
                        
                        print >>sys.stderr, "mainframe: Not closing messagebox did not return OK"
                        return
            except:
                print_exc()
            
        self.utility.abcquitting = True
        self.GUIupdate = False
        
        if VideoPlayer.hasInstance():
            print >>sys.stderr, "mainframe: Closing videoplayer"

            videoplayer = VideoPlayer.getInstance()
            videoplayer.stop_playback()

        try:
            print >>sys.stderr, "mainframe: Restoring from taskbar"
            
            # Restore the window before saving size and position
            # (Otherwise we'll get the size of the taskbar button and a negative position)
            self.onTaskBarActivate()
            self.saveWindowSettings()
        except:
            print_exc()

        if self.tbicon is not None:
            try:
                print >>sys.stderr, "mainframe: Removing tbicon"
                    
                self.tbicon.RemoveIcon()
                self.tbicon.Destroy()
            except:
                print_exc()
            
        try:
            print >>sys.stderr, "mainframe: Calling Destroy"
            self.Destroy()
        except:
            print_exc()
            
        print >>sys.stderr, "mainframe: Calling quit"
        self.quit(event != None or force)
        self.Destroy()
        
        if DEBUG:
            print >>sys.stderr,"mainframe: OnCloseWindow END"
            ts = enumerate()
            for t in ts:
                print >>sys.stderr,"mainframe: Thread still running",t.getName(),"daemon",t.isDaemon()
    
    @forceWxThread
    def onWarning(self,exc):
        msg = self.utility.lang.get('tribler_startup_nonfatalerror')
        msg += str(exc.__class__)+':'+str(exc)
        dlg = wx.MessageDialog(None, msg, self.utility.lang.get('tribler_warning'), wx.OK|wx.ICON_WARNING)
        result = dlg.ShowModal()
        dlg.Destroy()
        
    def exceptionHandler(self, exc, fatal = False):
        type, value, stack = sys.exc_info()
        backtrace = traceback.format_exception(type, value, stack)
        
        def do_gui():
            win = FeedbackWindow(self.utility.lang.get('tribler_warning'))
            win.SetParent(self)
            win.CreateOutputWindow('')
            for line in backtrace:
                win.write(line)
            
            if fatal:
                win.Show()
            
        wx.CallAfter(do_gui)

    def progressHandler(self, title, message, maximum):
        return ThreadSafeProgressDialog(title, message, maximum, self, wx.PD_APP_MODAL|wx.PD_ELAPSED_TIME|wx.PD_ESTIMATED_TIME|wx.PD_REMAINING_TIME|wx.PD_AUTO_HIDE)

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
        try:
            #print >>sys.stderr,"MainFrame: setActivity: t",type,"m",msg,"a2",arg2
            if self.utility is None:
                if DEBUG:
                    print >>sys.stderr,"MainFrame: setActivity: Cannot display: t",type,"m",msg,"a2",arg2
                return
            
            if not wx.Thread_IsMain():
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
            self.SRstatusbar.onActivity(text)
            self.stats.onActivity(text)
        except wx.PyDeadObjectError:
            pass

    def set_player_status(self,s):
        """ Called by VideoServer when using an external player """
        if self.videoframe is not None:
            self.videoframe.set_player_status(s)

    def set_wxapp(self,wxapp):
        self.wxapp = wxapp
        
    def quit(self, force = True):
        print >> sys.stderr, "mainframe: in quit"
        if self.wxapp is not None:
            app = self.wxapp
        else:
            app = wx.GetApp()
            
        if app:
            wx.CallLater(1000, app.ExitMainLoop)
            if force:
                wx.CallLater(2500, app.Exit)
