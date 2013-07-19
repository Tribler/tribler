# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker, Lucian Musat
# Modified by Niels Zeilemaker
# see LICENSE.txt for license information

import random
import wx
import os
import sys
import json

from wx import xrc

from Tribler.__init__ import LIBRARYNAME

from Tribler.Category.Category import Category
from Tribler.Core.CacheDB.SqliteCacheDBHandler import UserEventLogDBHandler
from Tribler.Core.Search.SearchManager import split_into_keywords, \
    fts3_preprocess
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager, ChannelManager, LibraryManager
from Tribler.Video.VideoPlayer import VideoPlayer
from time import time
from Tribler.Main.vwxGUI import forceWxThread
from Tribler.Main.Utility.GuiDBTuples import RemoteChannel
from Tribler.Main.vwxGUI.TorrentStateManager import TorrentStateManager
from Tribler.Core.simpledefs import SWIFT_URL_SCHEME
from Tribler.Core.CacheDB.sqlitecachedb import forcePrioDBThread

DEBUG = False


class GUIUtility:
    __single = None

    def __init__(self, utility=None, params=None, app=None):
        if GUIUtility.__single:
            raise RuntimeError("GUIUtility is singleton")
        GUIUtility.__single = self
        self.registered = False

        # do other init
        self.utility = utility
        self.vwxGUI_path = os.path.join(self.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI')
        self.utility.guiUtility = self
        self.params = params
        self.frame = None
        self.app = app

        # videoplayer
        self.videoplayer = VideoPlayer.getInstance()

        # current GUI page
        self.guiPage = 'home'
        # previous pages
        self.oldpage = []

        # firewall
        self.firewall_restart = False  # ie Tribler needs to restart for the port number to be updated

        # Recall improves by 20-25% by increasing the number of peers to query to 20 from 10 !
        self.max_remote_queries = 20  # max number of remote peers to query

        self.current_search_query = ''

        self.lists = []

    def getInstance(*args, **kw):
        if GUIUtility.__single is None:
            GUIUtility(*args, **kw)
        return GUIUtility.__single
    getInstance = staticmethod(getInstance)

    def hasInstance():
        return GUIUtility.__single != None
    hasInstance = staticmethod(hasInstance)

    def delInstance():
        if GUIUtility.__single:
            GUIUtility.__single.library_manager.delInstance()
            GUIUtility.__single.channelsearch_manager.delInstance()
            GUIUtility.__single.torrentsearch_manager.delInstance()

        GUIUtility.__single = None
    delInstance = staticmethod(delInstance)

    def register(self):
        if not self.registered:
            self.registered = True

            self.torrentsearch_manager = TorrentManager.getInstance(self)
            self.channelsearch_manager = ChannelManager.getInstance()
            self.library_manager = LibraryManager.getInstance(self)
            self.torrentstate_manager = TorrentStateManager.getInstance(self)

            self.torrentsearch_manager.connect(self.utility.session, self.library_manager, self.channelsearch_manager)
            self.channelsearch_manager.connect(self.utility.session, self.library_manager, self.torrentsearch_manager)
            self.library_manager.connect(self.utility.session, self.torrentsearch_manager, self.channelsearch_manager)
            self.torrentstate_manager.connect(self.torrentsearch_manager, self.library_manager, self.channelsearch_manager)
        else:
            raise RuntimeError('GuiUtility is already registered')

    def ShowPlayer(self):
        if self.frame.videoparentpanel:
            self.ShowPage('videoplayer')

    @forceWxThread
    def ShowPage(self, page, *args):
        if page == 'settings':
            xrcResource = os.path.join(self.vwxGUI_path, 'settingsDialog.xrc')
            res = xrc.XmlResource(xrcResource)
            dialog = res.LoadDialog(None, 'settingsDialog')
            if not dialog:  # failed to load dialog
                return

            dialog.Centre()
            dialog.ShowModal()
            dialog.Destroy()

        elif page != self.guiPage:
            self.frame.actlist.selectTab(page)

            self.frame.top_bg.ClearButtonHandlers()

            self.oldpage.append(self.guiPage)
            if len(self.oldpage) > 3:
                self.oldpage.pop(0)

            self.frame.Freeze()

            if page not in ['search_results', 'my_files', 'selectedchannel', 'playlist', 'channels']:
                self.frame.splitter.Show(False)

            if page == 'search_results':
                # Show list
                self.SetTopSplitterWindow(self.frame.searchlist)
                items = self.frame.searchlist.GetExpandedItems()
                if items:
                    self.frame.searchlist.Select(items[0][0])
                else:
                    self.frame.searchlist.ResetBottomWindow()
            elif self.guiPage == 'search_results':
                # Hide list
                self.frame.searchlist.Show(False)

            if page == 'channels':
                self.SetTopSplitterWindow(self.frame.channellist)
                items = self.frame.channellist.GetExpandedItems()
                if items:
                    self.frame.channellist.Select(items[0][0])
                else:
                    self.frame.channellist.ResetBottomWindow()

            elif self.guiPage == 'channels':
                self.frame.channellist.Show(False)

            if page == 'mychannel':
                # Show list
                self.frame.managechannel.SetChannelId(self.channelsearch_manager.channelcast_db._channel_id)
                self.frame.managechannel.Show()

            elif self.guiPage == 'mychannel':
                self.frame.managechannel.Show(False)

            if page == 'managechannel':
                self.frame.managechannel.Show()

            elif self.guiPage == 'managechannel':
                self.frame.managechannel.Show(False)

            if page == 'selectedchannel':
                self.SetTopSplitterWindow(self.frame.selectedchannellist)
                items = self.frame.selectedchannellist.GetExpandedItems()
                if items:
                    self.frame.selectedchannellist.Select(items[0][0])
                else:
                    self.frame.selectedchannellist.ResetBottomWindow()
                channelmenu = self.frame.actlist.GetItem(3)
                if channelmenu and channelmenu.expandedPanel:
                    channelmenu.expandedPanel.AddCurrentChannelLink()

            elif self.guiPage == 'selectedchannel':
                self.frame.selectedchannellist.Show(False)
                if not self.frame.splitter.IsSplit():
                    sashpos = getattr(self.frame.splitter_top_window, 'sashpos', -185)
                    self.frame.splitter.SplitHorizontally(self.frame.splitter_top_window, self.frame.splitter_bottom_window, sashpos)

            if page == 'playlist':
                self.SetTopSplitterWindow(self.frame.playlist)
                items = self.frame.playlist.GetExpandedItems()
                if items:
                    self.frame.playlist.Select(items[0][0])
                else:
                    self.frame.playlist.ResetBottomWindow()
                channelmenu = self.frame.actlist.GetItem(3)
                if channelmenu and channelmenu.expandedPanel:
                    channelmenu.expandedPanel.AddCurrentPlaylistLink()

            elif self.guiPage == 'playlist':
                self.frame.playlist.Show(False)

            if page == 'my_files':
                # Show list
                self.SetTopSplitterWindow(self.frame.librarylist)

                # Open infohash
                if args:
                    self.frame.librarylist.GetManager().refresh_or_expand(args[0])
                else:
                    items = self.frame.librarylist.GetExpandedItems()
                    if items:
                        items[0][1].expanded = False
                        self.frame.librarylist.Select(items[0][0])
                    else:
                        self.frame.librarylist.ResetBottomWindow()

                # Open infohash
                if args:
                    self.frame.librarylist.GetManager().refresh_or_expand(args[0])

            elif self.guiPage == 'my_files':
                # Hide list
                self.frame.librarylist.Show(False)

            if page == 'home':
                self.frame.home.ResetSearchBox()
                self.frame.home.Show()
            elif self.guiPage == 'home':
                self.frame.home.Show(False)

            if page == 'stats':
                self.frame.stats.Show()
            elif self.guiPage == 'stats':
                self.frame.stats.Show(False)

            if self.frame.videoparentpanel:
                if page == 'videoplayer':
                    self.frame.videoparentpanel.Show(True)
                elif self.guiPage == 'videoplayer':
                    self.frame.videoparentpanel.Show(False)

            self.guiPage = page
            self.frame.Layout()
            self.frame.Thaw()

        # Set focus to page
        if page == 'search_results':
            self.frame.searchlist.Focus()

            if args:
                self.frame.searchlist.total_results = None
                self.frame.searchlist.SetKeywords(args[0])

        elif page == 'channels':
            self.frame.channellist.Focus()
        elif page == 'selectedchannel':
            self.frame.selectedchannellist.Focus()
        elif page == 'my_files':
            self.frame.librarylist.Focus()

    def GetSelectedPage(self):
        if self.guiPage == 'home':
            return self.frame.home

        if self.guiPage == 'search_results':
            return self.frame.searchlist

        if self.guiPage == 'channels':
            return self.frame.channellist

        if self.guiPage == 'selectedchannel':
            return self.frame.selectedchannellist

        if self.guiPage == 'mychannel':
            return self.frame.managechannel

        if self.guiPage == 'managechannel':
            return self.frame.managechannel

        if self.guiPage == 'playlist':
            return self.frame.playlist

        if self.guiPage == 'my_files':
            return self.frame.librarylist

    def SetTopSplitterWindow(self, window=None, show=True):
        while self.frame.splitter_top.GetChildren():
            self.frame.splitter_top.Detach(0)

        self.SetBottomSplitterWindow()
        if window:
            self.frame.splitter_top.Add(window, 1, wx.EXPAND)
            window.Show(show)
        self.frame.splitter.Show(show)
        self.frame.splitter_top.Layout()
        self.frame.splitter_top_window.Refresh()

    def SetBottomSplitterWindow(self, window=None, show=True):
        self.frame.splitter_bottom.Clear(True)
        if window:
            self.frame.splitter_bottom.Add(window, 1, wx.EXPAND | wx.ALIGN_TOP | wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
            self.frame.splitter_bottom_window.SetBackgroundColour(window.GetBackgroundColour())
        else:
            from __init__ import GRADIENT_LGREY
            self.frame.splitter_bottom_window.SetBackgroundColour(GRADIENT_LGREY)
        if self.guiPage != 'mychannel':
            self.frame.splitter.Show(show)
        self.frame.splitter_bottom.Layout()
        self.frame.splitter_bottom_window.Refresh()

    def SetColumnInfo(self, itemtype, columns, hide_defaults=[]):
        fileconfig = wx.FileConfig(appName="Tribler", localFilename=os.path.join(self.frame.utility.session.get_state_dir(), "gui_settings"))
        # Load hidden column info
        hide_columns = fileconfig.Read("hide_columns")
        hide_columns = json.loads(hide_columns) if hide_columns else {}
        hide_columns = hide_columns.get(itemtype.__name__, {})
        for index, column in enumerate(columns):
            if column['name'] in hide_columns:
                column['show'] = hide_columns[column['name']]
            else:
                column['show'] = not (index in hide_defaults)

        # Load column width info
        column_sizes = fileconfig.Read("column_sizes")
        column_sizes = json.loads(column_sizes) if column_sizes else {}
        column_sizes = column_sizes.get(itemtype.__name__, {})
        for index, column in enumerate(columns):
            if column['name'] in column_sizes:
                column['width'] = column_sizes[column['name']]

        return columns

    def ReadGuiSetting(self, setting_name, default=None, do_json=True):
        fileconfig = wx.FileConfig(appName="Tribler", localFilename=os.path.join(self.frame.utility.session.get_state_dir(), "gui_settings"))
        setting_value = fileconfig.Read(setting_name)
        if do_json and setting_value:
            setting_value = json.loads(setting_value)
        elif not setting_value:
            setting_value = default
        return setting_value

    def WriteGuiSetting(self, setting_name, setting_value, do_json=True):
        fileconfig = wx.FileConfig(appName="Tribler", localFilename=os.path.join(self.frame.utility.session.get_state_dir(), "gui_settings"))
        fileconfig.Write(setting_name, json.dumps(setting_value) if do_json else setting_value)
        fileconfig.Flush()

    @forceWxThread
    def GoBack(self, scrollTo=None, topage=None):
        if topage:
            self.oldpage.pop()
        else:
            if len(self.oldpage) > 0:
                topage = self.oldpage.pop()
            else:
                return

        if topage == 'search_results':
            self.frame.actlist.selectTab('results')
        elif topage in ['channels', 'selectedchannel', 'mychannel']:
            self.frame.actlist.selectTab('channels')
        else:
            self.frame.actlist.selectTab(topage)

        self.ShowPage(topage)
        self.oldpage.pop()  # remove curpage from history

        if scrollTo:
            self.ScrollTo(scrollTo)

    def dosearch(self, input=None):
        if input == None:
            sf = self.frame.top_bg.searchField
            if sf is None:
                return

            input = sf.GetValue()

        if input:
            input = input.strip()
            if input == '':
                return
        else:
            return
        self.frame.top_bg.searchField.SetValue(input)

        if input.startswith("http://"):
            if self.frame.startDownloadFromUrl(str(input)):
                self.frame.top_bg.searchField.Clear()
                self.ShowPage('my_files')

        elif input.startswith("magnet:"):
            if self.frame.startDownloadFromMagnet(str(input)):
                self.frame.top_bg.searchField.Clear()
                self.ShowPage('my_files')

        elif input.startswith(SWIFT_URL_SCHEME) or input.startswith("ppsp://"):
            if self.frame.startDownloadFromSwift(str(input)):
                self.frame.top_bg.searchField.Clear()
                self.ShowPage('my_files')

        else:
            keywords = split_into_keywords(input)
            keywords = [keyword for keyword in keywords if len(keyword) > 1]

            if len(keywords) == 0:
                self.Notify('Please enter a search term', "Your search term '%s' was either to small or to general." % input, icon=wx.ART_INFORMATION)

            else:
                self.frame.top_bg.StartSearch()
                self.current_search_query = keywords
                if DEBUG:
                    print >> sys.stderr, "GUIUtil: searchFiles:", keywords, time()

                self.frame.searchlist.Freeze()

                self.torrentsearch_manager.setSearchKeywords(keywords)
                self.channelsearch_manager.setSearchKeywords(keywords)

                # We set oldkeywords to '', which will trigger a reset in SetKeywords (called from ShowPage). This avoid calling reset twice.
                # Niels: 17-09-2012, unfortunately showpage calls show(true) which results in the dirty items being refreshed.
                # We need to call Reset in order to prevent this from happening
                self.frame.searchlist.Reset()
                self.ShowPage('search_results', keywords)

                # We now have to call thaw, otherwise loading message will not be shown.
                self.frame.searchlist.Thaw()

                # Peform local search
                self.torrentsearch_manager.set_gridmgr(self.frame.searchlist.GetManager())
                self.channelsearch_manager.set_gridmgr(self.frame.searchlist.GetManager())

                def db_thread():
                    self.torrentsearch_manager.refreshGrid()

                    nr_peers_connected = self.torrentsearch_manager.searchDispersy()
                    self.channelsearch_manager.searchDispersy()
                    return nr_peers_connected

                def wx_thread(delayedResult):
                    nr_peers_connected = delayedResult.get()

                    self.frame.searchlist.SetMaxResults(nr_peers_connected + 1, keywords)
                    self.frame.searchlist.NewResult()

                startWorker(wx_thread, db_thread, priority=1024)

    @forceWxThread
    def NewResult(self):
        self.frame.searchlist.NewResult()

    @forceWxThread
    def showChannelCategory(self, category, show=True):

        manager = self.frame.channellist.GetManager()
        manager.SetCategory(category, True)

        if show:
            self.ShowPage('channels')

    @forceWxThread
    def showLibrary(self, show=True):
        manager = self.frame.librarylist.GetManager()
        manager.do_or_schedule_refresh(True)

        if show:
            self.ShowPage('my_files')

    def showChannelFromId(self, channel_id):
        def db_callback():
            channel = self.channelsearch_manager.getChannel(channel_id)
            self.showChannel(channel)

        startWorker(None, db_callback, priority=GUI_PRI_DISPERSY)

    def showChannelFromDispCid(self, channel_cid):
        def db_callback():
            channel = self.channelsearch_manager.getChannelByCid(channel_cid)
            self.showChannel(channel)

        startWorker(None, db_callback, priority=GUI_PRI_DISPERSY)

    def showChannelFromPermid(self, channel_permid):
        def db_callback():
            channel = self.channelsearch_manager.getChannelByPermid(channel_permid)
            self.showChannel(channel)

        startWorker(None, db_callback, priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def showChannel(self, channel):
        if channel:
            manager = self.frame.selectedchannellist.GetManager()
            manager.refresh_if_required(channel)

            self.ShowPage('selectedchannel')

            if isinstance(channel, RemoteChannel):
                self.showChannelFromPermid(channel.permid)

    def showChannels(self):
        self.frame.actlist.selectTab('channels')
        self.ShowPage('channels')

    @forceWxThread
    def showChannelResults(self, data_channel):
        self.frame.actlist.selectTab('channels')

        def subscribe_latestupdate_sort(a, b):
            val = cmp(a.modified, b.modified)
            if val == 0:
                return cmp(a.name, b.name)
            return val

        data = data_channel.values()
        data.sort(subscribe_latestupdate_sort, reverse=True)

        manager = self.frame.channellist.GetManager()
        manager.SetCategory('searchresults')
        manager.refresh(data)

        self.ShowPage('channels')

    @forceWxThread
    def showManageChannel(self, channel):
        self.frame.managechannel.SetChannel(channel)
        self.ShowPage('managechannel')

    @forceWxThread
    def showPlaylist(self, data):
        self.frame.playlist.Set(data)
        self.ShowPage('playlist')

    def OnList(self, goto_end, event=None):
        lists = {'channels': self.frame.channellist, 'selectedchannel': self.frame.selectedchannellist, 'mychannel': self.frame.managechannel, 'search_results': self.frame.searchlist, 'my_files': self.frame.librarylist}
        if self.guiPage in lists and lists[self.guiPage].HasFocus():
            lists[self.guiPage].ScrollToEnd(goto_end)
        elif event:
            event.Skip()

    def ScrollTo(self, id):
        lists = {'channels': self.frame.channellist, 'selectedchannel': self.frame.selectedchannellist, 'mychannel': self.frame.managechannel, 'search_results': self.frame.searchlist, 'my_files': self.frame.librarylist}
        if self.guiPage in lists:
            lists[self.guiPage].ScrollToId(id)

    def Notify(self, title, msg='', icon=wx.ART_INFORMATION):
        if sys.platform == 'win32' and not self.frame.IsShownOnScreen():
            self.frame.tbicon.Notify(title, msg, icon)
        else:
            if isinstance(icon, basestring):
                icon = wx.ArtProvider.GetBitmap(icon, wx.ART_FRAME_ICON) or \
                    wx.Bitmap(os.path.join(self.utility.getPath(), LIBRARYNAME, "Main", "vwxGUI", "images", "notify_%s.png" % icon), wx.BITMAP_TYPE_ANY)
            self.frame.actlist.Notify(msg or title, icon)

    def ShouldGuiUpdate(self):
        if self.frame.ready:
            return self.frame.GUIupdate
        return True

    def addList(self, l):
        if l not in self.lists:
            self.lists.append(l)

    def toggleFamilyFilter(self, newState=None, setCheck=False):
        if newState == None:
            newState = not self.getFamilyFilter()

        Category.getInstance().set_family_filter(newState)
        for l in self.lists:
            if getattr(l, 'GotFilter', False):
                l.GotFilter(None)

        if setCheck:
            self.frame.SRstatusbar.ff_checkbox.SetValue(newState)

        if newState:
            self.utility.config.Write('family_filter', '1')
        else:
            self.utility.config.Write('family_filter', '0')
        self.utility.config.Flush()

    def getFamilyFilter(self):
        catobj = Category.getInstance()
        return catobj.family_filter_enabled()

    def set_firewall_restart(self, b):
        self.firewall_restart = b

    @forceWxThread
    def MarkAsFavorite(self, event, channel):
        if channel:
            if event:
                button = event.GetEventObject()
                button.Enable(False)
                if hasattr(button, 'selected'):
                    button.selected = False

            dlgname = 'MFdialog'
            if not self.ReadGuiSetting('show_%s' % dlgname, default=True):
                response = wx.ID_OK
            else:
                from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
                dlg = ConfirmationDialog(None, dlgname, "You are about to add \'%s\' to your list of favourite channels." % channel.name,
                                         "If you mark this channel as your favourite, you will be able to access its full content.")
                response = dlg.ShowModal()

            if response == wx.ID_OK:
                @forcePrioDBThread
                def add_vote():
                    self.channelsearch_manager.favorite(channel.id)
                    wx.CallAfter(self.Notify, "Channel marked as favourite", "Marked channel '%s' as favourite" % channel.name, icon='favourite')
                    if event:
                        button.Enable(True)
                    UserEventLogDBHandler.getInstance().addEvent(message="User marked a channel as favorite", type=2)
                    self.RefreshChannel(channel.id)
                add_vote()
            elif event:
                button.Enable(True)

    @forceWxThread
    def RemoveFavorite(self, event, channel):
        if channel:
            if event:
                button = event.GetEventObject()
                button.Enable(False)
                if hasattr(button, 'selected'):
                    button.selected = False

            dlgname = 'RFdialog'
            if not self.ReadGuiSetting('show_%s' % dlgname, default=True):
                response = wx.ID_OK
            else:
                from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
                dlg = ConfirmationDialog(None, dlgname, "You are about to remove \'%s\' from your list of favourite channels." % channel.name,
                                         "If you remove this channel from your favourites, you will no longer be able to access its full content.")
                response = dlg.ShowModal()

            if response == wx.ID_OK:
                @forcePrioDBThread
                def remove_vote():
                    self.channelsearch_manager.remove_vote(channel.id)
                    wx.CallAfter(self.Notify, "Channel removed from favourites", "Removed channel '%s' from your favourites" % channel.name, icon='favourite')
                    if event:
                        button.Enable(True)
                    self.RefreshChannel(channel.id)
                remove_vote()
            elif event:
                button.Enable(True)

    @forceWxThread
    def MarkAsSpam(self, event, channel):
        if channel:
            if event:
                button = event.GetEventObject()
                button.Enable(False)
                if hasattr(button, 'selected'): button.selected = False

            dlgname = 'MSdialog'
            if not self.ReadGuiSetting('show_%s' % dlgname, default = True):
                response = wx.ID_OK
            else:
                from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
                dlg = ConfirmationDialog(None, dlgname, "You are about to report channel \'%s\' as spam." % channel.name, "")
                response = dlg.ShowModal()

            if response == wx.ID_OK:
                @forcePrioDBThread
                def remove_vote():
                    self.channelsearch_manager.spam(channel.id)
                    wx.CallAfter(self.Notify, "Channel marked as spam", "Channel '%s' marked as spam" % channel.name)
                    if event: button.Enable(True)
                    self.RefreshChannel(channel.id)
                remove_vote()
            elif event:
                button.Enable(True)

    @forceWxThread
    def RemoveSpam(self, event, channel):
        if channel:
            if event:
                button = event.GetEventObject()
                button.Enable(False)
                if hasattr(button, 'selected'): button.selected = False

            dlgname = 'RSdialog'
            if not self.ReadGuiSetting('show_%s' % dlgname, default = True):
                response = wx.ID_OK
            else:
                from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
                dlg = ConfirmationDialog(None, dlgname, "You are about unmark channel \'%s\' as spam." % channel.name, "")
                response = dlg.ShowModal()

            if response == wx.ID_OK:
                @forcePrioDBThread
                def remove_vote():
                    self.channelsearch_manager.remove_vote(channel.id)
                    wx.CallAfter(self.Notify, "Channel unmarked as spam", "Channel '%s' unmarked as spam" % channel.name)
                    if event: button.Enable(True)
                    self.RefreshChannel(channel.id)
                remove_vote()
            elif event:
                button.Enable(True)

    def RefreshChannel(self, channelid):
        if self.guiPage in ['search_results', 'selectedchannel', 'channels']:

            list = self.GetSelectedPage()
            if self.guiPage == 'search_results':
                list.GetManager().refresh_partial(channelids=[channelid])
            else:
                list.GetManager().refresh_partial((channelid,))

            if self.guiPage == 'selectedchannel':
                wx.CallAfter(list.GetManager().reload, channelid)
