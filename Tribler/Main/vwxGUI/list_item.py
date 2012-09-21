# Written by Niels Zeilemaker, Egbert Bouman
import wx
import sys
import json

from Tribler.Main.vwxGUI.widgets import NativeIcon, BetterText as StaticText, _set_font, TagText
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.IconsManager import IconsManager, SMALL_ICON_MAX_DIM
from list_body import *
from list_details import *
from _abcoll import Iterable
from Tribler.Main.vwxGUI.list_header import TorrentFilter

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
            
        else:
            self.descrSizer.Add(control, 0, wx.CENTER|wx.TOP, spacing)
            
            if column_index >= 0:
                sline = wx.StaticLine(self, -1, style=wx.LI_VERTICAL)
                self.descrSizer.Add(sline, 0, wx.EXPAND|wx.RIGHT|wx.LEFT, 7)
                
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
                self.Layout()

    @warnWxThread
    def OnShowColumn(self, event, index):
        self.columns[index]['show'] = not self.columns[index].get('show', True)
        
        fileconfig = wx.FileConfig(appName = "Tribler", localFilename = os.path.join(self.guiutility.frame.utility.session.get_state_dir(), "hide_columns"))
        
        hide_columns = fileconfig.Read("hide_columns")
        hide_columns = json.loads(hide_columns) if hide_columns else {}
        hide_columns[type(self).__name__] = [column.get('show', True) for column in self.columns]

        fileconfig.Write("hide_columns", json.dumps(hide_columns))
        fileconfig.Flush()

        if getattr(self.parent_list.parent_list, 'ResetBottomWindow', False):
            self.parent_list.parent_list.ResetBottomWindow()        
        self.parent_list.Rebuild()
            
    @warnWxThread        
    def GetContextMenu(self):
        menu = wx.Menu()
        show = wx.Menu()
        for index, column in enumerate(self.columns):
            itemid = wx.NewId()
            show.AppendCheckItem(itemid, column['name']).Enable(column['name'] != 'Name')
            show.Check(itemid, column.get('show', True))
            menu.Bind(wx.EVT_MENU, lambda event, index=index: self.OnShowColumn(event, index), id = itemid)
            
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


class TorrentListItem(DoubleLineListItem):
        
    @warnWxThread        
    def GetIcons(self):
        if getattr(self.parent_list.parent_list, '_special_icon', None) and getattr(self.parent_list.parent_list, '_status_icon', None):
            return [self.parent_list.parent_list._special_icon(self), self.parent_list.parent_list._status_icon(self)]
        else:
            return []
        
class ChannelListItem(DoubleLineListItemWithButtons):
        
    def AddComponents(self, *args, **kwargs):
        # Hack to enable torrents and channels to be mixed in the search results            
        if isinstance(self.parent_list.parent_list, Tribler.Main.vwxGUI.list.GenericSearchList):
            self.columns = self.guiutility.frame.channellist.columns

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
            else:
                self.AddButton("Mark as Favorite", lambda evt, data = self.original_data: self.parent_list.parent_list.MarkAsFavorite(evt, data))
            self.last_my_vote = self.original_data.my_vote
        
    @warnWxThread
    def RefreshData(self, data):
        DoubleLineListItemWithButtons.RefreshData(self, data)
        
        if self.last_my_vote != data[2].my_vote:
            self.AddButtons()
        
    def GetIcons(self):
        return [self.guiutility.frame.channellist._special_icon(self)]
        
    def OnDClick(self, event):
        self.guiutility.showChannel(self.original_data)
        
    @warnWxThread        
    def SetTitleSizerHeight(self, height):
        self.titleSizer.AddSpacer((-1,height))

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
        # Hack to enable torrents and playlists to be mixed     
        if not isinstance(self.parent_list.parent_list, TorrentFilter) and isinstance(self.original_data, Playlist):
            self.columns = self.guiutility.frame.selectedchannellist.playlist_columns
        
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
    def __init__(self, *args, **kwargs):
        DoubleLineListItem.__init__(self, *args, **kwargs)
        
    def GetIcons(self):
        return [self.parent_list.parent_list._swift_icon(self)]        

    def GetContextMenu(self):
        menu = wx.Menu()
        show = wx.Menu()
        for index, column in enumerate(self.columns):
            itemid = wx.NewId()
            label = column['name'] if column['name'] else 'Progress'
            show.AppendCheckItem(itemid, label).Enable(label != 'Name')
            show.Check(itemid, column.get('show', True))
            menu.Bind(wx.EVT_MENU, lambda event, index=index: self.OnShowColumn(event, index), id = itemid)
            
        menu.AppendMenu(wx.ID_ANY, 'Show labels..', show)
        
        for label, handler in [('Explore files', self.OnExplore)]:
            itemid = wx.NewId()
            menu.Append(itemid, label)
            menu.Bind(wx.EVT_MENU, handler, id=itemid)
        return menu
        
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
        

class DragItem(DoubleLineListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED, list_expanded = LIST_EXPANDED):
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)

    def AddEvents(self, control):
        if getattr(control, 'GetWindow', False): #convert sizeritems
            control = control.GetWindow() or control.GetSizer()
        
        if getattr(control, 'Bind', False):
            control.Bind(wx.EVT_MOTION, self.OnDrag)
            
        ListItem.AddEvents(self, control)
        
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
        
        vSizer.Add(header, 0, wx.EXPAND)
        vSizer.Add(wx.StaticLine(self, -1, style = wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.RIGHT, 5)
        
        self.moreButton = None
        if len(self.additionalButtons) > 0:
            self.moreButton = wx.Button(self, style = wx.BU_EXACTFIT)
            
        self.desc = MaxBetterText(self, self.body, maxLines = self.maxlines, button = self.moreButton)
        self.desc.SetMinSize((1, -1))
        vSizer.Add(self.desc, 0, wx.EXPAND)
        
        if len(self.additionalButtons) > 0:
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            hSizer.Add(self.moreButton, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        
            for button in self.additionalButtons:
                hSizer.Add(button, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
                button.Show(False)
                
            self.moreButton.Show(False)
            vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT)
        
        titleRow.Add(vSizer, 1)
        
        if rightSpacer > 0:
            titleRow.AddSpacer((rightSpacer, -1))
        self.vSizer.Add(titleRow, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, 3)
        self.AddEvents(self)
        
    def BackgroundColor(self, color):
        changed = ListItem.BackgroundColor(self, color)
        
        if len(self.additionalButtons) > 0 and changed:
            if self.desc.hasMore:
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
