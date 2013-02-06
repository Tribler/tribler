# Written by Niels Zeilemaker, Egbert Bouman
import wx
import sys
import json
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Main.vwxGUI.widgets import NativeIcon, BetterText as StaticText, _set_font, TagText
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.IconsManager import IconsManager, SMALL_ICON_MAX_DIM
from list_body import *
from list_details import *
from _abcoll import Iterable
from datetime import timedelta
import urllib

class ColumnsManager:
    __single = None
    def __init__(self):
        if ColumnsManager.__single:
            raise RuntimeError, "ColumnsManager is singleton"
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
    
    @warnWxThread
    def AddComponents(self, leftSpacer, rightSpacer):
        if leftSpacer > 0:
            self.hSizer.AddSpacer((leftSpacer, -1))
            
        self.icons = self.GetIcons()
        if self.icons:
            iconSizer = wx.BoxSizer(wx.VERTICAL)
            for index, icon in enumerate(self.icons):
                if icon:
                    bmp = wx.StaticBitmap(self, -1, icon[0])
                    bmp.SetToolTipString(icon[1])
                    if index < len(self.icons)-1:
                        iconSizer.Add(bmp, 0, wx.CENTER|wx.BOTTOM, 7)
                    else:
                        iconSizer.Add(bmp, 0, wx.CENTER)
                    self.icons[index] = bmp
            iconSizer.AddSpacer((33, -1))
            self.hSizer.Add(iconSizer, 0, wx.ALIGN_CENTER_VERTICAL)
        else:
            self.hSizer.AddSpacer((33, -1))
            
        self.titleSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.descrSizer = wx.BoxSizer(wx.HORIZONTAL)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.titleSizer, 0, wx.TOP|wx.BOTTOM|wx.EXPAND, 3)
        vSizer.Add(self.descrSizer, 0, wx.TOP|wx.BOTTOM, 3)            
        self.hSizer.Add(vSizer, 1, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.CENTER|wx.TOP|wx.BOTTOM|wx.EXPAND, 3) 
           
        ListItem.AddComponents(self, 0, rightSpacer)
        
        #remove last line
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
                #Remove the spacer and replace it with the icon
                self.hSizer.Remove(0)
                self.hSizer.Insert(0, control.icon, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, (33-control.icon.GetSize().x)/2)            
        else:
            self.descrSizer.Add(control, 0, wx.CENTER|wx.TOP, spacing)
            
            if column_index >= 0:
                sline = wx.StaticLine(self, -1, style=wx.LI_VERTICAL)
                if sys.platform == 'win32':
                    self._add_columnresizing(sline, column_index)
                self.descrSizer.Add(sline, 0, wx.EXPAND|wx.RIGHT|wx.LEFT, 7)
            
    def _add_columnresizing(self, sline, column_index):
        sline.SetCursor(wx.StockCursor(wx.CURSOR_SIZEWE))
        # Take hidden columns into account
        control_index = len([column for column in self.columns[:column_index] if column['show']])
                    
        def OnLeftDown(event):
            eo = event.GetEventObject()
            eo.CaptureMouse()
            eo.Unbind(wx.EVT_ENTER_WINDOW)
            eo.Unbind(wx.EVT_LEAVE_WINDOW)
            eo.Bind(wx.EVT_MOTION, OnMotion)

        def OnMotion(event, control_index = control_index):
            control = self.controls[control_index]
            mouse_x = event.GetPosition().x
            width = max(0, control.GetSize().x + mouse_x)
            if getattr(self, 'buttonSizer', False):
                width = min(width, self.buttonSizer.GetPosition().x - self.descrSizer.GetPosition().x - sum([child.GetSize().x for child in self.descrSizer.GetChildren()]) + control.GetSize().x)
            else:
                pass
            control.SetMinSize((width, -1))
            self.hSizer.Layout()

        def OnLeftUp(event, column_index = column_index, control_index = control_index):
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
                            self.columns[column_index]['width'] += self.descrSizer.GetChildren()[index-1].GetSize().x
                        break

            fileconfig = wx.FileConfig(appName = "Tribler", localFilename = os.path.join(self.guiutility.frame.utility.session.get_state_dir(), "gui_settings"))
            column_sizes = fileconfig.Read("column_sizes")
            column_sizes = json.loads(column_sizes) if column_sizes else {}
            column_sizes[type(self).__name__] = column_sizes.get(type(self).__name__, {})
            column_sizes[type(self).__name__].update({self.columns[column_index]['name']: self.columns[column_index]['width']})
            fileconfig.Write("column_sizes", json.dumps(column_sizes))
            fileconfig.Flush()
            
            wx.CallAfter(self.parent_list.Rebuild)

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
            if new_icon and (new_icon[0].ConvertToImage().GetData() != self.icons[index].GetBitmap().ConvertToImage().GetData() or \
                             new_icon[1] != self.icons[index].GetToolTip().GetTip()):
                self.icons[index].SetBitmap(new_icon[0])
                self.icons[index].SetToolTipString(new_icon[1])
                self.icons[index].Show(True)
            elif not new_icon and self.icons[index]:
                self.icons[index].Show(False)

    @warnWxThread
    def OnRightClick(self, event = None):
        if len(self.columns) > 1:
            menu = self.GetContextMenu()
            if menu:
                self.PopupMenu(menu, self.ScreenToClient(wx.GetMousePosition()))
                menu.Destroy()

    @warnWxThread
    def OnShowColumn(self, event, index):
        self.columns[index]['show'] = not self.columns[index].get('show', True)
        
        fileconfig = wx.FileConfig(appName = "Tribler", localFilename = os.path.join(self.guiutility.frame.utility.session.get_state_dir(), "gui_settings"))
        
        hide_columns = fileconfig.Read("hide_columns")
        hide_columns = json.loads(hide_columns) if hide_columns else {}
        hide_columns[type(self).__name__] = hide_columns.get(type(self).__name__, {})
        hide_columns[type(self).__name__].update({self.columns[index]['name']: self.columns[index]['show']})

        fileconfig.Write("hide_columns", json.dumps(hide_columns))
        fileconfig.Flush()

        if getattr(self.parent_list.parent_list, 'ResetBottomWindow', False):
            self.parent_list.parent_list.ResetBottomWindow()        
        wx.CallAfter(self.parent_list.Rebuild)
            
    @warnWxThread        
    def GetContextMenu(self):
        menu = wx.Menu()
        show = wx.Menu()
        for index, column in enumerate(self.columns):
            itemid = wx.NewId()
            show.AppendCheckItem(itemid, column['name']).Enable(column['name'] != 'Name')
            show.Check(itemid, column.get('show', True))
            
            #Niels: 16-10-2012, apparently windows requires this event to be bound to menu, ubuntu requires it to be bound to show?
            if sys.platform == 'win32':
                menu.Bind(wx.EVT_MENU, lambda event, index=index: self.OnShowColumn(event, index), id = itemid)
            else:
                show.Bind(wx.EVT_MENU, lambda event, index=index: self.OnShowColumn(event, index), id = itemid)
            
        menu.AppendMenu(wx.ID_ANY, 'Show labels..', show)
        return menu

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
        self.hSizer.Add(self.buttonSizer, 0, wx.CENTER|wx.TOP|wx.BOTTOM|wx.EXPAND, 3)
        self.hide_buttons = True
        self.AddButtons()
        
    def AddButtons(self):
        pass
        
    def AddButton(self, label, handler):
        if handler == None or label == None:
            return

        button = ProgressButton(self, -1, label)
        button.Bind(wx.EVT_LEFT_UP, handler)
        self.AddEvents(button)
        self.buttonSizer.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 10)
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

        torcoldir    = self.guiutility.utility.session.get_torrent_collecting_dir()
        rel_thumbdir = 'thumbs-'+binascii.hexlify(self.original_data.infohash)
        abs_thumbdir = os.path.join(torcoldir, rel_thumbdir)
        if os.path.exists(abs_thumbdir):
            if not os.listdir(abs_thumbdir):
                return
            # Override the settings flags set by AddComponents
            self.controls[0].SetMinSize(self.controls[0].GetBestSize())
            self.titleSizer.Detach(self.controls[0])
            self.titleSizer.Insert(0, self.controls[0], 0, wx.CENTER)
            
            # Add icon right after the torrent title, indicating that the torrent has thumbnails
            snapshot = wx.Bitmap(os.path.join(self.guiutility.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","snapshot.png"), wx.BITMAP_TYPE_ANY)
            snapshot = wx.StaticBitmap(self, -1, snapshot)
            snapshot.SetToolTipString("This torrent has thumbnails.")
            self.AddEvents(snapshot)
            self.titleSizer.Add(snapshot, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT|wx.LEFT, 10)

    def AddButtons(self):
        self.buttonSizer.Clear(deleteWindows = True)
        
        do_add = False
        for column in self.columns:
            if column.get('name', None) == 'Name':
                do_add = column.get('dlbutton', False)
                break
        
        if do_add:
            button = self.AddButton("Download", lambda evt: self.guiutility.frame.top_bg.OnDownload(evt, [self.original_data]))
            button.Enable('completed' not in self.original_data.state)
            
    @warnWxThread        
    def GetIcons(self):
        if getattr(self.parent_list.parent_list, '_status_icon', None):
            return [self.parent_list.parent_list._status_icon(self)]
        else:
            return []
        
    @warnWxThread        
    def GetContextMenu(self):
        menu = DoubleLineListItem.GetContextMenu(self)

        itemid = wx.NewId()
        menu.AppendCheckItem(itemid, 'Show download button on hover')
        enabled = bool(len(self.buttonSizer.GetChildren()))
        menu.Check(itemid, enabled)
        menu.Bind(wx.EVT_MENU, lambda event, enabled=enabled: self.OnShowDownload(not enabled), id = itemid)
        
        menu.AppendSeparator()

        filename = self.guiutility.torrentsearch_manager.getCollectedFilename(self.original_data)
        if filename and os.path.exists(filename):
            itemid = wx.NewId()
            menu.Append(itemid, 'Export .torrent..')
            menu.Bind(wx.EVT_MENU, lambda event, filename=filename: wx.CallAfter(self.OnExportTorrent, filename), id = itemid)
        
        itemid = wx.NewId()
        menu.Append(itemid, 'Copy magnet link')
        menu.Bind(wx.EVT_MENU, lambda event, infohash=self.original_data.infohash: self.OnCopyMagnet(infohash), id = itemid)

        return menu
    
    def OnExportTorrent(self, filename):
        dlg = wx.FileDialog(self, message = "Select an export destination", defaultFile = "%s.torrent" % self.original_data.name, wildcard = "*.torrent", style = wx.FD_SAVE|wx.CHANGE_DIR|wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            paths = dlg.GetPaths()
            if os.path.exists(paths[0]):
                os.remove(paths[0])
            shutil.copyfile(filename, paths[0])
        dlg.Destroy()
        
    def OnCopyMagnet(self, infohash):
        magnetlink = "magnet:?xt=urn:btih:" + hexlify(infohash)
        trackers = self.guiutility.channelsearch_manager.torrent_db.getTracker(infohash)
        if trackers:
            for tracker,_ in trackers:
                magnetlink += "&tr="+urllib.quote_plus(tracker)
                
        if wx.TheClipboard.Open():
            magnetlinkObj = wx.TextDataObject()
            magnetlinkObj.SetText(magnetlink)
            wx.TheClipboard.SetData(magnetlinkObj)
            wx.TheClipboard.Close()
        else:
            wx.MessageBox("Unable to copy magnet link to clipboard", "Error")

    def OnShowDownload(self, show):
        for column in self.columns:
            if column.get('name', None) == 'Name':
                column['dlbutton'] = show
                break
        
        for item in self.parent_list.items.values():
            if isinstance(item, TorrentListItem):
                item.AddButtons()

        self.guiutility.WriteGuiSetting("hide_buttons", not show)      
        
    def OnDClick(self, event):
        self.guiutility.frame.top_bg.OnDownload(None, [self.original_data])
        
        
class ChannelListItem(DoubleLineListItemWithButtons):
        
    def AddComponents(self, *args, **kwargs):
        DoubleLineListItemWithButtons.AddComponents(self, *args, **kwargs)

        tag = TagText(self, -1, label='channel', fill_colour = wx.Colour(210,252,120))
        self.AddEvents(tag)
        self.titleSizer.Insert(0, tag, 0, wx.CENTER|wx.TOP, 2)
        self.titleSizer.Insert(1, (5, -1), 0, 0)
        
    def AddButtons(self):
        self.buttonSizer.Clear(deleteWindows = True)
        if not isinstance(self.parent_list.parent_list, Tribler.Main.vwxGUI.list_header.BaseFilter):
            self.AddButton("Visit channel", lambda evt: self.guiutility.showChannel(self.original_data))
        if not isinstance(self.parent_list.parent_list, Tribler.Main.vwxGUI.list.GenericSearchList):
            if self.original_data.my_vote == 2:
                self.AddButton("Remove Favorite", lambda evt, data = self.original_data: self.parent_list.parent_list.RemoveFavorite(evt, data))
            elif not self.original_data.isMyChannel():
                self.AddButton("Mark as Favorite", lambda evt, data = self.original_data: self.parent_list.parent_list.MarkAsFavorite(evt, data))
            self.last_my_vote = self.original_data.my_vote
        
    @warnWxThread
    def RefreshData(self, data):
        DoubleLineListItemWithButtons.RefreshData(self, data)
        
        if self.last_my_vote != data[2].my_vote:
            self.AddButtons()
        
    def GetIcons(self):
        return [self.guiutility.frame.channellist._special_icon(self)]
        
    def OnDClick(self, event = None):
        self.guiutility.showChannel(self.original_data)
        
    @warnWxThread        
    def SetTitleSizerHeight(self, height):
        self.titleSizer.AddSpacer((-1,height))
        
class ChannelListItemAssociatedTorrents(ChannelListItem):
    def __init__(self, *args, **kwargs):
        self.at_index = -1
        DoubleLineListItemWithButtons.__init__(self, *args, **kwargs)
        
    def AddComponents(self, *args, **kwargs):
        DoubleLineListItemWithButtons.AddComponents(self, *args, **kwargs)
        
        visible_columns = [column['name'] for column in self.columns if column['show']]
        try:
            self.at_index = visible_columns.index('Associated torrents')
            self.controls[self.at_index].SetToolTipString('This channel contains %d torrents matching your search query. The visible matches are currently highlighted.' % len(self.data[-1]))
            self.controls[self.at_index].Bind(wx.EVT_MOUSE_EVENTS, self.ShowSelected)
        except:
            pass
        
        tag = TagText(self, -1, label='channel', fill_colour = wx.Colour(210,252,120))
        self.AddEvents(tag)
        self.titleSizer.Insert(0, tag, 0, wx.CENTER|wx.TOP, 2)
        self.titleSizer.Insert(1, (5, -1), 0, 0)
        
    def ShowSelected(self, event = None):
        if event: self.OnMouse(event)
        DoubleLineListItemWithButtons.ShowSelected(self)
        
        highlight = event and event.GetEventObject() == self.controls[self.at_index] and not event.Leaving()
        
        if self.at_index >= 0:
            for torrent in self.data[-1]:
                infohash = torrent.infohash
                if infohash in self.parent_list.items:
                    torrent_item = self.parent_list.GetItem(infohash)
                    if highlight:
                        torrent_item.Highlight(colour = LIST_AT_HIGHLIST, timeout = 5, revert = True)
                    else:
                        torrent_item.ShowSelected()
                        
    def OnDClick(self, event = None):
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
        
        tag = TagText(self, -1, label='playlist', fill_colour = wx.Colour(136,117,255), text_colour = wx.WHITE)
        self.AddEvents(tag)
        self.titleSizer.Insert(0, tag, 0, wx.CENTER|wx.TOP, 2)
        self.titleSizer.Insert(1, (5, -1), 0, 0)
        
    def AddButtons(self):
        self.buttonSizer.Clear(deleteWindows = True)
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
        self.titleSizer.AddSpacer((-1,height))
        
class PlaylistItemNoButton(PlaylistItem):
    def AddButtons(self):
        pass
        
class LibraryListItem(DoubleLineListItem):
            
    def GetIcons(self):
        return [self.parent_list.parent_list._swift_icon(self)]        

    def GetContextMenu(self):
        menu = DoubleLineListItem.GetContextMenu(self)
        
        menu_items = [('Explore files', self.OnExplore)]
            
        if 'seeding' in self.original_data.state:
            menu_items.append(('Add to my channel', self.OnAddToMyChannel))
        
        for label, handler in menu_items:
            itemid = wx.NewId()
            menu.Append(itemid, label)
            menu.Bind(wx.EVT_MENU, handler, id=itemid)
        return menu

    @forceDBThread    
    def OnAddToMyChannel(self, event):
        didAdd = self.guiutility.channelsearch_manager.createTorrent(None, self.original_data)
        if didAdd:
            UserEventLogDBHandler.getInstance().addEvent(message="MyChannel: manual add from library", type = 2)
            
            #remote channel link to force reload
            del self.original_data.channel
            self.original_data.channel
            
            def gui_call():
                self.guiutility.Notify('New torrent added to My Channel', "Torrent '%s' has been added to My Channel" % self.original_data.name, icon = wx.ART_INFORMATION)
            wx.CallAfter(gui_call)
        
    def OnExplore(self, event):
        path = self._GetPath()
        if path and os.path.exists(path):
            startfile(path)
        else:
            path = DefaultDownloadStartupConfig.getInstance().get_dest_dir()
            startfile(path)
            
    def _GetPath(self, file = None):
        ds = self.original_data.ds
        if ds:
            destdirs = ds.get_download().get_dest_files()
            if file:
                for filenameintorrent, path in destdirs:
                    if filenameintorrent == file:
                        return path
                    
            return os.path.commonprefix([os.path.split(path)[0] for _,path in destdirs])


class ActivityListItem(ListItem):
    def __init__(self, *args, **kwargs):
        ListItem.__init__(self, *args, **kwargs)

    def AddComponents(self, leftSpacer, rightSpacer):
        ListItem.AddComponents(self, leftSpacer, rightSpacer)
        if self.data[0] in ['Results', 'Channels', 'Downloads']:
            self.num_items = TagText(self, -1, label='0', fill_colour=GRADIENT_DGREY, edge_colour=SEPARATOR_GREY)
            self.hSizer.Add(self.num_items, 0, wx.CENTER|wx.RIGHT, 5)
            self.hSizer.Layout()
        

class DragItem(TorrentListItem):

    def AddEvents(self, control):
        if getattr(control, 'GetWindow', False): #convert sizeritems
            control = control.GetWindow() or control.GetSizer()
        
        if getattr(control, 'Bind', False):
            control.Bind(wx.EVT_MOTION, self.OnDrag)
            
        TorrentListItem.AddEvents(self, control)
        
    def OnDrag(self, event):
        if event.LeftIsDown():
            self.parent_list.parent_list.OnDrag(self)

class AvantarItem(ListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED, list_expanded = LIST_EXPANDED):
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
            titleRow.Add(wx.StaticBitmap(self, bitmap = self.avantar), 0, wx.RIGHT, 7)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        header = wx.StaticText(self, -1, self.header)
        _set_font(header, -1, wx.FONTWEIGHT_BOLD)
        header.SetMinSize((1, -1))
        
        vSizer.Add(header, 0, wx.EXPAND)
        vSizer.Add(wx.StaticLine(self, -1, style = wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.RIGHT, 5)
        
        self.moreButton = None
        if len(self.additionalButtons) > 0:
            self.moreButton = wx.Button(self, style = wx.BU_EXACTFIT)
            
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        if len(self.additionalButtons) > 0:
            hSizer.Add(self.moreButton, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_BOTTOM)
        
            for button in self.additionalButtons:
                hSizer.Add(button, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_BOTTOM)
                button.Show(False)
                
            self.moreButton.Show(False)
                
        if isinstance(self.body, basestring):
            self.desc = MaxBetterText(self, self.body, maxLines = self.maxlines, button = self.moreButton)
            self.desc.SetMinSize((1, -1))
            vSizer.Add(self.desc, 0, wx.EXPAND)
            vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT)            
        else:
            self.desc = None
            for index, bmp in enumerate(self.body):
                sbmp = wx.StaticBitmap(self, -1, bmp)
                hSizer.Insert(index, sbmp, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 6)
            hSizer.InsertStretchSpacer(len(self.body))
            vSizer.Add(hSizer, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, 5)
        
        titleRow.Add(vSizer, 1)
        
        if rightSpacer > 0:
            titleRow.AddSpacer((rightSpacer, -1))
        self.vSizer.Add(titleRow, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, 3)
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
    
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED, list_expanded = LIST_EXPANDED):
        #check if we are part of a torrent
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
        
        self.header = "Posted %s by %s"%(format_time(comment.time_stamp).lower(), comment.name)
        self.body = comment.comment
        self.avantar = comment.avantar
        
        if depth == 0:
            if not self.inTorrent and comment.torrent:
                self.header += " in %s"%comment.torrent.name
                button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
                button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
                self.additionalButtons.append(button)
        else:
            leftSpacer += depth * (self.avantar.GetWidth() + 7)  #avantar + spacer
            
        if self.canRemove:
            button = wx.Button(self, -1, 'Remove Comment', style = wx.BU_EXACTFIT)
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
        self.header = "New comment received, posted %s by %s"%(format_time(comment.time_stamp).lower(), comment.name)
        
        if not self.inTorrent and comment.torrent:
            self.header += " in %s"%comment.torrent.name
            button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
            self.additionalButtons.append(button)
            
        self.body = comment.comment
        im = IconsManager.getInstance()
        self.avantar = im.get_default('COMMENT', SMALL_ICON_MAX_DIM)
        
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)  

class NewTorrentActivityItem(AvantarItem):
        
    def AddComponents(self, leftSpacer, rightSpacer):
        torrent = self.original_data
        
        self.header = "New torrent received at %s"%(format_time(torrent.time_stamp).lower())
        self.body = torrent.name
        
        button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
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
        
        self.header = "Discovered a torrent at %s, injected at %s"%(format_time(torrent.inserted).lower(), format_time(torrent.time_stamp).lower())
        self.body = torrent.name
        
        button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
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

        self.header = "Discovered a modification by %s at %s"%(modification.peer_name, format_time(modification.inserted).lower())

        if modification.name == "swift-thumbnails":
            self.guiutility = GUIUtility.getInstance()                    
            self.session    = self.guiutility.utility.session

            thumb_dir = os.path.join(self.session.get_torrent_collecting_dir(), 'thumbs-'+hexlify(modification.torrent.infohash))
            self.body = []
            if os.path.exists(thumb_dir):
                for single_thumb in os.listdir(thumb_dir)[:4]:
                    bmp = wx.Bitmap(os.path.join(thumb_dir, single_thumb), wx.BITMAP_TYPE_ANY)
                    if bmp.IsOk():
                        res = limit_resolution(bmp.GetSize(), (100, 100))
                        self.body.append(bmp.ConvertToImage().Scale(*res, quality = wx.IMAGE_QUALITY_HIGH).ConvertToBitmap())
            if not self.body:
                self.body = "WARNING: The thumbnails related to this modification could not be found on the filesystem."
        elif modification.name == "video-info":
            video_info = json.loads(modification.value)
            duration = timedelta(seconds=video_info['duration'])
            duration = str(duration).split('.')[0]
            self.body = "Modified the bitrate in '%s kb/s', the duration in '%s', and the resolution in '%dx%d'" % \
                        (video_info['bitrate'], duration, video_info['resolution'][0], video_info['resolution'][1])
        else: 
            self.body = "Modified %s in '%s'"%(modification.name, modification.value)
        
        if modification.torrent:
            self.header += " for torrent '%s'"%modification.torrent.colt_name
            button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
            self.additionalButtons.append(button)
        
        im = IconsManager.getInstance()
        self.avantar = im.get_default('MODIFICATION',SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
    
    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.torrent)
        
class ModificationItem(AvantarItem):
    
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED, list_expanded = LIST_EXPANDED):
        if isinstance(parent, wx.Dialog):
            self.noButton = True
        else:
            self.noButton = not getattr(parent_list.parent_list, 'canModify', True)
        AvantarItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
    
    def AddComponents(self, leftSpacer, rightSpacer):
        modification = self.original_data

        if modification.name == "swift-thumbnails":
            self.guiutility = GUIUtility.getInstance()                    
            self.session    = self.guiutility.utility.session

            thumb_dir = os.path.join(self.session.get_torrent_collecting_dir(), 'thumbs-'+hexlify(modification.torrent.infohash))
            self.body = []
            if os.path.exists(thumb_dir):
                for single_thumb in os.listdir(thumb_dir)[:4]:
                    bmp = wx.Bitmap(os.path.join(thumb_dir, single_thumb), wx.BITMAP_TYPE_ANY)
                    if bmp.IsOk():
                        res = limit_resolution(bmp.GetSize(), (100, 100))
                        self.body.append(bmp.ConvertToImage().Scale(*res, quality = wx.IMAGE_QUALITY_HIGH).ConvertToBitmap())
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
            self.header = "%s modified by %s,\nbut reverted by %s due to: '%s'"%(modification.name.capitalize(), modification.peer_name, moderation.peer_name, moderation.message)
            self.avantar = im.get_default('REVERTED_MODIFICATION',SMALL_ICON_MAX_DIM)
            self.maxlines = 2
        else:
            self.header = "%s modified by %s at %s"%(modification.name.capitalize(), modification.peer_name, format_time(modification.time_stamp).lower())
            self.avantar = im.get_default('MODIFICATION',SMALL_ICON_MAX_DIM)
        
            if not self.noButton:
                button = wx.Button(self, -1, 'Revert Modification', style = wx.BU_EXACTFIT)
                button.Bind(wx.EVT_BUTTON, self.RevertModification)
                self.additionalButtons.append(button)
        
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
        
    def RevertModification(self, event):
        self.parent_list.parent_list.OnRevertModification(self.original_data)
        
class ModerationActivityItem(AvantarItem):
    
    def AddComponents(self, leftSpacer, rightSpacer):
        moderation = self.original_data

        self.header = "Discovered a moderation %s"%(format_time(moderation.inserted).lower())
        self.body = "%s reverted a modification made by %s, reason '%s'"%(moderation.peer_name, moderation.by_peer_name, moderation.message)
        
        im = IconsManager.getInstance()
        self.avantar = im.get_default('REVERTED_MODIFICATION',SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
        
class ModerationItem(AvantarItem):
    
    def AddComponents(self, leftSpacer, rightSpacer):
        moderation = self.original_data

        self.header = "%s reverted a modification by %s at %s"%(moderation.peer_name.capitalize(), moderation.by_peer_name, format_time(moderation.time_stamp).lower())
        
        if moderation.modification:
            modification = moderation.modification
            self.body = "%s reverted due to '%s'.\n"%(modification.name.capitalize(),moderation.message)
            if moderation.severity > 0:
                self.body += "%s additionally issued a warning!\n"%moderation.peer_name.capitalize()
            self.body += "Modification was:\n%s"%modification.value
            
            if modification.torrent:
                self.header += " for torrent '%s'"%modification.torrent.name
                button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
                button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
                self.additionalButtons.append(button)
            
        else:
            self.body = moderation.message
        im = IconsManager.getInstance()
        self.avantar = im.get_default('REVERTED_MODIFICATION',SMALL_ICON_MAX_DIM)
        
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
        
    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.modification.torrent)
            
class MarkingActivityItem(AvantarItem):
    
    def AddComponents(self, leftSpacer, rightSpacer):
        marking = self.original_data

        self.header = "Discovered an opinion %s"%(format_time(marking.time_stamp).lower())
        self.body = "%s was marked as '%s'"%(marking.torrent.name, marking.type)
        
        button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
        button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        self.additionalButtons.append(button)
        
        im = IconsManager.getInstance()
        self.avantar = im.get_default('MARKING',SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)       
        
    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.torrent)     
