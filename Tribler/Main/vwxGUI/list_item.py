# Written by Niels Zeilemaker, Egbert Bouman
import wx
import os
import sys
import json
import shutil
import urllib
import logging
import binascii
from datetime import timedelta

from Tribler.Core.simpledefs import (DOWNLOAD, UPLOAD, DLSTATUS_METADATA, DLSTATUS_HASHCHECKING,
                                     DLSTATUS_WAITING4HASHCHECK)
from Tribler.Core.osutils import startfile
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread

from Tribler.Main.vwxGUI import (warnWxThread, GRADIENT_DGREY, SEPARATOR_GREY, LIST_AT_HIGHLIST, LIST_SELECTED,
                                 LIST_EXPANDED, format_time, LIST_DARKBLUE, LIST_DESELECTED, THUMBNAIL_FILETYPES)
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice
from Tribler.Main.vwxGUI.widgets import _set_font, TagText, ActionButton, ProgressButton, MaxBetterText, FancyPanel
from Tribler.Main.vwxGUI.list_body import ListItem
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager, SMALL_ICON_MAX_DIM
from Tribler.Main.Utility.GuiDBTuples import Torrent, CollectedTorrent

from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Core.Video.VideoUtility import limit_resolution
from Tribler.Core.TorrentDef import TorrentDef

from Tribler.Main.Utility.utility import round_range


class ColumnsManager:
    __single = None

    def __init__(self):
        if ColumnsManager.__single:
            raise RuntimeError("ColumnsManager is singleton")
        ColumnsManager.__single = self
        self.defaults = {}

    def getInstance(*args, **kw):
        if ColumnsManager.__single is None:
            ColumnsManager(*args, **kw)
        return ColumnsManager.__single
    getInstance = staticmethod(getInstance)

    def setColumns(self, itemtype, columns):
        self.defaults[itemtype.__name__] = columns

    def getColumns(self, itemtype):
        return self.defaults.get(itemtype.__name__, [])


class DoubleLineListItem(ListItem):

    def __init__(self, *args, **kwargs):
        self.guiutility = GUIUtility.getInstance()
        ListItem.__init__(self, *args, **kwargs)

        self._logger = logging.getLogger(self.__class__.__name__)

    @warnWxThread
    def AddComponents(self, leftSpacer, rightSpacer):
        if leftSpacer > 0:
            self.hSizer.AddSpacer((leftSpacer, -1))

        self.icons = self.GetIcons()
        if self.icons:
            iconSizer = wx.BoxSizer(wx.VERTICAL)
            for index, icon in enumerate(self.icons):
                if icon:
                    bmp = ActionButton(self, bitmap=icon[0], hover=False)
                    bmp.SetBitmapDisabled(icon[1] or icon[0])
                    bmp.SetBitmapHover(icon[1] or icon[0])
                    bmp.SetToolTipString(icon[2])
                    bmp.Bind(wx.EVT_LEFT_UP, icon[3] if len(icon) > 3 else None)
                    bmp.Show(icon[4] if len(icon) > 4 else True)
                    if index < len(self.icons) - 1:
                        iconSizer.Add(bmp, 0, wx.CENTER | wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.BOTTOM, 7)
                    else:
                        iconSizer.Add(bmp, 0, wx.CENTER | wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
                    self.icons[index] = bmp
            iconSizer.AddSpacer((33, -1))
            self.hSizer.Add(iconSizer, 0, wx.ALIGN_CENTER_VERTICAL)
        else:
            self.hSizer.AddSpacer((33, -1))

        self.titleSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.descrSizer = wx.BoxSizer(wx.HORIZONTAL)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.titleSizer, 0, wx.TOP | wx.BOTTOM | wx.EXPAND, 3)
        vSizer.Add(self.descrSizer, 0, wx.TOP | wx.BOTTOM, 3)
        self.hSizer.Add(vSizer, 1, wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.CENTER | wx.TOP | wx.BOTTOM | wx.EXPAND, 3)

        ListItem.AddComponents(self, 0, rightSpacer)

        # remove last line
        nrchildren = len(self.descrSizer.GetChildren())
        if nrchildren > 0:
            lastline = self.descrSizer.GetItem(nrchildren - 1)
            lastline.Show(False)
            self.descrSizer.Detach(nrchildren - 1)

        else:
            vSizer.Detach(self.descrSizer)
            self.descrSizer = None

    def _add_control(self, control, column_index, option, spacing):
        if column_index == 0:
            self.titleSizer.Add(control, 1, wx.CENTER)

            if getattr(control, 'icon', None):
                # Remove the spacer and replace it with the icon
                self.hSizer.Remove(0)
                self.hSizer.Insert(
                    0,
                    control.icon,
                    0,
                    wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT,
                    (33 - control.icon.GetSize().x) / 2)
        else:
            self.descrSizer.Add(control, 0, wx.CENTER | wx.TOP, spacing)

            if column_index >= 0:
                sline = wx.StaticLine(self, -1, style=wx.LI_VERTICAL)
                if sys.platform == 'win32':
                    self._add_columnresizing(sline, column_index)
                self.descrSizer.Add(sline, 0, wx.EXPAND | wx.RIGHT | wx.LEFT, 7)

    def _add_columnresizing(self, sline, column_index):
        sline.SetCursor(wx.StockCursor(wx.CURSOR_SIZEWE))
        # Take hidden columns into account
        control_index = self.columns[column_index]['controlindex']

        def OnLeftDown(event):
            eo = event.GetEventObject()
            eo.CaptureMouse()
            eo.Unbind(wx.EVT_ENTER_WINDOW)
            eo.Unbind(wx.EVT_LEAVE_WINDOW)
            eo.Bind(wx.EVT_MOTION, OnMotion)

        def OnMotion(event, control_index=control_index):
            control = self.controls[control_index]
            mouse_x = event.GetPosition().x
            width = max(0, control.GetSize().x + mouse_x)
            if getattr(self, 'buttonSizer', False):
                width = min(width, self.buttonSizer.GetPosition().x - self.descrSizer.GetPosition().x - sum(
                    [child.GetSize().x for child in self.descrSizer.GetChildren()]) + control.GetSize().x)
            else:
                pass
            control.SetMinSize((width, -1))
            self.hSizer.Layout()

        def OnLeftUp(event, column_index=column_index, control_index=control_index):
            eo = event.GetEventObject()
            eo.ReleaseMouse()
            eo.Bind(wx.EVT_ENTER_WINDOW, self.OnMouse)
            eo.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouse)
            eo.Unbind(wx.EVT_MOTION)
            self.columns[column_index]['width'] = self.controls[control_index].GetSize().x

            # If we are dealing with a control with a label in front of it, we need to
            # add the width of the label to the column width.
            if self.columns[column_index].get('showColumname', True) and \
               self.columns[column_index].get('name', False) and \
               self.columns[column_index].get('type', '') == 'method':
                for index, child in enumerate(self.descrSizer.GetChildren()):
                    if child.IsWindow() and child.GetWindow() == self.controls[control_index]:
                        if index > 1:
                            self.columns[column_index]['width'] += self.descrSizer.GetChildren()[index - 1].GetSize().x
                        break

            column_sizes = self.guiutility.ReadGuiSetting("column_sizes", default={})
            column_sizes[type(self).__name__] = column_sizes.get(type(self).__name__, {})
            column_sizes[type(self).__name__].update(
                {self.columns[column_index]['name']: self.columns[column_index]['width']})
            self.guiutility.WriteGuiSetting("column_sizes", column_sizes)

            def rebuild():
                if hasattr(self.parent_list.parent_list, 'oldDS'):
                    self.parent_list.parent_list.oldDS = {}
                self.parent_list.Rebuild()

            wx.CallAfter(rebuild)

        sline.Bind(wx.EVT_LEFT_DOWN, OnLeftDown)
        sline.Bind(wx.EVT_LEFT_UP, OnLeftUp)

    def _replace_control(self, columnindex, newcontrol):
        oldcontrol = self.controls[columnindex]
        if columnindex == 0:
            self.titleSizer.Replace(oldcontrol, newcontrol)
        else:
            self.descrSizer.Replace(oldcontrol, newcontrol)
            newcontrol.SetMinSize(oldcontrol.GetMinSize())

        if isinstance(oldcontrol, wx.Sizer):
            oldcontrol.ShowItems(False)
            oldcontrol.DeleteWindows()
            oldcontrol.Destroy()
        else:
            oldcontrol.Show(False)
            oldcontrol.Destroy()

    @warnWxThread
    def RefreshData(self, data):
        ListItem.RefreshData(self, data)

        new_icons = self.GetIcons()
        for index, new_icon in enumerate(new_icons):
            if new_icon and (new_icon[0].ConvertToImage().GetData() != self.icons[index].GetBitmapLabel().ConvertToImage().GetData() or
                             new_icon[2] != self.icons[index].GetToolTip().GetTip()):
                self.icons[index].SetBitmapLabel(new_icon[0])
                self.icons[index].SetBitmapDisabled(new_icon[1] or new_icon[0])
                self.icons[index].SetBitmapHover(new_icon[1] or new_icon[0])
                self.icons[index].SetToolTipString(new_icon[2])
                self.icons[index].Bind(wx.EVT_LEFT_UP, new_icon[3] if len(new_icon) > 3 else None)
                self.icons[index].Enable(True)
                self.icons[index].Show(True)
            elif not new_icon and self.icons[index]:
                self.icons[index].Show(False)

    @warnWxThread
    def OnRightClick(self, event=None):
        mousepos = wx.GetMousePosition()
        if not self.expanded:
            self.OnClick(event)

        def do_menu():
            menu = self.GetContextMenu()
            if menu:
                self.PopupMenu(menu, self.ScreenToClient(mousepos))
                menu.Destroy()
        wx.CallLater(200, do_menu)

    @warnWxThread
    def OnShowColumn(self, event, index):
        self.columns[index]['show'] = not self.columns[index].get('show', True)

        hide_columns = self.guiutility.ReadGuiSetting("hide_columns", default={})
        hide_columns[type(self).__name__] = hide_columns.get(type(self).__name__, {})
        hide_columns[type(self).__name__].update({self.columns[index]['name']: self.columns[index]['show']})
        self.guiutility.WriteGuiSetting("hide_columns", hide_columns)

        if getattr(self.parent_list.parent_list, 'ResetBottomWindow', False):
            self.parent_list.parent_list.ResetBottomWindow()
        wx.CallAfter(self.parent_list.Rebuild)

    @warnWxThread
    def GetContextMenu(self):
        menu = wx.Menu()
        self.GetSubMenu([{'title': 'Show labels..',
                          'handler': [{'title': c['name'], 'type': 'check', 'enable': c['name'] != 'Name', 'check': c.get('show', True),
                                       'handler': lambda e, i=i: self.OnShowColumn(e, i)} for i, c in enumerate(self.columns)]}], menu)
        return menu

    def GetSubMenu(self, items, submenu=None):
        submenu = submenu or wx.Menu()
        for item in items:
            if not item:
                submenu.AppendSeparator()
                continue

            title = item['title']
            itemtype = item.get('type', '')
            enable = item.get('enable', None)
            check = item.get('check', None)
            updateui = item.get('updateui', None)
            handler = item.get('handler', None)

            if isinstance(handler, list):
                itemid = wx.NewId()
                submenu.AppendMenu(itemid, title, self.GetSubMenu(handler))
            else:
                itemid = wx.NewId()
                if itemtype == 'check':
                    submenu.AppendCheckItem(itemid, title)
                else:
                    submenu.Append(itemid, title)
                wx.EVT_MENU(self, itemid, handler)

            if updateui is not None:
                wx.EVT_UPDATE_UI(self, itemid, updateui)

            if isinstance(enable, bool):
                submenu.Enable(itemid, enable)

            if itemtype == 'check' and isinstance(check, bool):
                submenu.Check(itemid, check)

        return submenu

    @warnWxThread
    def GetIcons(self):
        if getattr(self.parent_list.parent_list, '_special_icon', None):
            return [self.parent_list.parent_list._special_icon(self)]
        else:
            return []


class DoubleLineListItemWithButtons(DoubleLineListItem):

    def AddComponents(self, *args, **kwargs):
        DoubleLineListItem.AddComponents(self, *args, **kwargs)

        self.buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer.Add(self.buttonSizer, 0, wx.CENTER | wx.TOP | wx.BOTTOM | wx.EXPAND, 3)
        self.hide_buttons = True
        self.AddButtons()

    def AddButtons(self):
        pass

    def AddButton(self, label, handler, right_spacer=10):
        if handler is None or label is None:
            return

        button = ProgressButton(self, -1, label)
        button.Bind(wx.EVT_LEFT_UP, handler)
        self.AddEvents(button)
        self.buttonSizer.Add(button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, right_spacer)
        self.Layout()
        self.ShowSelected()
        return button

    def ShowSelected(self):
        if not self:
            return

        DoubleLineListItem.ShowSelected(self)

        if self.hide_buttons and self.GetBackgroundColour() == self.list_deselected:
            self.buttonSizer.ShowItems(False)
        else:
            self.buttonSizer.ShowItems(True)
        self.Layout()

    def SetHideButtons(self, val):
        self.hide_buttons = val
        self.ShowSelected()


class TorrentListItem(DoubleLineListItemWithButtons):

    def __init__(self, *args, **kwargs):
        self.plbutton = None
        self.dlbutton = None
        DoubleLineListItem.__init__(self, *args, **kwargs)
        self.SetThumbnailIcon()

    def AddButtons(self):
        self.buttonSizer.Clear(deleteWindows=True)

        do_add = False
        for column in self.columns:
            if column.get('name', None) == 'Name':
                do_add = column.get('dlbutton', False)
                break

        if do_add:
            self.plbutton = self.AddButton(
                "Stream",
                lambda evt: self.guiutility.library_manager.playTorrent(
                    self.original_data.infohash))
            self.dlbutton = self.AddButton(
                "Download",
                lambda evt: self.guiutility.frame.top_bg.OnDownload(evt,
                                                                    [self.original_data]))
            self.dlbutton.Enable(
                'completed' not in self.original_data.state and 'active' not in self.original_data.state)

    def SetCollectedTorrent(self, coltorrent):
        if self.plbutton:
            self.plbutton.Enable(coltorrent.isPlayable() if coltorrent else True)

    @warnWxThread
    def GetIcons(self):
        if getattr(self.parent_list.parent_list, '_status_icon', None):
            return [self.parent_list.parent_list._status_icon(self)]
        else:
            return []

    @warnWxThread
    def RefreshData(self, data):
        DoubleLineListItem.RefreshData(self, data)
        self.SetThumbnailIcon()
        if self.dlbutton:
            self.dlbutton.Enable(
                'completed' not in self.original_data.state and 'active' not in self.original_data.state)

    def SetThumbnailIcon(self):
        torcoldir = self.guiutility.utility.session.get_torrent_collecting_dir()
        rel_thumbdir = binascii.hexlify(self.original_data.infohash)
        abs_thumbdir = os.path.join(torcoldir, rel_thumbdir)
        has_thumbnails = os.path.exists(abs_thumbdir) and os.listdir(abs_thumbdir)

        if has_thumbnails and not getattr(self, 'snapshot', None):
            # Override the settings flags set by AddComponents
            if sys.platform == 'darwin':
                # on Mac OS X (10.8), the GetBestSize() returns a very small size that is
                # not suitable for the title text, so we get the size through ClientDC
                cdc = wx.ClientDC(self.controls[0])
                cdc.SetFont(self.controls[0].GetFont())
                w, _ = cdc.GetTextExtent(self.controls[0].GetLabel())
                self.controls[0].SetMinSize((w, -1))
            else:
                self.controls[0].SetMinSize(self.controls[0].GetBestSize())
            self.titleSizer.Detach(self.controls[0])
            self.titleSizer.Insert(0, self.controls[0], 0, wx.CENTER)

            # Add icon right after the torrent title, indicating that the torrent has thumbnails
            snapshot_bmp = GuiImageManager.getInstance().getImage(u"snapshot.png")
            self.snapshot = wx.StaticBitmap(self, -1, snapshot_bmp)
            self.snapshot.SetToolTipString("This torrent has thumbnails.")
            self.AddEvents(self.snapshot)
            self.titleSizer.Add(self.snapshot, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT | wx.LEFT, 10)
            self.Layout()

            # Avoid errors related to PyDeadObject
            def refresh():
                if self:
                    self.Refresh()
            wx.CallAfter(refresh)

    @warnWxThread
    def GetContextMenu(self):
        menu = DoubleLineListItem.GetContextMenu(self)

        self.GetSubMenu(
            [{'title': 'Show download button on hover', 'type': 'check', 'updateui': self.CanShowHover, 'handler': self.OnShowHover},
             None,
             {'title': 'Force start', 'updateui': self.CanForceStart, 'handler': self.OnForceStart},
             {'title': 'Start', 'updateui': self.CanStart, 'handler': self.OnStart},
             {'title': 'Stop', 'updateui': self.CanStop, 'handler': self.OnStop},
             None,
             {'title': 'Remove download', 'updateui': self.CanRemove, 'handler': self.OnRemove},
             {'title': 'Remove download + data',
                       'updateui': self.CanRemoveAll,
                       'handler': self.OnRemoveAll},
             None,
             {'title': 'Force recheck', 'updateui': self.CanRecheck, 'handler': self.OnRecheck},
             None,
             {'title': 'Bandwidth allocation..', 'updateui': self.CanAllocateBandwidth, 'handler': []},
             None,
             {'title': 'Export torrent..',
                       'updateui': self.CanExportTorrent,
                       'handler': self.OnExportTorrent},
             {'title': 'Copy magnet link', 'updateui': self.CanCopyMagnet, 'handler': self.OnCopyMagnet},
             {'title': 'Add to my channel',
                       'updateui': self.CanAddToMyChannel,
                       'handler': self.OnAddToMyChannel},
             None,
             {'title': 'Explore files', 'updateui': self.CanExplore, 'handler': self.OnExplore},
             {'title': 'Change download location..', 'updateui': self.CanMove, 'handler': self.OnMove}], menu)

        bw_alloc = menu.FindItemById(menu.FindItem('Bandwidth allocation..')).GetSubMenu()
        download = self.original_data.ds.get_download() if self.original_data.ds else None
        if download:
            bw_alloc.AppendMenu(wx.ID_ANY, 'Set download limit..', self.CreateBandwidthMenu(download, DOWNLOAD, menu))
            bw_alloc.AppendMenu(wx.ID_ANY, 'Set upload limit..', self.CreateBandwidthMenu(download, UPLOAD, menu))

        return menu

    def CreateBandwidthMenu(self, download, direction, parent_menu):
        result = wx.Menu()

        limit = download.get_max_speed(direction)

        values = round_range(limit) if limit > 0 else range(0, 1000, 100)
        if limit > 0 and limit not in values:
            values.append(limit)
            values.sort(cmp=lambda x, y: cmp(int(x), int(y)))
        if 0 in values:
            values.remove(0)
        values.append(0)

        for value in values:
            itemid = wx.NewId()
            result.AppendRadioItem(itemid, str(value) if value > 0 else 'unlimited')
            if sys.platform == 'win32':
                parent_menu.Bind(
                    wx.EVT_MENU,
                    lambda x,
                    value=value: download.set_max_speed(
                        direction,
                        value),
                    id=itemid)
            else:
                result.Bind(wx.EVT_MENU, lambda x, value=value: download.set_max_speed(direction, value), id=itemid)
            result.Check(itemid, limit == value)

        return result

    def OnShowHover(self, event):
        show = not bool(len(self.buttonSizer.GetChildren()))
        for column in self.columns:
            if column.get('name', None) == 'Name':
                column['dlbutton'] = show
                break

        for item in self.parent_list.items.values():
            if isinstance(item, TorrentListItem):
                item.AddButtons()

        self.guiutility.WriteGuiSetting("hide_buttons", not show)

    def OnForceStart(self, event):
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            self.guiutility.library_manager.resumeTorrent(torrent, force_seed=True)

    def OnStart(self, event):
        self.guiutility.frame.top_bg.OnDownload()

    def OnStop(self, event):
        self.guiutility.frame.top_bg.OnStop()

    def OnRemove(self, event):
        wx.CallAfter(lambda: self.guiutility.frame.top_bg.OnDelete(silent=True, delete=False))

    def OnRemoveAll(self, event):
        wx.CallAfter(lambda: self.guiutility.frame.top_bg.OnDelete(silent=True, delete=True))

    def OnRecheck(self, event):
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            if torrent.download_state and 'metadata' not in torrent.state and 'checking' not in torrent.state:
                torrent.download_state.get_download().force_recheck()

    def OnExportTorrent(self, filename):
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        if len(torrents) == 1:
            torrent_data = self.guiutility.utility.session.get_collected_torrent(torrents[0].infohash)
            dlg = wx.FileDialog(
                None,
                message="Select an export destination",
                defaultFile="%s.torrent" % torrents[0].name,
                wildcard="*.torrent",
                style=wx.FD_SAVE | wx.CHANGE_DIR | wx.OVERWRITE_PROMPT)
            dlg.SetDirectory(DefaultDownloadStartupConfig.getInstance().get_dest_dir())
            if dlg.ShowModal() == wx.ID_OK:
                paths = dlg.GetPaths()
                if os.path.exists(paths[0]):
                    os.remove(paths[0])

                with open(paths[0], "wb") as f:
                    f.write(torrent_data)
            dlg.Destroy()

        elif len(torrents) > 1:
            dlg = wx.DirDialog(None, "Choose where to move the selected torrent(s)", style=wx.DEFAULT_DIALOG_STYLE)
            dlg.SetPath(DefaultDownloadStartupConfig.getInstance().get_dest_dir())
            if dlg.ShowModal() == wx.ID_OK:
                path = dlg.GetPath()
                for torrent in torrents:
                    torrent_data = self.guiutility.utility.session.get_collected_torrent(torrent.infohash)
                    dst_filename = os.path.join(path, "%s.torrent" % torrent.name)
                    if os.path.exists(dst_filename):
                        os.remove(dst_filename)

                    with open(dst_filename, "wb") as f:
                        f.write(torrent_data)
            dlg.Destroy()

    def OnCopyMagnet(self, event):
        magnetlinks = ''
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            magnetlink = "magnet:?xt=urn:btih:" + binascii.hexlify(torrent.infohash)
            trackers = self.guiutility.channelsearch_manager.torrent_db.getTrackerListByTorrentID(torrent.torrent_id)
            if trackers:
                for tracker in trackers:
                    if tracker != 'DHT':
                        magnetlink += "&tr=" + urllib.quote_plus(tracker)
            magnetlinks += magnetlink + '\n'

        if wx.TheClipboard.Open():
            magnetlinkObj = wx.TextDataObject()
            magnetlinkObj.SetText(magnetlinks)
            wx.TheClipboard.SetData(magnetlinkObj)
            wx.TheClipboard.Close()
        else:
            wx.MessageBox("Unable to copy magnet link to clipboard", "Error")

    @forceDBThread
    def OnAddToMyChannel(self, event):
        added = []
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            if self.guiutility.channelsearch_manager.createTorrent(None, torrent):
                added.append(torrent)

        if added:
            # remote channel link to force reload
            for torrent in added:
                del torrent.channel
                torrent.channel

            if len(added) == 1:
                def gui_call():
                    self.guiutility.Notify(
                        'New torrent added to My Channel',
                        "Torrent '%s' has been added to My Channel" %
                        self.original_data.name,
                        icon=wx.ART_INFORMATION)
            else:
                def gui_call():
                    self.guiutility.Notify(
                        'New torrents added to My Channel',
                        "%d Torrents have been added to My Channel" % len(added),
                        icon=wx.ART_INFORMATION)

            wx.CallAfter(gui_call)

    def OnExplore(self, event):
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            path = None
            if torrent.ds:
                download = torrent.ds.get_download()
                if isinstance(download.get_def(), TorrentDef):
                    destdirs = torrent.ds.get_download().get_dest_files()
                    path = os.path.commonprefix([os.path.split(path)[0] for _, path in destdirs])
                    if path and os.path.exists(path):
                        startfile(path)
                    else:
                        path = DefaultDownloadStartupConfig.getInstance().get_dest_dir()
                        startfile(path)

    def OnMove(self, event):
        items = self.guiutility.frame.librarylist.GetExpandedItems()
        torrents = [item[1].original_data for item in items if isinstance(
                    item[1].original_data,
                    Torrent) or isinstance(item[1].original_data,
                                           CollectedTorrent)]

        dlg = wx.DirDialog(None, "Choose where to move the selected torrent(s)", style=wx.DEFAULT_DIALOG_STYLE)
        dlg.SetPath(self.original_data.ds.get_download().get_dest_dir())
        if dlg.ShowModal() == wx.ID_OK:
            new_dir = dlg.GetPath()
            for torrent in torrents:
                if torrent.ds:
                    self._MoveDownload(torrent.ds, new_dir)

    def _MoveDownload(self, download_state, new_dir):
        def rename_or_merge(old, new):
            if os.path.exists(old):
                if os.path.exists(new):
                    files = os.listdir(old)
                    for file in files:
                        oldfile = os.path.join(old, file)
                        newfile = os.path.join(new, file)

                        if os.path.isdir(oldfile):
                            self.rename_or_merge(oldfile, newfile)

                        elif os.path.exists(newfile):
                            os.remove(newfile)
                            shutil.move(oldfile, newfile)
                        else:
                            shutil.move(oldfile, newfile)
                else:
                    os.renames(old, new)

        destdirs = download_state.get_download().get_dest_files()
        if len(destdirs) > 1:
            old = os.path.commonprefix([os.path.split(path)[0] for _, path in destdirs])
            _, old_dir = new = os.path.split(old)
            new = os.path.join(new_dir, old_dir)
        else:
            old = destdirs[0][1]
            _, old_file = os.path.split(old)
            new = os.path.join(new_dir, old_file)

        self._logger.info("Creating new downloadconfig")

        # Move torrents
        storage_moved = False

        download = download_state.get_download()
        self._logger.info("Moving from %s to %s newdir %s", old, new, new_dir)
        download.move_storage(new_dir)
        if download.get_save_path() == new_dir:
            storage_moved = True

        # If libtorrent hasn't moved the files yet, move them now
        if not storage_moved:
            self._logger.info("Moving from %s to %s newdir %s", old, new, new_dir)
            movelambda = lambda: rename_or_merge(old, new)
            self.guiutility.utility.session.lm.rawserver.add_task(movelambda, 0.0)

    def OnDClick(self, event):
        self.guiutility.frame.top_bg.OnDownload(None, [self.original_data])

    def CanShowHover(self, event):
        enable = not isinstance(self, LibraryListItem)
        check = bool(len(self.buttonSizer.GetChildren()))
        event.Enable(enable)
        event.Check(enable and check)

    def CanForceStart(self, event):
        enable = True
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            if 'completed' in torrent.state or 'seeding' in torrent.state:
                tdef = torrent.ds.get_download().get_def() if torrent.ds else None
                if tdef:
                    if UserDownloadChoice.get_singleton().get_download_state(tdef.get_infohash()) == 'restartseed':
                        enable = False
                        break
        event.Enable(enable)

    def CanStart(self, event):
        event.Enable(self.guiutility.frame.top_bg.upload_btn.IsEnabled() or
                     self.guiutility.frame.top_bg.download_btn.IsEnabled())

    def CanStop(self, event):
        event.Enable(self.guiutility.frame.top_bg.stop_btn.IsEnabled())

    def CanRemove(self, event):
        event.Enable(self.guiutility.frame.top_bg.delete_btn.IsEnabled())

    def CanRemoveAll(self, event):
        event.Enable(self.guiutility.frame.top_bg.delete_btn.IsEnabled())

    def CanRecheck(self, event):
        enable = False
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            status = torrent.download_state.get_status() if torrent.download_state else None
            if status not in [None, DLSTATUS_METADATA, DLSTATUS_HASHCHECKING, DLSTATUS_WAITING4HASHCHECK]:
                enable = True
                break
        event.Enable(enable)

    def CanAllocateBandwidth(self, event):
        enable = False
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            download = torrent.ds.get_download() if torrent.ds else None
            if download:
                enable = True
                break
        event.Enable(enable)

    def CanExplore(self, event):
        enable = False
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            if torrent.state:
                enable = True
                break
        event.Enable(enable)

    def CanExportTorrent(self, event):
        enable = False
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            if self.guiutility.utility.session.has_collected_torrent(torrent.infohash):
                enable = True
                break
        event.Enable(enable)

    def CanCopyMagnet(self, event):
        enable = False
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            download = torrent.ds.get_download() if torrent.ds else None
            if download:
                enable = True
                break
        event.Enable(enable)

    def CanAddToMyChannel(self, event):
        enable = False
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            if 'seeding' in torrent.state:
                enable = True
                break
        event.Enable(enable)

    def CanMove(self, event):
        enable = False
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        # Only support moving 1 download at a time
        if len(torrents) == 1 and torrents[0].infohash and 'active' in torrents[0].state:
            enable = True
        event.Enable(enable)


class ChannelListItem(DoubleLineListItemWithButtons):

    def __init__(self, *args, **kwargs):
        DoubleLineListItemWithButtons.__init__(self, *args, **kwargs)
        self.last_my_vote = None

    def AddComponents(self, *args, **kwargs):
        DoubleLineListItemWithButtons.AddComponents(self, *args, **kwargs)

        tag = TagText(self, -1, label='channel', fill_colour=wx.Colour(210, 252, 120))
        self.AddEvents(tag)
        self.titleSizer.Insert(0, tag, 0, wx.CENTER | wx.TOP, 2)
        self.titleSizer.Insert(1, (5, -1), 0, 0)

    def AddButtons(self):
        self.buttonSizer.Clear(deleteWindows=True)
        from Tribler.Main.vwxGUI.list import GenericSearchList
        from Tribler.Main.vwxGUI.list_header import BaseFilter
        if not isinstance(self.parent_list.parent_list, BaseFilter):
            self.AddButton("Visit channel", lambda evt: self.guiutility.showChannel(self.original_data))
        if not isinstance(self.parent_list.parent_list, GenericSearchList):
            if self.original_data.my_vote == 2:
                self.AddButton(
                    "Remove Favorite",
                    lambda evt,
                    data=self.original_data: self.guiutility.RemoveFavorite(
                        evt,
                        data))
            elif not self.original_data.isMyChannel():
                self.AddButton(
                    "Mark as Favorite",
                    lambda evt,
                    data=self.original_data: self.guiutility.MarkAsFavorite(
                        evt,
                        data))
            self.last_my_vote = self.original_data.my_vote

    @warnWxThread
    def RefreshData(self, data):
        DoubleLineListItemWithButtons.RefreshData(self, data)

        if self.last_my_vote != data[2].my_vote:
            self.AddButtons()

    def GetIcons(self):
        return [self.guiutility.frame.channellist._special_icon(self)]

    def OnDClick(self, event=None):
        self.guiutility.showChannel(self.original_data)

    @warnWxThread
    def SetTitleSizerHeight(self, height):
        self.titleSizer.AddSpacer((-1, height))


class ChannelListItemAssociatedTorrents(ChannelListItem):

    def __init__(self, *args, **kwargs):
        self.at_index = -1
        ChannelListItem.__init__(self, *args, **kwargs)

    def AddComponents(self, *args, **kwargs):
        DoubleLineListItemWithButtons.AddComponents(self, *args, **kwargs)

        visible_columns = [column['name'] for column in self.columns if column['show']]
        try:
            self.at_index = visible_columns.index('Associated torrents')
            self.controls[self.at_index].SetToolTipString(
                'This channel contains %d torrents matching your search query. The visible matches are currently highlighted.' %
                len(self.data[-1]))
            self.controls[self.at_index].Bind(wx.EVT_MOUSE_EVENTS, self.ShowSelected)
        except:
            pass

        tag = TagText(self, -1, label='channel', fill_colour=wx.Colour(210, 252, 120))
        self.AddEvents(tag)
        self.titleSizer.Insert(0, tag, 0, wx.CENTER | wx.TOP, 2)
        self.titleSizer.Insert(1, (5, -1), 0, 0)

    def ShowSelected(self, event=None):
        if event:
            self.OnMouse(event)
        DoubleLineListItemWithButtons.ShowSelected(self)

        highlight = event and event.GetEventObject() == self.controls[self.at_index] and not event.Leaving()

        if self.at_index >= 0:
            for torrent in self.data[-1]:
                infohash = torrent.infohash
                if infohash in self.parent_list.items:
                    torrent_item = self.parent_list.GetItem(infohash)
                    if highlight:
                        torrent_item.Highlight(colour=LIST_AT_HIGHLIST, timeout=5, revert=True)
                    else:
                        torrent_item.ShowSelected()

    def OnDClick(self, event=None):
        for torrent in self.data[4]:
            self.original_data.addTorrent(torrent)
        ChannelListItem.OnDClick(self, event)


class ChannelListItemNoButton(ChannelListItem):

    def AddButtons(self):
        pass


class PlaylistItem(DoubleLineListItemWithButtons):

    def __init__(self, parent, parent_list, columns, data, original_data, *args, **kwargs):
        DoubleLineListItemWithButtons.__init__(self, parent, parent_list, columns, data, original_data, *args, **kwargs)

        if getattr(parent_list.parent_list, 'AddTorrent', False):
            from .channel import TorrentDT
            self.SetDropTarget(TorrentDT(original_data, parent_list.parent_list.AddTorrent))

    def AddComponents(self, *args, **kwargs):
        DoubleLineListItemWithButtons.AddComponents(self, *args, **kwargs)

        tag = TagText(self, -1, label='playlist', fill_colour=wx.Colour(136, 117, 255), text_colour=wx.WHITE)
        self.AddEvents(tag)
        self.titleSizer.Insert(0, tag, 0, wx.CENTER | wx.TOP, 2)
        self.titleSizer.Insert(1, (5, -1), 0, 0)

    def AddButtons(self):
        self.buttonSizer.Clear(deleteWindows=True)
        self.AddButton("Visit playlist", lambda evt: self.guiutility.showPlaylist(self.original_data))

    def OnChange(self):
        self.parent_list.OnChange()

    def OnDClick(self, event):
        self.guiutility.showPlaylist(self.original_data)

    @warnWxThread
    def GetIcons(self):
        return []

    @warnWxThread
    def SetTitleSizerHeight(self, height):
        self.titleSizer.AddSpacer((-1, height))


class PlaylistItemNoButton(PlaylistItem):

    def AddButtons(self):
        pass


class LibraryListItem(TorrentListItem):

    def AddButtons(self):
        pass

    def GetIcons(self):
        return [self.parent_list.parent_list._torrent_icon(self)]

    def GetContextMenu(self):
        menu = TorrentListItem.GetContextMenu(self)
        menu.Enable(menu.FindItem('Show download button on hover'), False)
        return menu

    def OnDClick(self, event):
        pass


class ThumbnailListItemNoTorrent(FancyPanel, ListItem):

    def __init__(
        self,
        parent,
     parent_list,
     columns,
     data,
     original_data,
     leftSpacer=0,
     rightSpacer=0,
     showChange=False,
     list_selected=LIST_SELECTED,
     list_expanded=LIST_EXPANDED,
     list_selected_and_expanded=LIST_DARKBLUE):
        FancyPanel.__init__(self, parent, border=wx.RIGHT | wx.BOTTOM)
        self.SetBorderColour(SEPARATOR_GREY)
        self.guiutility = GUIUtility.getInstance()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.parent_list = parent_list
        self.columns = self.controls = []
        self.data = data
        self.original_data = original_data
        self.max_bitmap_size = (175, 175)

        self.showChange = showChange
        self.list_deselected = LIST_DESELECTED
        self.list_selected = list_selected
        self.list_expanded = list_expanded
        self.list_selected_and_expanded = list_selected_and_expanded

        self.highlightTimer = self.expandedPanel = self.dlbutton = self.plbutton = None
        self.selected = self.expanded = False
        self.SetBackgroundColour(self.list_deselected)

        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.vSizer.Add(self.hSizer, 0, wx.EXPAND)

        self.AddComponents(leftSpacer, rightSpacer)

        self.SetSizer(self.vSizer)

    def AddComponents(self, leftSpacer, rightSpacer):
        ListItem.AddComponents(self, leftSpacer, rightSpacer)

        self.bitmap, self.bitmap_hover = self.CreateBitmaps()

        if sys.platform == 'darwin':
            # on Mac OS X (10.8), NO_BORDER will make the bitmap distorted
            self.thumbnail = wx.BitmapButton(self, -1, self.bitmap)
        else:
            self.thumbnail = wx.BitmapButton(self, -1, self.bitmap, style=wx.NO_BORDER)
        self.thumbnail.SetBitmapHover(self.bitmap_hover)
        self.thumbnail.Bind(wx.EVT_BUTTON, self.OnThumbnailClick)
        self.hSizer.Add(self.thumbnail, 1, wx.EXPAND | wx.ALL, 15)
        self.AddEvents(self.thumbnail)

        def ShortenText(statictext, text):
            for i in xrange(len(text), 0, -1):
                newText = text[0:i]
                if i != len(text):
                    newText += ".."
                width, _ = statictext.GetTextExtent(newText)
                if width <= self.GetBestSize().x:
                    return newText
            return ""

        self.vSizer.AddStretchSpacer()

        name = wx.StaticText(self, -1, '')
        name.SetLabel(ShortenText(name, self.original_data.name))
        self.AddEvents(name)
        self.vSizer.Add(name, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 10)

        self.hSizer.Layout()

    def CreateBitmaps(self):
        # Temporary silence wx errors. Avoids "No handler found for image type" errors.
        nolog = wx.LogNull()

        bitmap = None

        thumb_dir = os.path.join(
            self.guiutility.utility.session.get_torrent_collecting_dir(),
            binascii.hexlify(self.original_data.infohash))
        thumb_files = [os.path.join(dp, fn) for dp, _, fns in os.walk(thumb_dir)
                       for fn in fns if os.path.splitext(fn)[1] in THUMBNAIL_FILETYPES]

        if thumb_files:
            bmp = wx.Bitmap(thumb_files[0], wx.BITMAP_TYPE_ANY)
            res = limit_resolution(bmp.GetSize(), self.max_bitmap_size)
            bitmap = bmp.ConvertToImage(
            ).Scale(
                *res,
                quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap(
            ) if bmp.IsOk(
            ) and res else None

        if not bitmap:
            bitmap = GuiImageManager.getInstance().drawBitmap("no-thumbnail",
                                                              self.max_bitmap_size, self.GetFont())

        res = bitmap.GetSize()
        bitmap_hover = wx.EmptyBitmap(*res)
        dc = wx.MemoryDC(bitmap_hover)
        gc = wx.GraphicsContext.Create(dc)
        gc.DrawBitmap(bitmap, 0, 0, *res)
        gc.SetBrush(wx.Brush(wx.Colour(0, 0, 0, 150)))
        gc.DrawRectangle(0, 0, *res)

        size = min(res)
        path = gc.CreatePath()
        path.MoveToPoint(0.2 * size, 0.2 * size)
        path.AddLineToPoint(0.2 * size, 0.8 * size)
        path.AddLineToPoint(0.8 * size, 0.5 * size)
        gc.PushState()
        gc.Translate((res[0] - size) / 2, (res[1] - size) / 2)
        gc.SetBrush(wx.Brush(wx.Colour(255, 255, 255, 150)))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawPath(path)

        dc.SelectObject(wx.NullBitmap)
        del dc

        # Re-enable wx errors
        del nolog

        return bitmap, bitmap_hover

    def OnThumbnailClick(self, event):
        self.guiutility.library_manager.playTorrent(self.original_data.infohash)


class ThumbnailListItem(ThumbnailListItemNoTorrent, TorrentListItem):

    def __init__(self, *args, **kwargs):
        ThumbnailListItemNoTorrent.__init__(self, *args, **kwargs)

    def AddComponents(self, *args, **kwargs):
        ThumbnailListItemNoTorrent.AddComponents(self, *args, **kwargs)

    def GetContextMenu(self):
        menu = TorrentListItem.GetContextMenu(self)
        menu.DestroyId(menu.FindItem('Show labels..'))
        return menu

    def CanShowHover(self, event):
        event.Enable(False)
        event.Check(False)

    def ShowSelected(self):
        DoubleLineListItem.ShowSelected(self)

    def GetIcons(self):
        return []

    def SetThumbnailIcon(self):
        pass


class ActivityListItem(ListItem):

    def __init__(self, *args, **kwargs):
        ListItem.__init__(self, *args, **kwargs)

    def AddComponents(self, leftSpacer, rightSpacer):
        ListItem.AddComponents(self, leftSpacer, rightSpacer)
        if self.data[0] in ['Results', 'Channels', 'Downloads', 'Videoplayer']:
            self.num_items = TagText(self, -1, label='0', fill_colour=GRADIENT_DGREY, edge_colour=SEPARATOR_GREY)
            self.hSizer.Add(self.num_items, 0, wx.CENTER | wx.RIGHT, 5)
            self.hSizer.Layout()


class DragItem(TorrentListItem):

    def AddEvents(self, control):
        if getattr(control, 'GetWindow', False):  # convert sizeritems
            control = control.GetWindow() or control.GetSizer()

        if getattr(control, 'Bind', False):
            control.Bind(wx.EVT_MOTION, self.OnDrag)

        TorrentListItem.AddEvents(self, control)

    def OnDrag(self, event):
        if event.LeftIsDown():
            self.parent_list.parent_list.OnDrag(self)


class AvantarItem(ListItem):

    def __init__(
        self,
        parent,
     parent_list,
     columns,
     data,
     original_data,
     leftSpacer=0,
     rightSpacer=0,
     showChange=False,
     list_selected=LIST_SELECTED,
     list_expanded=LIST_EXPANDED):
        self.header = ''
        self.body = ''
        self.avantar = None
        self.additionalButtons = []
        self.maxlines = 6
        ListItem.__init__(
            self,
            parent,
            parent_list,
            columns,
            data,
            original_data,
            leftSpacer,
            rightSpacer,
            showChange,
            list_selected)

    def AddComponents(self, leftSpacer, rightSpacer):
        titleRow = wx.BoxSizer(wx.HORIZONTAL)
        if leftSpacer > 0:
            titleRow.AddSpacer((leftSpacer, -1))

        if self.avantar:
            titleRow.Add(wx.StaticBitmap(self, bitmap=self.avantar), 0, wx.RIGHT, 7)

        vSizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(self, -1, self.header)
        _set_font(header, -1, wx.FONTWEIGHT_BOLD)
        header.SetMinSize((1, -1))

        vSizer.Add(header, 0, wx.EXPAND)
        vSizer.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.RIGHT, 5)

        self.moreButton = None
        if len(self.additionalButtons) > 0:
            self.moreButton = wx.Button(self, style=wx.BU_EXACTFIT)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        if len(self.additionalButtons) > 0:
            hSizer.Add(self.moreButton, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_BOTTOM)

            for button in self.additionalButtons:
                hSizer.Add(button, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_BOTTOM)
                button.Show(False)

            self.moreButton.Show(False)

        if isinstance(self.body, basestring):
            self.desc = MaxBetterText(self, self.body, maxLines=self.maxlines, button=self.moreButton)
            self.desc.SetMinSize((1, -1))
            vSizer.Add(self.desc, 0, wx.EXPAND)
            vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT)
        else:
            self.desc = None
            for index, bmp in enumerate(self.body):
                sbmp = wx.StaticBitmap(self, -1, bmp)
                hSizer.Insert(index, sbmp, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            hSizer.InsertStretchSpacer(len(self.body))
            vSizer.Add(hSizer, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        titleRow.Add(vSizer, 1)

        if rightSpacer > 0:
            titleRow.AddSpacer((rightSpacer, -1))
        self.vSizer.Add(titleRow, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 3)
        self.AddEvents(self)

    def BackgroundColor(self, color):
        changed = ListItem.BackgroundColor(self, color)

        if len(self.additionalButtons) > 0 and changed:
            if self.desc and self.desc.hasMore:
                self.moreButton.Show(color == self.list_selected)

            for button in self.additionalButtons:
                button.Show(color == self.list_selected)

    def OnChange(self):
        self.parent_list.OnChange()


class CommentItem(AvantarItem):

    def __init__(
        self,
        parent,
     parent_list,
     columns,
     data,
     original_data,
     leftSpacer=0,
     rightSpacer=0,
     showChange=False,
     list_selected=LIST_SELECTED,
     list_expanded=LIST_EXPANDED):
        # check if we are part of a torrent
        manager = parent_list.parent_list.GetManager()
        if manager.channeltorrent:
            self.inTorrent = True
        else:
            self.inTorrent = False

        _, comment = original_data
        self.canRemove = comment.isMyComment() or (comment.channel and comment.channel.isMyChannel())

        AvantarItem.__init__(
            self,
            parent,
            parent_list,
            columns,
            data,
            original_data,
            leftSpacer,
            rightSpacer,
            showChange,
            list_selected)

    def AddComponents(self, leftSpacer, rightSpacer):
        depth, comment = self.original_data

        self.header = "Posted %s by %s" % (format_time(comment.time_stamp).lower(), comment.name)
        self.body = comment.comment
        self.avantar = comment.avantar

        if depth == 0:
            if not self.inTorrent and comment.torrent:
                self.header += " in %s" % comment.torrent.name
                button = wx.Button(self, -1, 'Open Torrent', style=wx.BU_EXACTFIT)
                button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
                self.additionalButtons.append(button)
        else:
            leftSpacer += depth * (self.avantar.GetWidth() + 7)  # avantar + spacer

        if self.canRemove:
            button = wx.Button(self, -1, 'Remove Comment', style=wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, self.RemoveComment)
            self.additionalButtons.append(button)

        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def ShowTorrent(self, event):
        _, comment = self.original_data
        if comment.torrent:
            self.parent_list.parent_list.OnShowTorrent(comment.torrent)

    def RemoveComment(self, event):
        _, comment = self.original_data
        self.parent_list.parent_list.OnRemoveComment(comment)


class CommentActivityItem(CommentItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        _, comment = self.original_data
        self.header = "New comment received, posted %s by %s" % (format_time(comment.time_stamp).lower(), comment.name)

        if not self.inTorrent and comment.torrent:
            self.header += " in %s" % comment.torrent.name
            button = wx.Button(self, -1, 'Open Torrent', style=wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
            self.additionalButtons.append(button)

        self.body = comment.comment
        self.avantar = GuiImageManager.getInstance().getImage(u"COMMENT", SMALL_ICON_MAX_DIM)

        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)


class NewTorrentActivityItem(AvantarItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        torrent = self.original_data

        self.header = "New torrent received at %s" % (format_time(torrent.time_stamp).lower())
        self.body = torrent.name

        button = wx.Button(self, -1, 'Open Torrent', style=wx.BU_EXACTFIT)
        button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        self.additionalButtons.append(button)

        self.avantar = GuiImageManager.getInstance().getImage(u"TORRENT_NEW", SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data)


class TorrentActivityItem(AvantarItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        torrent = self.original_data

        self.header = "Discovered a torrent at %s, injected at %s" % (
            format_time(torrent.inserted).lower(),
            format_time(torrent.time_stamp).lower())
        self.body = torrent.name

        button = wx.Button(self, -1, 'Open Torrent', style=wx.BU_EXACTFIT)
        button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        self.additionalButtons.append(button)

        self.avantar = GuiImageManager.getInstance().getImage(u"TORRENT", SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data)


class ModificationActivityItem(AvantarItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        modification = self.original_data

        self.header = "Discovered a modification by %s at %s" % (
            modification.peer_name,
            format_time(modification.inserted).lower())

        if modification.name == "swift-thumbnails":
            self.guiutility = GUIUtility.getInstance()
            self.session = self.guiutility.utility.session

            thumb_dir = os.path.join(
                self.session.get_torrent_collecting_dir(),
                binascii.hexlify(modification.torrent.infohash))
            self.body = []
            if os.path.exists(thumb_dir):
                for single_thumb in os.listdir(thumb_dir)[:4]:
                    bmp = wx.Bitmap(os.path.join(thumb_dir, single_thumb), wx.BITMAP_TYPE_ANY)
                    if bmp.IsOk():
                        res = limit_resolution(bmp.GetSize(), (100, 100))
                        self.body.append(
                            bmp.ConvertToImage().Scale(*res,
                                                       quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap())
            if not self.body:
                self.body = "WARNING: The thumbnails related to this modification could not be found on the filesystem."
        elif modification.name == "video-info":
            video_info = json.loads(modification.value)
            duration = timedelta(seconds=video_info['duration'])
            duration = str(duration).split('.')[0]
            self.body = "Modified the bitrate in '%s kb/s', the duration in '%s', and the resolution in '%dx%d'" % \
                        (video_info['bitrate'], duration, video_info['resolution'][0], video_info['resolution'][1])
        else:
            self.body = "Modified %s in '%s'" % (modification.name, modification.value)

        if modification.torrent:
            self.header += " for torrent '%s'" % modification.torrent.colt_name
            button = wx.Button(self, -1, 'Open Torrent', style=wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
            self.additionalButtons.append(button)

        self.avantar = GuiImageManager.getInstance().getImage(u"MODIFICATION", SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.torrent)


class ModificationItem(AvantarItem):

    def __init__(
        self,
        parent,
     parent_list,
     columns,
     data,
     original_data,
     leftSpacer=0,
     rightSpacer=0,
     showChange=False,
     list_selected=LIST_SELECTED,
     list_expanded=LIST_EXPANDED):
        if isinstance(parent, wx.Dialog):
            self.noButton = True
        else:
            self.noButton = not getattr(parent_list.parent_list, 'canModify', True)
        AvantarItem.__init__(
            self,
            parent,
            parent_list,
            columns,
            data,
            original_data,
            leftSpacer,
            rightSpacer,
            showChange,
            list_selected)

    def AddComponents(self, leftSpacer, rightSpacer):
        modification = self.original_data

        if modification.name == "swift-thumbnails":
            self.guiutility = GUIUtility.getInstance()
            self.session = self.guiutility.utility.session

            thumb_dir = os.path.join(
                self.session.get_torrent_collecting_dir(),
                binascii.hexlify(modification.torrent.infohash))
            self.body = []
            if os.path.exists(thumb_dir):
                for single_thumb in os.listdir(thumb_dir)[:4]:
                    bmp = wx.Bitmap(os.path.join(thumb_dir, single_thumb), wx.BITMAP_TYPE_ANY)
                    if bmp.IsOk():
                        res = limit_resolution(bmp.GetSize(), (100, 100))
                        self.body.append(
                            bmp.ConvertToImage().Scale(*res,
                                                       quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap())
            if not self.body:
                self.body = "WARNING: The thumbnails related to this modification could not be found on the filesystem."
        elif modification.name == "video-info":
            video_info = json.loads(modification.value)
            duration = timedelta(seconds=video_info['duration'])
            duration = str(duration).split('.')[0]
            self.body = "Modified the bitrate in '%s kb/s', the duration in '%s', and the resolution in '%dx%d'" % \
                        (video_info['bitrate'], duration, video_info['resolution'][0], video_info['resolution'][1])
        else:
            self.body = modification.value

        gui_image_manager = GuiImageManager.getInstance()
        if modification.moderation:
            moderation = modification.moderation
            self.header = "%s modified by %s,\nbut reverted by %s due to: '%s'" % (
                modification.name.capitalize(),
                modification.peer_name,
                moderation.peer_name,
                moderation.message)
            self.avantar = gui_image_manager.getImage(u"REVERTED_MODIFICATION", SMALL_ICON_MAX_DIM)
            self.maxlines = 2
        else:
            self.header = "%s modified by %s at %s" % (
                modification.name.capitalize(),
                modification.peer_name,
                format_time(modification.time_stamp).lower())
            self.avantar = gui_image_manager.getImage(u"MODIFICATION", SMALL_ICON_MAX_DIM)

            if not self.noButton:
                button = wx.Button(self, -1, 'Revert Modification', style=wx.BU_EXACTFIT)
                button.Bind(wx.EVT_BUTTON, self.RevertModification)
                self.additionalButtons.append(button)

        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def RevertModification(self, event):
        self.parent_list.parent_list.OnRevertModification(self.original_data)


class ModerationActivityItem(AvantarItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        moderation = self.original_data

        self.header = "Discovered a moderation %s" % (format_time(moderation.inserted).lower())
        self.body = "%s reverted a modification made by %s, reason '%s'" % (
            moderation.peer_name, moderation.by_peer_name, moderation.message)

        gui_image_manager = GuiImageManager.getInstance()
        self.avantar = gui_image_manager.getImage(u"REVERTED_MODIFICATION", SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)


class ModerationItem(AvantarItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        moderation = self.original_data

        self.header = "%s reverted a modification by %s at %s" % (
            moderation.peer_name.capitalize(),
            moderation.by_peer_name,
            format_time(moderation.time_stamp).lower())

        if moderation.modification:
            modification = moderation.modification
            self.body = "%s reverted due to '%s'.\n" % (modification.name.capitalize(), moderation.message)
            if moderation.severity > 0:
                self.body += "%s additionally issued a warning!\n" % moderation.peer_name.capitalize()
            self.body += "Modification was:\n%s" % modification.value

            if modification.torrent:
                self.header += " for torrent '%s'" % modification.torrent.name
                button = wx.Button(self, -1, 'Open Torrent', style=wx.BU_EXACTFIT)
                button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
                self.additionalButtons.append(button)

        else:
            self.body = moderation.message
        gui_image_manager = GuiImageManager.getInstance()
        self.avantar = gui_image_manager.getImage(u"REVERTED_MODIFICATION", SMALL_ICON_MAX_DIM)

        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.modification.torrent)


class MarkingActivityItem(AvantarItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        marking = self.original_data

        self.header = "Discovered an opinion %s" % (format_time(marking.time_stamp).lower())
        self.body = "%s was marked as '%s'" % (marking.torrent.name, marking.type)

        button = wx.Button(self, -1, 'Open Torrent', style=wx.BU_EXACTFIT)
        button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        self.additionalButtons.append(button)

        gui_image_manager = GuiImageManager.getInstance()
        self.avantar = gui_image_manager.getImage(u"MARKING", SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.torrent)
