#
# Author : Choopan RATTANAPOKA, Jie Yang, Arno Bakker
#
# Description : Main ABC [Yet Another Bittorrent Client] python script.
#               you can run from source code by using
#               >python abc.py
#               need Python, WxPython in order to run from source code.
#
# see LICENSE.txt for license information
#

import os
import sys
import traceback
import logging
import wx

import subprocess
import atexit
import re
import urlparse

import threading
import time
from traceback import print_exc, print_stack
import urllib
import copy

from Tribler.Category.Category import Category

from Tribler.Core.version import version_id
from Tribler.Core.simpledefs import (dlstatus_strings, NTFY_MYPREFERENCES, NTFY_ACT_NEW_VERSION, NTFY_ACT_NONE,
                                     NTFY_ACT_ACTIVE, NTFY_ACT_UPNP, NTFY_ACT_REACHABLE, NTFY_ACT_MEET,
                                     NTFY_ACT_GET_EXT_IP_FROM_PEERS, NTFY_ACT_GOT_METADATA, NTFY_ACT_RECOMMEND,
                                     NTFY_ACT_DISK_FULL, DLSTATUS_SEEDING, DLSTATUS_ALLOCATING_DISKSPACE,
                                     DLSTATUS_HASHCHECKING, DLSTATUS_WAITING4HASHCHECK, DOWNLOAD)
from Tribler.Core.exceptions import DuplicateDownloadException
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.Utilities.utilities import parse_magnetlink

from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.Utility.GuiDBHandler import startWorker

from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
from Tribler.Main.Dialogs.FeedbackWindow import FeedbackWindow
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.Dialogs.systray import ABCTaskBarIcon
from Tribler.Main.Dialogs.SaveAs import SaveAs

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.vwxGUI import DEFAULT_BACKGROUND, SEPARATOR_GREY
from Tribler.Main.vwxGUI.list import SearchList, ChannelList, LibraryList, ActivitiesList
from Tribler.Main.vwxGUI.list_details import (SearchInfoPanel, ChannelInfoPanel, LibraryInfoPanel, PlaylistInfoPanel,
                                              SelectedchannelInfoPanel, TorrentDetails, LibraryDetails, ChannelDetails,
                                              PlaylistDetails)
from Tribler.Main.vwxGUI.TopSearchPanel import TopSearchPanel, TopSearchPanelStub
from Tribler.Main.vwxGUI.home import Home, Stats, NetworkGraphPanel
from Tribler.Main.vwxGUI.channel import SelectedChannelList, Playlist, ManageChannel
from Tribler.Main.vwxGUI.SRstatusbar import SRstatusbar

from Tribler.Core.Video.utils import videoextdefaults


#
#
# Class: FileDropTarget
#
# To enable drag and drop for ABC list in main menu
#
#


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
                # lets see if we can find a .torrent in this directory
                head, _ = os.path.split(filename)
                files = os.listdir(head)

                found = False
                for file in files:
                    if file.endswith(".torrent"):  # this is the .torrent, use head as destdir to start seeding
                        filename = os.path.join(head, file)
                        destdir = head

                        found = True
                        break

                if not found:
                    dlg = wx.FileDialog(None, "Tribler needs a .torrent file to start seeding, please select the associated .torrent file.", wildcard="torrent (*.torrent)|*.torrent", style=wx.FD_OPEN)
                    if dlg.ShowModal() == wx.ID_OK:
                        filename = dlg.GetPath()

                        destdir = head
                        found = True
                    dlg.Destroy()
                if not found:
                    break
            try:
                self.frame.startDownload(filename, destdir=destdir, fixtorrent=True)
            except IOError:
                dlg = wx.MessageDialog(None,
                    "File not found or cannot be accessed.",
                    "Tribler Warning", wx.OK | wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
        return True


class MainFrame(wx.Frame):

    def __init__(self, parent, channelonly, internalvideo, progress):
        self._logger = logging.getLogger(self.__class__.__name__)

        print >> sys.stderr, 'GUI started'

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

        title = "Tribler %s" % version_id

        # Get window size and (sash) position from config file
        size, position, sashpos = self.getWindowSettings()
        style = wx.DEFAULT_DIALOG_STYLE | wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.NO_FULL_REPAINT_ON_RESIZE | wx.CLIP_CHILDREN

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
        if r > 190 or g > 190 or b > 190:  # Grey == 190,190,190
            self.SetForegroundColour(wx.BLACK)

        if internalvideo:
            self.videoparentpanel = wx.Panel(self)
            self.videoparentpanel.Hide()
        else:
            self.videoparentpanel = None

        # Create all components
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
            self.splitter_bottom_window.SetMinSize((-1, 25))
            self.splitter_bottom_window.SetForegroundColour(self.GetForegroundColour())
            self.splitter_bottom_window.OnChange = lambda: self.splitter_bottom.Layout()
            self.splitter_bottom_window.parent_list = self.splitter_bottom_window

            self.networkgraph = NetworkGraphPanel(self)
            self.networkgraph.Show(False)
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

            # Populate the bottom window
            self.splitter_bottom = wx.BoxSizer(wx.HORIZONTAL)
            self.torrentdetailspanel = TorrentDetails(self.splitter_bottom_window)
            self.torrentdetailspanel.Show(False)
            self.librarydetailspanel = LibraryDetails(self.splitter_bottom_window)
            self.librarydetailspanel.Show(False)
            self.channeldetailspanel = ChannelDetails(self.splitter_bottom_window)
            self.channeldetailspanel.Show(False)
            self.playlistdetailspanel = PlaylistDetails(self.splitter_bottom_window)
            self.playlistdetailspanel.Show(False)
            self.searchinfopanel = SearchInfoPanel(self.splitter_bottom_window)
            self.searchinfopanel.Show(False)
            self.channelinfopanel = ChannelInfoPanel(self.splitter_bottom_window)
            self.channelinfopanel.Show(False)
            self.libraryinfopanel = LibraryInfoPanel(self.splitter_bottom_window)
            self.libraryinfopanel.Show(False)
            self.playlistinfopanel = PlaylistInfoPanel(self.splitter_bottom_window)
            self.playlistinfopanel.Show(False)
            self.selectedchannelinfopanel = SelectedchannelInfoPanel(self.splitter_bottom_window)
            self.selectedchannelinfopanel.Show(False)
            self.splitter_bottom.Add(self.torrentdetailspanel, 1, wx.EXPAND)
            self.splitter_bottom.Add(self.librarydetailspanel, 1, wx.EXPAND)
            self.splitter_bottom.Add(self.channeldetailspanel, 1, wx.EXPAND)
            self.splitter_bottom.Add(self.playlistdetailspanel, 1, wx.EXPAND)
            self.splitter_bottom.Add(self.searchinfopanel, 1, wx.EXPAND)
            self.splitter_bottom.Add(self.channelinfopanel, 1, wx.EXPAND)
            self.splitter_bottom.Add(self.libraryinfopanel, 1, wx.EXPAND)
            self.splitter_bottom.Add(self.playlistinfopanel, 1, wx.EXPAND)
            self.splitter_bottom.Add(self.selectedchannelinfopanel, 1, wx.EXPAND)
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
            # position all elements
            vSizer = wx.BoxSizer(wx.VERTICAL)

            vSizer.Add(self.top_bg, 0, wx.EXPAND)

            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            vSizer.Add(hSizer, 1, wx.EXPAND)

            hSizer.Add(self.actlist, 0, wx.EXPAND)
            separator = wx.Panel(self, size=(1, -1))
            separator.SetBackgroundColour(SEPARATOR_GREY)
            hSizer.Add(separator, 0, wx.EXPAND)
            hSizer.Add(self.home, 1, wx.EXPAND)
            hSizer.Add(self.stats, 1, wx.EXPAND)
            hSizer.Add(self.networkgraph, 1, wx.EXPAND)
            hSizer.Add(self.splitter, 1, wx.EXPAND)
        else:
            vSizer = wx.BoxSizer(wx.VERTICAL)
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            vSizer.Add(hSizer, 1, wx.EXPAND | wx.ALL, 5)

            self.top_bg = TopSearchPanelStub()

        hSizer.Add(self.managechannel, 1, wx.EXPAND)

        if self.videoparentpanel:
            hSizer.Add(self.videoparentpanel, 1, wx.EXPAND)

        self.SetSizer(vSizer)

        # set sizes
        if not channelonly:
            self.top_bg.SetMinSize((-1, 45))
            self.actlist.SetMinSize((200, -1))

        self.SRstatusbar = SRstatusbar(self)
        self.SetStatusBar(self.SRstatusbar)

        def preload_data():
            if not channelonly:
                self.guiUtility.showChannelCategory('All', False)
            self.guiUtility.showLibrary(False)
        startWorker(None, preload_data, delay=1.5, workerType="guiTaskQueue")

        if channelonly:
            self.guiUtility.showChannelFromDispCid(channelonly)
            if internalvideo:
                self.guiUtility.ShowPlayer()

        if sys.platform != 'darwin':
            dragdroplist = FileDropTarget(self)
            self.SetDropTarget(dragdroplist)
        try:
            self.SetIcon(wx.Icon(os.path.join(self.utility.getPath(), 'Tribler', 'Main', 'vwxGUI', 'images', 'tribler.ico'), wx.BITMAP_TYPE_ICO))
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
        #
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
        anonId = wx.NewId()
        DISPERSY_DEBUG_FRAME_ID = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnFind, id=findId)
        self.Bind(wx.EVT_MENU, lambda event: self.Close(), id=quitId)
        self.Bind(wx.EVT_MENU, self.OnNext, id=nextId)
        self.Bind(wx.EVT_MENU, self.OnPrev, id=prevId)
        self.Bind(wx.EVT_MENU, lambda evt: self.guiUtility.ShowPage('stats'), id=dispId)
        self.Bind(wx.EVT_MENU, lambda evt: self.guiUtility.ShowPage('networkgraph'), id=anonId)
        self.Bind(wx.EVT_MENU, self.OnOpenDebugFrame, id=DISPERSY_DEBUG_FRAME_ID)

        accelerators = [(wx.ACCEL_CTRL, ord('f'), findId)]
        accelerators.append((wx.ACCEL_CTRL, ord('d'), dispId))
        accelerators.append((wx.ACCEL_CTRL, ord('n'), anonId))
        accelerators.append((wx.ACCEL_CTRL, wx.WXK_TAB, nextId))
        accelerators.append((wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_TAB, prevId))
        accelerators.append((wx.ACCEL_CTRL | wx.ACCEL_ALT, ord('d'), DISPERSY_DEBUG_FRAME_ID))

        if sys.platform == 'linux2':
            accelerators.append((wx.ACCEL_CTRL, ord('q'), quitId))
            accelerators.append((wx.ACCEL_CTRL, ord('/'), findId))
        self.SetAcceleratorTable(wx.AcceleratorTable(accelerators))

        # Init video player
        print >> sys.stderr, 'GUI ready'
        self.Thaw()
        self.ready = True

        def post():
            self.checkVersion()
            self.startCMDLineTorrent()

        # If the user passed a torrentfile on the cmdline, load it.
        wx.CallAfter(post)

    def OnOpenDebugFrame(self, event=None):
        from Tribler.Main.vwxGUI.DispersyDebugFrame import DispersyDebugFrame
        if not wx.FindWindowByName("DispersyDebugFrame"):
            frame = DispersyDebugFrame(self, -1, self.utility.session.get_dispersy_instance())
            frame.Show()

        if event:
            event.Skip()

    def startCMDLineTorrent(self):
        if self.params[0] != "" and not self.params[0].startswith("--"):
            vod = False
            url_filename = self.params[0]
            selectedFiles = [self.params[1]] if len(self.params) == 2 else None
            if selectedFiles:
                _, ext = os.path.splitext(selectedFiles[0])
                if ext != '' and ext[0] == '.':
                    ext = ext[1:]
                if ext.lower() in videoextdefaults:
                    vod = True

            if url_filename.startswith("magnet:"):
                self.startDownloadFromMagnet(self.params[0], cmdline=True, selectedFiles=selectedFiles, vodmode=vod)
            elif url_filename.startswith("http"):
                self.startDownloadFromUrl(self.params[0], cmdline=True, selectedFiles=selectedFiles, vodmode=vod)
            else:
                self.startDownload(url_filename, cmdline=True, selectedFiles=selectedFiles, vodmode=vod)

    def startDownloadFromMagnet(self, url, destdir=None, cmdline=False, selectedFiles=None, vodmode=False, hops=0):
        name, infohash, _ = parse_magnetlink(url)
        tdef = TorrentDefNoMetainfo(infohash, name, url=url)
        wx.CallAfter(self.startDownload, tdef=tdef, cmdline=cmdline, destdir=destdir, selectedFiles=selectedFiles, vodmode=vodmode, hops=0)
        return True

    def startDownloadFromUrl(self, url, destdir=None, cmdline=False, selectedFiles=None, vodmode=False, hops=0):
        try:
            tdef = TorrentDef.load_from_url(url)
            if tdef:
                kwargs = {'tdef': tdef,
                          'cmdline': cmdline,
                          'destdir': destdir,
                          'selectedFiles': selectedFiles,
                          'vodmode': vodmode,
                          'hops':hops}
                if wx.Thread_IsMain():
                    self.startDownload(**kwargs)
                else:
                    wx.CallAfter(self.startDownload, *kwargs)
                return True
        except:
            print_exc()
        self.guiUtility.Notify("Download from url failed", icon=wx.ART_WARNING)
        return False

    def startDownload(self, torrentfilename=None, destdir=None, tdef=None, cmdline=False, clicklog=None,
                      name=None, vodmode=False, hops=0, try_hidden_services=False, fixtorrent=False, selectedFiles=None,
                      correctedFilename=None, hidden=False):
        self._logger.debug(u"startDownload: %s %s %s %s %s", torrentfilename, destdir, tdef, vodmode, selectedFiles)

        if fixtorrent and torrentfilename:
            self.fixTorrent(torrentfilename)

        try:
            if torrentfilename and tdef is None:
                tdef = TorrentDef.load(torrentfilename)

            d = self.utility.session.get_download(tdef.get_id())
            if d:
                new_trackers = list(set(tdef.get_trackers_as_single_tuple()) - set(d.get_def().get_trackers_as_single_tuple()))
                if not new_trackers:
                    raise DuplicateDownloadException()

                else:
                    @forceWxThread
                    def do_gui():
                        # Show update tracker dialog
                        dialog = wx.MessageDialog(None, 'This torrent is already being downloaded. Do you wish to load the trackers from it?', 'Tribler', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
                        if dialog.ShowModal() == wx.ID_YES:
                            # Update trackers
                            self.utility.session.update_trackers(cdef.get_id(), new_trackers)
                        dialog.Destroy()

                    do_gui()
                return

            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()

            cancelDownload = False
            useDefault = not self.utility.read_config('showsaveas')
            if not useDefault and not destdir:
                defaultname = correctedFilename
                if not correctedFilename and tdef and tdef.is_multifile_torrent():
                    defaultname = tdef.get_name_as_unicode()

                if wx.Thread_IsMain():
                    dlg = SaveAs(None, tdef, dscfg.get_dest_dir(), defaultname, selectedFiles)
                    dlg.CenterOnParent()

                    if isinstance(tdef, TorrentDefNoMetainfo):
                        # Correct for the smaller size of the dialog if there is no metainfo
                        center_pos = dlg.GetPosition()
                        center_pos[1] -= 150
                        dlg.SetPosition(center_pos)

                    if dlg.ShowModal() == wx.ID_OK:
                        # If the dialog has collected a torrent, use the new tdef
                        tdef = dlg.GetCollected() or tdef

                        # for multifile we enabled correctedFilenames, use split to remove the filename from the path
                        if tdef and tdef.is_multifile_torrent():
                            destdir, correctedFilename = os.path.split(dlg.GetPath())
                            selectedFiles = dlg.GetSelectedFiles()
                        else:
                            destdir = dlg.GetPath()
                        hops = dlg.GetHops()
                    else:
                        cancelDownload = True
                    dlg.Destroy()
                else:
                    raise Exception("cannot create dialog, not on wx thread")

            # use default setup
            else:
                # set hops to the default anonymous level
                hops = self.utility.read_config('default_anonymous_level')

            if hops > 0:
                if not tdef:
                    raise Exception('Currently only torrents can be downloaded in anonymous mode')

            if try_hidden_services and not vodmode and not isinstance(tdef, TorrentDefNoMetainfo) and \
               not tdef.is_anonymous() and hops > 0:
                monitorHiddenSerivcesProgress = True
                # Set anonymous flag
                metainfo = copy.deepcopy(tdef.metainfo)
                metainfo['info']['anonymous'] = 1
                orig_tdef = tdef
                cdef = tdef = TorrentDef._create(metainfo)
            else:
                monitorHiddenSerivcesProgress = False

            dscfg.set_hops(hops)

            if not cancelDownload:
                if destdir is not None:
                    dscfg.set_dest_dir(destdir)

                if correctedFilename:
                    dscfg.set_corrected_filename(correctedFilename)

                if selectedFiles and len(selectedFiles) == 1:
                    # we should filter files to see if they are all playable
                    videofiles = selectedFiles

                elif tdef and not selectedFiles:
                    videofiles = tdef.get_files(exts=videoextdefaults)

                else:
                    videofiles = []

                # disable vodmode if no videofiles, unless we still need to collect the torrent
                if vodmode and len(videofiles) == 0 and (not tdef or not isinstance(tdef, TorrentDefNoMetainfo)):
                    vodmode = False

                vodmode = vodmode or tdef.get_live()

                if vodmode:
                    self._logger.info('MainFrame: startDownload: Starting in VOD mode')
                    result = self.utility.session.start_download(tdef, dscfg)
                    self.guiUtility.library_manager.playTorrent(tdef.get_id(), videofiles[0] if len(videofiles) == 1 else None)

                else:
                    if selectedFiles:
                        dscfg.set_selected_files(selectedFiles)

                    self._logger.debug('MainFrame: startDownload: Starting in DL mode')
                    result = self.utility.session.start_download(tdef, dscfg, hidden=hidden)

                if result and not hidden:
                    self.show_saved(tdef)

                    if monitorHiddenSerivcesProgress:
                        state_lambda = lambda ds, tdef = orig_tdef, dscfg = dscfg, selectedFiles = selectedFiles: self.monitorHiddenSerivcesProgress(ds, tdef, dscfg, selectedFiles)
                        result.set_state_callback(state_lambda, delay=40.0)

                if clicklog is not None:
                    mypref = self.utility.session.open_dbhandler(NTFY_MYPREFERENCES)
                    startWorker(None, mypref.addClicklogToMyPreference, wargs=(tdef.get_id(), clicklog))

                return result

        except DuplicateDownloadException as e:
            # If there is something on the cmdline, all other torrents start
            # in STOPPED state. Restart
            if cmdline:
                dlist = self.utility.session.get_downloads()
                for d in dlist:
                    if d.get_def().get_infohash() == tdef.get_infohash():
                        d.restart()
                        break

            if wx.Thread_IsMain():
                # show nice warning dialog
                dlg = wx.MessageDialog(None,
                    "You are already downloading this torrent, see the Downloads section.",
                    "Duplicate download", wx.OK | wx.ICON_ERROR)
                result = dlg.ShowModal()
                dlg.Destroy()

            else:
                print_exc()
                self.onWarning(e)

        except Exception as e:
            print_exc()
            self.onWarning(e)

        return None

    def modifySelection(self, download, selectedFiles):
        download.set_selected_files(selectedFiles)

    def fixTorrent(self, filename):
        f = open(filename, "rb")
        bdata = f.read()
        f.close()

        # Check if correct bdata
        try:
            bdecode(bdata)
        except ValueError:
            # Try reading using sloppy
            try:
                bdata = bencode(bdecode(bdata, 1))
                # Overwrite with non-sloppy torrent
                f = open(filename, "wb")
                f.write(bdata)
                f.close()
            except:
                return False

        return True

    def monitorHiddenSerivcesProgress(self, ds, tdef, dscfg, selectedFiles):
        if ds.get_status() in [DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_HASHCHECKING, DLSTATUS_WAITING4HASHCHECK]:
            return (5.0, True)

        if ds.get_current_speed(DOWNLOAD) == 0:
            download = ds.get_download()
            self.utility.session.remove_download(download)

            self._logger.error("Switching from hidden services to exit nodes")
            dscfg = dscfg.copy()
            dscfg.set_selected_files(selectedFiles or [])
            self.utility.session.start_download(tdef, dscfg)
        return (0, False)

    @forceWxThread
    def show_saved(self, tdef):
        if self.ready and self.librarylist.isReady:
            torrentname = tdef.get_name_as_unicode() if tdef else ''
            if isinstance(tdef, TorrentDefNoMetainfo):
                if torrentname:
                    self.guiUtility.Notify('Downloading .torrent \'%s\' from DHT' % torrentname, icon='magnet')
                else:
                    self.guiUtility.Notify('Downloading .torrent from DHT', icon='magnet')
            elif torrentname:
                self.guiUtility.Notify("Download started", "Torrent '%s' has been added to the download queue." % torrentname, icon='download')
            else:
                self.guiUtility.Notify("Download started", "A new torrent has been added to the download queue.", icon='download')

            self._logger.info("Allowing refresh in 3 seconds %s", long(time.time() + 3))
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
            # Web2Updater(self.utility).checkUpdate()
        except Exception as e:
            self._logger.error("Tribler: Version check failed %s %s", time.ctime(time.time()), str(e))
            # print_exc()

    def _upgradeVersion(self, my_version, latest_version, info):
        # check if there is a .torrent for our OS
        torrent_key = "torrent-%s" % sys.platform
        notes_key = "notes-txt-%s" % sys.platform
        if torrent_key in info:
            self._logger.info("-- Upgrade %s -> %s", my_version, latest_version)
            notes = []
            if "notes-txt" in info:
                notes.append(info["notes-txt"])
            if notes_key in info:
                notes.append(info[notes_key])
            notes = "\n".join(notes)
            if notes:
                for line in notes.split("\n"):
                    self._logger.info("-- Notes: %s", line)
            else:
                notes = "No release notes found"
            self._logger.info("-- Downloading %s for upgrade", info[torrent_key])

            # prepare directort and .torrent file
            location = os.path.join(self.utility.session.get_state_dir(), "upgrade")
            if not os.path.exists(location):
                os.mkdir(location)
            self._logger.info("-- Dir: %s", location)
            filename = os.path.join(location, os.path.basename(urlparse.urlparse(info[torrent_key])[2]))
            self._logger.info("-- File: %s", filename)
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
                    self._logger.info("-- exe: %s", file_)
                    executable = file_
                    break

                elif sys.platform == "linux2" and file_.endswith(u".deb"):
                    self._logger.info("-- deb: %s", file_)
                    executable = file_
                    break

                elif sys.platform == "darwin" and file_.endswith(u".dmg"):
                    self._logger.info("-- dmg: %s", file_)
                    executable = file_
                    break

            if not executable:
                self._logger.info("-- Abort upgrade: no file found")
                return

            # start download
            try:
                download = self.utility.session.start_download(tdef)

            except DuplicateDownloadException:
                self._logger.error("-- Duplicate download")
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

                    self._logger.info("-- Tribler closed, starting upgrade")
                    self._logger.info("-- Start: %s", args)
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
                    self._logger.debug("-- State: %s %s", dlstatus_strings[state.get_status()], state.get_progress())
                    # todo: does DLSTATUS_STOPPED mean it has completely downloaded?
                    if state.get_status() == DLSTATUS_SEEDING:
                        self.shutdown_and_upgrade_notes = notes
                        wx.CallAfter(wxthread_upgrade)
                        return (0.0, False)
                    return (1.0, False)

                download.set_state_callback(state_callback)

    @forceWxThread
    def _manualUpgrade(self, my_version, latest_version, url):
        dialog = wx.MessageDialog(self, 'There is a new version of Tribler.\nYour version:\t\t\t\t%s\nLatest version:\t\t\t%s\n\nPlease visit %s to upgrade.' % (my_version, latest_version, url), 'New version of Tribler is available', wx.OK | wx.ICON_INFORMATION)
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

    # Force restart of Tribler
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
        self._logger.info(repr(executable))

        def start_tribler():
            try:
                subprocess.Popen(executable)
            except:
                print_exc()

        atexit.register(start_tribler)
        self.Close(force=True)

    def OnFind(self, event):
        self.top_bg.SearchFocus()

    def OnNext(self, event):
        self.actlist.NextPage()

    def OnPrev(self, event):
        self.actlist.PrevPage()

    #
    # minimize to tray bar control
    #
    def onTaskBarActivate(self, event=None):
        if not self.GUIupdate:
            self.Iconize(False)
            self.Show(True)
            self.Raise()

            if self.tbicon is not None:
                self.tbicon.updateIcon(False)

            self.GUIupdate = True

    def onIconify(self, event=None):
        # This event handler is called both when being minimalized
        # and when being restored.
        # Arno, 2010-01-15: on Win7 with wxPython2.8-win32-unicode-2.8.10.1-py26
        # there is no event on restore :-(
        if event is not None:
            self._logger.debug("main: onIconify( %s", event.Iconized())
        else:
            self._logger.debug("main: onIconify event None")

        if event.Iconized():
            # Niels, 2011-06-17: why pause the video? This does not make any sense
            # videoplayer = VideoPlayer.getInstance()
            # videoplayer.pause_playback() # when minimzed pause playback

            if self.utility.read_config('mintray') == 1:
                self.tbicon.updateIcon(True)
                self.Show(False)

            self.GUIupdate = False
        else:
            # Niels, 2011-06-17: why pause the video? This does not make any sense
            # at least make it so, that it will only resume if it was actually paused by the minimize action

            # videoplayer = VideoPlayer.getInstance()
            # videoplayer.resume_playback()

            self.GUIupdate = True
        if event is not None:
            event.Skip()

    def onSize(self, event=None):
        # Arno: On Windows when I enable the tray icon and then change
        # virtual desktop (see MS DeskmanPowerToySetup.exe)
        # I get a onIconify(event.Iconized()==True) event, but when
        # I switch back, I don't get an event. As a result the GUIupdate
        # remains turned off. The wxWidgets wiki on the TaskBarIcon suggests
        # catching the onSize event.
        if event is not None:
            self._logger.debug("main: onSize: %s", self.GetSize())
        else:
            self._logger.debug("main: onSize: None")

        self.GUIupdate = True
        if event is not None:
            if event.GetEventType() == wx.EVT_MAXIMIZE:
                self.window.SetClientSize(self.GetClientSize())
            event.Skip()

    def getWindowSettings(self):
        width = self.utility.read_config("window_width")
        height = self.utility.read_config("window_height")
        try:
            size = wx.Size(int(width), int(height))
        except:
            size = wx.Size(1024, 670)

        x = self.utility.read_config("window_x")
        y = self.utility.read_config("window_y")
        if (x == "" or y == "" or x == 0 or y == 0):
            # position = wx.DefaultPosition

            # On Mac, the default position will be underneath the menu bar, so lookup (top,left) of
            # the primary display
            primarydisplay = wx.Display(0)
            dsize = primarydisplay.GetClientArea()
            position = dsize.GetTopLeft()

            # Decrease size to fit on screen, if needed
            width = min(size.GetWidth(), dsize.GetWidth())
            height = min(size.GetHeight(), dsize.GetHeight())
            size = wx.Size(width, height)
        else:
            position = wx.Point(int(x), int(y))
        sashpos = self.utility.read_config("sash_position")
        try:
            sashpos = int(sashpos)
        except:
            sashpos = -185

        return size, position, sashpos

    def saveWindowSettings(self):
        width, height = self.GetSizeTuple()
        x, y = self.GetPositionTuple()
        self.utility.write_config("window_width", width)
        self.utility.write_config("window_height", height)
        self.utility.write_config("window_x", x)
        self.utility.write_config("window_y", y)

        if self.splitter.IsShownOnScreen() and self.splitter.IsSplit():
            self.utility.write_config("sash_position", self.splitter.GetSashPosition())

        self.utility.flush_config()

    #
    # Close Program
    #

    def OnCloseWindow(self, event=None, force=False):
        found = False
        if event is not None:
            nr = event.GetEventType()
            lookup = {wx.EVT_CLOSE.evtType[0]: "EVT_CLOSE", wx.EVT_QUERY_END_SESSION.evtType[0]: "EVT_QUERY_END_SESSION", wx.EVT_END_SESSION.evtType[0]: "EVT_END_SESSION"}
            if nr in lookup:
                nr = lookup[nr]
                found = True

            self._logger.info("mainframe: Closing due to event %s %s", nr, repr(event))
        else:
            self._logger.info("mainframe: Closing untriggered by event")

        # Don't do anything if the event gets called twice for some reason
        if self.utility.abcquitting:
            return

        # Check to see if we can veto the shutdown
        # (might not be able to in case of shutting down windows)
        if event is not None:
            try:
                if isinstance(event, wx.CloseEvent) and event.CanVeto() and self.utility.read_config('confirmonclose') and not event.GetEventType() == wx.EVT_QUERY_END_SESSION.evtType[0]:
                    if self.shutdown_and_upgrade_notes:
                        confirmmsg = "Do you want to close Tribler and upgrade to the next version?  See release notes below" + "\n\n" + self.shutdown_and_upgrade_notes
                        confirmtitle = "Upgrade Tribler?"
                    else:
                        confirmmsg = "Do you want to close Tribler?"
                        confirmtitle = "Confirm"

                    dialog_name = 'closeconfirmation'
                    if not self.shutdown_and_upgrade_notes and not self.guiUtility.ReadGuiSetting('show_%s' % dialog_name, default=True):
                        result = wx.ID_OK
                    else:
                        dialog = ConfirmationDialog(None, dialog_name, confirmmsg, title=confirmtitle)
                        result = dialog.ShowModal()
                        dialog.Destroy()

                    if result != wx.ID_OK:
                        event.Veto()

                        self._logger.info("mainframe: Not closing messagebox did not return OK")
                        return
            except:
                print_exc()

        print >> sys.stderr, 'GUI closing'
        self.utility.abcquitting = True
        self.GUIupdate = False

        if self.videoframe:
            self._logger.info("mainframe: Stopping internal player")

            self.videoframe.get_videopanel().Stop()

        try:
            self._logger.info("mainframe: Restoring from taskbar")

            # Restore the window before saving size and position
            # (Otherwise we'll get the size of the taskbar button and a negative position)
            self.onTaskBarActivate()
            self.saveWindowSettings()
        except:
            print_exc()

        if self.tbicon is not None:
            try:
                self._logger.info("mainframe: Removing tbicon")

                self.tbicon.RemoveIcon()
                self.tbicon.Destroy()
            except:
                print_exc()

        self._logger.info("mainframe: Calling quit")
        self.quit(event is not None or force)

        self._logger.debug("mainframe: OnCloseWindow END")
        ts = threading.enumerate()
        for t in ts:
            self._logger.info("mainframe: Thread still running %s daemon %s", t.getName(), t.isDaemon())

        print >> sys.stderr, 'GUI closed'

    @forceWxThread
    def onWarning(self, exc):
        msg = "A non-fatal error occured during Tribler startup, you may need to change the network Preferences:  \n\n"
        msg += str(exc.__class__) + ':' + str(exc)
        dlg = wx.MessageDialog(None, msg, "Tribler Warning", wx.OK | wx.ICON_WARNING)
        result = dlg.ShowModal()
        dlg.Destroy()

    def exceptionHandler(self, exc, fatal=False):
        type, value, stack = sys.exc_info()
        backtrace = traceback.format_exception(type, value, stack)

        def do_gui():
            win = FeedbackWindow("Tribler Warning")
            win.SetParent(self)
            win.CreateOutputWindow('')
            for line in backtrace:
                win.write(line)

            if fatal:
                win.Show()

        wx.CallAfter(do_gui)

    def onUPnPError(self, upnp_type, listenport, error_type, exc=None, listenproto='TCP'):

        if error_type == 0:
            errormsg = unicode(' UPnP mode ' + str(upnp_type) + ' ') + "request to the firewall failed."
        elif error_type == 1:
            errormsg = unicode(' UPnP mode ' + str(upnp_type) + ' ') + "request to firewall returned:  '" + unicode(str(exc)) + "'. "
        elif error_type == 2:
            errormsg = unicode(' UPnP mode ' + str(upnp_type) + ' ') + "was enabled, but initialization failed."
        else:
            errormsg = unicode(' UPnP mode ' + str(upnp_type) + ' Unknown error')

        msg = "An error occured while trying to open the listen port "
        msg += listenproto + ' '
        msg += str(listenport)
        msg += " on the firewall."
        msg += errormsg
        msg += " This will hurt the performance of Tribler.\n\nTo fix this, configure your firewall/router/modem or try setting a different listen port or UPnP mode in (advanced) network Preferences."

        dlg = wx.MessageDialog(None, msg, "Tribler Warning", wx.OK | wx.ICON_WARNING)
        result = dlg.ShowModal()
        dlg.Destroy()

    def setActivity(self, type, msg=u'', arg2=None):
        try:
            # print >>sys.stderr,"MainFrame: setActivity: t",type,"m",msg,"a2",arg2
            if self.utility is None:
                self._logger.debug("MainFrame: setActivity: Cannot display: t %s m %s a2 %s", type, msg, arg2)
                return

            if not wx.Thread_IsMain():
                self._logger.debug("main: setActivity thread %s is NOT MAIN THREAD", threading.currentThread().getName())
                print_stack()

            if type == NTFY_ACT_NONE:
                prefix = msg
                msg = u''
            elif type == NTFY_ACT_ACTIVE:
                prefix = u""
                if msg == "no network":
                    text = "No network - last activity: %.1f seconds ago" % arg2
                    self.SetTitle(text)
                    self._logger.info("main: Activity %s", repr(text))
                elif self.GetTitle().startswith("No network"):
                    title = "Tribler %s" % version_id
                    self.SetTitle(title)

            elif type == NTFY_ACT_UPNP:
                prefix = "Opening firewall (if any) via UPnP"
            elif type == NTFY_ACT_REACHABLE:
                prefix = "Seeing if not firewalled"
            elif type == NTFY_ACT_GET_EXT_IP_FROM_PEERS:
                prefix = "Asking peers for my IP address"
            elif type == NTFY_ACT_MEET:
                prefix = "Person connected: "
            elif type == NTFY_ACT_GOT_METADATA:
                prefix = "File discovered:"

                if self.category.family_filter_enabled() and arg2 == 7:  # XXX category
                    self._logger.debug("MainFrame: setActivity: Hiding XXX torrent %s", msg)
                    return

            elif type == NTFY_ACT_RECOMMEND:
                prefix = "Discovered more persons and files from"
            elif type == NTFY_ACT_DISK_FULL:
                prefix = "Disk is full to collect more torrents. Please change your preferences or free space on "
            elif type == NTFY_ACT_NEW_VERSION:
                prefix = "New version of Tribler available"
            if msg == u'':
                text = prefix
            else:
                text = unicode(prefix + u' ' + msg)

            self._logger.debug("main: Activity %s", repr(text))
            self.SRstatusbar.onActivity(text)
            self.stats.onActivity(text)
        except wx.PyDeadObjectError:
            pass

    def set_wxapp(self, wxapp):
        self.wxapp = wxapp

    @forceWxThread
    def quit(self, force=True):
        self._logger.info("mainframe: in quit")
        if self.wxapp is not None:
            self._logger.info("mainframe: using self.wxapp")
            app = self.wxapp
        else:
            self._logger.info("mainframe: got app from wx")
            app = wx.GetApp()

        self._logger.info("mainframe: looping through toplevelwindows")
        for item in wx.GetTopLevelWindows():
            if item != self:
                if isinstance(item, wx.Dialog):
                    self._logger.info("mainframe: destroying %s", item)
                    item.Destroy()
                item.Close()
        self._logger.info("mainframe: destroying %s", self)
        self.Destroy()

        if app:
            def doexit():
                app.ExitMainLoop()
                wx.WakeUpMainThread()

            wx.CallLater(1000, doexit)
            if force:
                wx.CallLater(2500, app.Exit)
