# Written by Niels Zeilemaker, Egbert Bouman
import wx
import sys
import json
import shutil
import urllib
import logging
from datetime import timedelta

from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice
from Tribler.Main.vwxGUI.widgets import NativeIcon, BetterText as StaticText, _set_font, TagText
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.IconsManager import IconsManager, SMALL_ICON_MAX_DIM
from Tribler.Main.Utility.GuiDBTuples import MergedDs
from Tribler import LIBRARYNAME

from Tribler.Main.vwxGUI.list_body import *
from Tribler.Main.vwxGUI.list_details import *
from Tribler.Main.globals import DefaultDownloadStartupConfig


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
                self.hSizer.Insert(0, control.icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, (33 - control.icon.GetSize().x) / 2)
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
                width = min(width, self.buttonSizer.GetPosition().x - self.descrSizer.GetPosition().x - sum([child.GetSize().x for child in self.descrSizer.GetChildren()]) + control.GetSize().x)
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

            # If we are dealing with a control with a label in front of it, we need to add the width of the label to the column width.
            if self.columns[column_index].get('showColumname', True) and \
               self.columns[column_index].get('name', False) and \
               self.columns[column_index].get('type', '') == 'method':
                for index, child in enumerate(self.descrSizer.GetChildren()):
                    if child.IsWindow() and child.GetWindow() == self.controls[control_index]:
                        if index > 1:
                            self.columns[column_index]['width'] += self.descrSizer.GetChildren()[index - 1].GetSize().x
                        break

            config = self.guiutility.utility.config
            column_sizes = config.Read("column_sizes")
            column_sizes = json.loads(column_sizes) if column_sizes else {}
            column_sizes[type(self).__name__] = column_sizes.get(type(self).__name__, {})
            column_sizes[type(self).__name__].update({self.columns[column_index]['name']: self.columns[column_index]['width']})
            config.Write("column_sizes", json.dumps(column_sizes))
            config.Flush()

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

        config = self.guiutility.utility.config

        hide_columns = config.Read("hide_columns")
        hide_columns = json.loads(hide_columns) if hide_columns else {}
        hide_columns[type(self).__name__] = hide_columns.get(type(self).__name__, {})
        hide_columns[type(self).__name__].update({self.columns[index]['name']: self.columns[index]['show']})

        config.Write("hide_columns", json.dumps(hide_columns))
        config.Flush()

        if getattr(self.parent_list.parent_list, 'ResetBottomWindow', False):
            self.parent_list.parent_list.ResetBottomWindow()
        wx.CallAfter(self.parent_list.Rebuild)

    @warnWxThread
    def GetContextMenu(self):
        menu = wx.Menu()
        self.GetSubMenu([{'title': 'Show labels..', \
                          'handler': [{'title': c['name'], 'type': 'check', 'enable': c['name'] != 'Name', 'check': c.get('show', True), \
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

            if type(handler) is list:
                itemid = wx.NewId()
                submenu.AppendMenu(itemid, title, self.GetSubMenu(handler))
            else:
                itemid = wx.NewId()
                if itemtype == 'check':
                    submenu.AppendCheckItem(itemid, title)
                else:
                    submenu.Append(itemid, title)
                wx.EVT_MENU(self, itemid, handler)

            if updateui != None:
                wx.EVT_UPDATE_UI(self, itemid, updateui)

            if type(enable) is bool:
                submenu.Enable(itemid, enable)

            if itemtype == 'check' and type(check) is bool:
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
        if handler == None or label == None:
            return

        button = ProgressButton(self, -1, label)
        button.Bind(wx.EVT_LEFT_UP, handler)
        self.AddEvents(button)
        self.buttonSizer.Add(button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, right_spacer)
        self.Layout()
        self.ShowSelected()
        return button

    def ShowSelected(self):
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
        DoubleLineListItem.__init__(self, *args, **kwargs)
        self.SetThumbnailIcon()
        self.dlbutton = None

    def AddButtons(self):
        self.buttonSizer.Clear(deleteWindows=True)

        do_add = False
        for column in self.columns:
            if column.get('name', None) == 'Name':
                do_add = column.get('dlbutton', False)
                break

        if do_add:
            self.dlbutton = self.AddButton("Download", lambda evt: self.guiutility.frame.top_bg.OnDownload(evt, [self.original_data]))
            self.dlbutton.Enable('completed' not in self.original_data.state and 'active' not in self.original_data.state)

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
            self.dlbutton.Enable('completed' not in self.original_data.state and 'active' not in self.original_data.state)

    def SetThumbnailIcon(self):
        torcoldir = self.guiutility.utility.session.get_torrent_collecting_dir()
        rel_thumbdir = 'thumbs-' + binascii.hexlify(self.original_data.infohash)
        abs_thumbdir = os.path.join(torcoldir, rel_thumbdir)
        has_thumbnails = os.path.exists(abs_thumbdir) and os.listdir(abs_thumbdir)

        if has_thumbnails and not getattr(self, 'snapshot', None):
            # Override the settings flags set by AddComponents
            self.controls[0].SetMinSize(self.controls[0].GetBestSize())
            self.titleSizer.Detach(self.controls[0])
            self.titleSizer.Insert(0, self.controls[0], 0, wx.CENTER)

            # Add icon right after the torrent title, indicating that the torrent has thumbnails
            snapshot_bmp = wx.Bitmap(os.path.join(self.guiutility.utility.getPath(), LIBRARYNAME, "Main", "vwxGUI", "images", "snapshot.png"), wx.BITMAP_TYPE_ANY)
            self.snapshot = wx.StaticBitmap(self, -1, snapshot_bmp)
            self.snapshot.SetToolTipString("This torrent has thumbnails.")
            self.AddEvents(self.snapshot)
            self.titleSizer.Add(self.snapshot, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT | wx.LEFT, 10)
            self.Layout()
            wx.CallAfter(self.Refresh)

    @warnWxThread
    def GetContextMenu(self):
        menu = DoubleLineListItem.GetContextMenu(self)

        self.GetSubMenu([{'title': 'Show download button on hover', 'type': 'check', 'updateui': self.CanShowHover, 'handler': self.OnShowHover}, \
                         None, \
                         {'title': 'Force start', 'updateui': self.CanForceStart, 'handler': self.OnForceStart}, \
                         {'title': 'Start', 'updateui': self.CanStart, 'handler': self.OnStart}, \
                         {'title': 'Stop', 'updateui': self.CanStop, 'handler': self.OnStop}, \
                         None, \
                         {'title': 'Remove download', 'updateui': self.CanRemove, 'handler': self.OnRemove}, \
                         {'title': 'Remove download + data', 'updateui': self.CanRemoveAll, 'handler': self.OnRemoveAll}, \
                         None, \
                         {'title': 'Force recheck', 'updateui': self.CanRecheck, 'handler': self.OnRecheck}, \
                         None, \
                         {'title': 'Bandwidth allocation..', 'updateui': self.CanAllocateBandwidth, 'handler': []}, \
                         None, \
                         {'title': 'Export torrent..', 'updateui': self.CanExportTorrent, 'handler': self.OnExportTorrent}, \
                         {'title': 'Copy magnet link', 'updateui': self.CanCopyMagnet, 'handler': self.OnCopyMagnet}, \
                         {'title': 'Add to my channel', 'updateui': self.CanAddToMyChannel, 'handler': self.OnAddToMyChannel}, \
                         None, \
                         {'title': 'Explore files', 'updateui': self.CanExplore, 'handler': self.OnExplore}, \
                         {'title': 'Change download location..', 'updateui': self.CanMove, 'handler': self.OnMove}], menu)

        bw_alloc = menu.FindItemById(menu.FindItem('Bandwidth allocation..')).GetSubMenu()
        download = self.original_data.ds.get_download() if self.original_data.ds else None
        if download and download.get_def().get_def_type() == 'torrent':
            bw_alloc.AppendMenu(wx.ID_ANY, 'Set download limit..', self.CreateBandwidthMenu(download, DOWNLOAD, menu))
            bw_alloc.AppendMenu(wx.ID_ANY, 'Set upload limit..', self.CreateBandwidthMenu(download, UPLOAD, menu))

        return menu

    def CreateBandwidthMenu(self, download, direction, parent_menu):
        result = wx.Menu()

        limit = download.get_max_speed(direction)

        values = self.guiutility.utility.round_range(limit) if limit > 0 else range(0, 1000, 100)
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
                parent_menu.Bind(wx.EVT_MENU, lambda x, value=value: download.set_max_speed(direction, value), id=itemid)
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
            if torrent.dslist[0] and 'metadata' not in torrent.state and 'checking' not in torrent.state:
                torrent.dslist[0].get_download().force_recheck()

    def OnExportTorrent(self, filename):
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        if len(torrents) == 1:
            filename = self.guiutility.torrentsearch_manager.getCollectedFilename(torrents[0])
            dlg = wx.FileDialog(self, message="Select an export destination", defaultFile="%s.torrent" % torrents[0].name, wildcard="*.torrent", style=wx.FD_SAVE | wx.CHANGE_DIR | wx.OVERWRITE_PROMPT)
            dlg.SetDirectory(DefaultDownloadStartupConfig.getInstance().get_dest_dir())
            if dlg.ShowModal() == wx.ID_OK:
                paths = dlg.GetPaths()
                if os.path.exists(paths[0]):
                    os.remove(paths[0])
                shutil.copyfile(filename, paths[0])
            dlg.Destroy()
        elif len(torrents) > 1:
            dlg = wx.DirDialog(self, "Choose where to move the selected torrent(s)", style=wx.DEFAULT_DIALOG_STYLE)
            dlg.SetPath(DefaultDownloadStartupConfig.getInstance().get_dest_dir())
            if dlg.ShowModal() == wx.ID_OK:
                path = dlg.GetPath()
                for torrent in torrents:
                    src_filename = self.guiutility.torrentsearch_manager.getCollectedFilename(torrent)
                    dst_filename = os.path.join(path, "%s.torrent" % torrent.name)
                    if os.path.exists(dst_filename):
                        os.remove(dst_filename)
                    shutil.copyfile(src_filename, dst_filename)
            dlg.Destroy()

    def OnCopyMagnet(self, event):
        magnetlinks = ''
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            magnetlink = "magnet:?xt=urn:btih:" + binascii.hexlify(torrent.infohash)
            trackers = self.guiutility.channelsearch_manager.torrent_db.getTrackerListByTorrentID(torrent.torrent_id)
            if trackers:
                for tracker in trackers:
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
            UserEventLogDBHandler.getInstance().addEvent(message="MyChannel: %d manual add(s) from library" % len(added), type=2)

            # remote channel link to force reload
            for torrent in added:
                del torrent.channel
                torrent.channel

            if len(added) == 1:
                def gui_call():
                    self.guiutility.Notify('New torrent added to My Channel', "Torrent '%s' has been added to My Channel" % self.original_data.name, icon=wx.ART_INFORMATION)
            else:
                def gui_call():
                    self.guiutility.Notify('New torrents added to My Channel', "%d Torrents have been added to My Channel" % len(added), icon=wx.ART_INFORMATION)

            wx.CallAfter(gui_call)

    def OnExplore(self, event):
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            path = None
            if torrent.ds:
                destdirs = torrent.ds.get_download().get_dest_files()
                path = os.path.commonprefix([os.path.split(path)[0] for _, path in destdirs])
                if path and os.path.exists(path):
                    startfile(path)
                else:
                    path = DefaultDownloadStartupConfig.getInstance().get_dest_dir()
                    startfile(path)


    def OnMove(self, event):
        items = self.guiutility.frame.librarylist.GetExpandedItems()
        torrents = [item[1].original_data for item in items if isinstance(item[1].original_data, Torrent) or isinstance(item[1].original_data, CollectedTorrent)]

        dlg = wx.DirDialog(self, "Choose where to move the selected torrent(s)", style=wx.DEFAULT_DIALOG_STYLE)
        dlg.SetPath(self.original_data.ds.get_download().get_dest_dir())
        if dlg.ShowModal() == wx.ID_OK:
            new_dir = dlg.GetPath()
            for torrent in torrents:
                if torrent.ds:
                    self._MoveDownload(torrent.ds, new_dir)

    def _MoveDownload(self, download_state, new_dir):
        def modify_config(download):
            self.guiutility.library_manager.deleteTorrentDownload(download, None, removestate=False)

            cdef = download.get_def()
            dscfg = DownloadStartupConfig(download.dlconfig)
            dscfg.set_dest_dir(new_dir)

            return cdef, dscfg

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
                            os.rename(oldfile, newfile)
                        else:
                            os.rename(oldfile, newfile)
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
        if isinstance(download_state, MergedDs):
            dslist = download_state.dslist
        else:
            dslist = [download_state]

        # Remove Swift downloads
        to_start = []
        for ds in dslist:
            download = ds.get_download()
            if download.get_def().get_def_type() == 'swift':
                to_start.append(modify_config(download))

        # Move torrents
        storage_moved = False
        for ds in dslist:
            download = ds.get_download()
            if download.get_def().get_def_type() == 'torrent':
                self._logger.info("Moving from %s to %s newdir %s", old, new, new_dir)
                download.move_storage(new_dir)
                if download.get_save_path() == new_dir:
                    storage_moved = True

        # If libtorrent hasn't moved the files yet, move them now
        if not storage_moved:
            self._logger.info("Moving from %s to %s newdir %s", old, new, new_dir)
            movelambda = lambda: rename_or_merge(old, new)
            self.guiutility.utility.session.lm.rawserver.add_task(movelambda, 0.0)

        # Start Swift downloads again..
        for cdef, dscfg in to_start:
            startlambda = lambda cdef = cdef, dscfg = dscfg: self.guiutility.utility.session.start_download(cdef, dscfg)
            self.guiutility.utility.session.lm.rawserver.add_task(startlambda, 0.0)

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
                if tdef and tdef.get_def_type() == 'torrent':
                    if UserDownloadChoice.get_singleton().get_download_state(tdef.get_id()) == 'restartseed':
                        enable = False
                        break
        event.Enable(enable)

    def CanStart(self, event):
        event.Enable(self.guiutility.frame.top_bg.upload_btn.IsEnabled() or \
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
            status = torrent.dslist[0].get_status() if torrent.dslist[0] else None
            if status not in [None, DLSTATUS_METADATA, DLSTATUS_HASHCHECKING, DLSTATUS_WAITING4HASHCHECK]:
                enable = True
                break
        event.Enable(enable)

    def CanAllocateBandwidth(self, event):
        enable = False
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            download = torrent.ds.get_download() if torrent.ds else None
            if download and download.get_def().get_def_type() == 'torrent':
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
            filename = self.guiutility.torrentsearch_manager.getCollectedFilename(torrent)
            if filename and os.path.exists(filename):
                enable = True
                break
        event.Enable(enable)

    def CanCopyMagnet(self, event):
        enable = False
        torrents = self.guiutility.frame.top_bg.GetSelectedTorrents()
        for torrent in torrents:
            download = torrent.ds.get_download() if torrent.ds else None
            if download and download.get_def().get_def_type() == 'torrent':
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
                self.AddButton("Remove Favorite", lambda evt, data=self.original_data: self.guiutility.RemoveFavorite(evt, data))
            elif not self.original_data.isMyChannel():
                self.AddButton("Mark as Favorite", lambda evt, data=self.original_data: self.guiutility.MarkAsFavorite(evt, data))
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
            self.controls[self.at_index].SetToolTipString('This channel contains %d torrents matching your search query. The visible matches are currently highlighted.' % len(self.data[-1]))
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
            from channel import TorrentDT
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
        return [self.parent_list.parent_list._torrent_icon(self), self.parent_list.parent_list._swift_icon(self)]

    def GetContextMenu(self):
        menu = TorrentListItem.GetContextMenu(self)
        menu.Enable(menu.FindItem('Show download button on hover'), False)
        return menu

    def OnDClick(self, event):
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

    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer=0, rightSpacer=0, showChange=False, list_selected=LIST_SELECTED, list_expanded=LIST_EXPANDED):
        self.header = ''
        self.body = ''
        self.avantar = None
        self.additionalButtons = []
        self.maxlines = 6
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)

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

    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer=0, rightSpacer=0, showChange=False, list_selected=LIST_SELECTED, list_expanded=LIST_EXPANDED):
        # check if we are part of a torrent
        manager = parent_list.parent_list.GetManager()
        if manager.channeltorrent:
            self.inTorrent = True
        else:
            self.inTorrent = False

        _, comment = original_data
        self.canRemove = comment.isMyComment() or (comment.channel and comment.channel.isMyChannel())

        AvantarItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)

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
        im = IconsManager.getInstance()
        self.avantar = im.get_default('COMMENT', SMALL_ICON_MAX_DIM)

        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)


class NewTorrentActivityItem(AvantarItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        torrent = self.original_data

        self.header = "New torrent received at %s" % (format_time(torrent.time_stamp).lower())
        self.body = torrent.name

        button = wx.Button(self, -1, 'Open Torrent', style=wx.BU_EXACTFIT)
        button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        self.additionalButtons.append(button)

        im = IconsManager.getInstance()
        self.avantar = im.get_default('TORRENT_NEW', SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data)


class TorrentActivityItem(AvantarItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        torrent = self.original_data

        self.header = "Discovered a torrent at %s, injected at %s" % (format_time(torrent.inserted).lower(), format_time(torrent.time_stamp).lower())
        self.body = torrent.name

        button = wx.Button(self, -1, 'Open Torrent', style=wx.BU_EXACTFIT)
        button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        self.additionalButtons.append(button)

        im = IconsManager.getInstance()
        self.avantar = im.get_default('TORRENT', SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data)


class ModificationActivityItem(AvantarItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        modification = self.original_data

        self.header = "Discovered a modification by %s at %s" % (modification.peer_name, format_time(modification.inserted).lower())

        if modification.name == "swift-thumbnails":
            self.guiutility = GUIUtility.getInstance()
            self.session = self.guiutility.utility.session

            thumb_dir = os.path.join(self.session.get_torrent_collecting_dir(), 'thumbs-' + binascii.hexlify(modification.torrent.infohash))
            self.body = []
            if os.path.exists(thumb_dir):
                for single_thumb in os.listdir(thumb_dir)[:4]:
                    bmp = wx.Bitmap(os.path.join(thumb_dir, single_thumb), wx.BITMAP_TYPE_ANY)
                    if bmp.IsOk():
                        res = limit_resolution(bmp.GetSize(), (100, 100))
                        self.body.append(bmp.ConvertToImage().Scale(*res, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap())
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

        im = IconsManager.getInstance()
        self.avantar = im.get_default('MODIFICATION', SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.torrent)


class ModificationItem(AvantarItem):

    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer=0, rightSpacer=0, showChange=False, list_selected=LIST_SELECTED, list_expanded=LIST_EXPANDED):
        if isinstance(parent, wx.Dialog):
            self.noButton = True
        else:
            self.noButton = not getattr(parent_list.parent_list, 'canModify', True)
        AvantarItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)

    def AddComponents(self, leftSpacer, rightSpacer):
        modification = self.original_data

        if modification.name == "swift-thumbnails":
            self.guiutility = GUIUtility.getInstance()
            self.session = self.guiutility.utility.session

            thumb_dir = os.path.join(self.session.get_torrent_collecting_dir(), 'thumbs-' + binascii.hexlify(modification.torrent.infohash))
            self.body = []
            if os.path.exists(thumb_dir):
                for single_thumb in os.listdir(thumb_dir)[:4]:
                    bmp = wx.Bitmap(os.path.join(thumb_dir, single_thumb), wx.BITMAP_TYPE_ANY)
                    if bmp.IsOk():
                        res = limit_resolution(bmp.GetSize(), (100, 100))
                        self.body.append(bmp.ConvertToImage().Scale(*res, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap())
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

        im = IconsManager.getInstance()
        if modification.moderation:
            moderation = modification.moderation
            self.header = "%s modified by %s,\nbut reverted by %s due to: '%s'" % (modification.name.capitalize(), modification.peer_name, moderation.peer_name, moderation.message)
            self.avantar = im.get_default('REVERTED_MODIFICATION', SMALL_ICON_MAX_DIM)
            self.maxlines = 2
        else:
            self.header = "%s modified by %s at %s" % (modification.name.capitalize(), modification.peer_name, format_time(modification.time_stamp).lower())
            self.avantar = im.get_default('MODIFICATION', SMALL_ICON_MAX_DIM)

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
        self.body = "%s reverted a modification made by %s, reason '%s'" % (moderation.peer_name, moderation.by_peer_name, moderation.message)

        im = IconsManager.getInstance()
        self.avantar = im.get_default('REVERTED_MODIFICATION', SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)


class ModerationItem(AvantarItem):

    def AddComponents(self, leftSpacer, rightSpacer):
        moderation = self.original_data

        self.header = "%s reverted a modification by %s at %s" % (moderation.peer_name.capitalize(), moderation.by_peer_name, format_time(moderation.time_stamp).lower())

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
        im = IconsManager.getInstance()
        self.avantar = im.get_default('REVERTED_MODIFICATION', SMALL_ICON_MAX_DIM)

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

        im = IconsManager.getInstance()
        self.avantar = im.get_default('MARKING', SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)

    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.torrent)
