# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import wx
import os
import sys

from Tribler.Main.vwxGUI.tribler_topButton import _set_font, BetterText as StaticText,\
    EditText
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import TRIBLER_TORRENT_EXT
from threading import Event
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.vwxGUI import forceWxThread
from traceback import print_exc
from Tribler.community.channel.community import ChannelCommunity

class RemoveTorrent(wx.Dialog):
    def __init__(self, parent, torrent):
        canEdit = canComment = False
        if torrent.hasChannel():
            state, iamModerator = torrent.channel.getState()
            canEdit = state >= ChannelCommunity.CHANNEL_OPEN
        
        height = 125
        if canEdit:
            height = 200
        
        wx.Dialog.__init__(self, parent, -1, 'Are you sure you want to remove this torrent?', size=(600, height))
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticBitmap(self, -1, wx.ArtProvider.GetBitmap(wx.ART_QUESTION, wx.ART_MESSAGE_BOX)), 0, wx.RIGHT, 10)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        firstLine = StaticText(self, -1, "Delete '%s' from disk, or just remove them from your downloads?"%torrent.name)
        _set_font(firstLine, fontweight = wx.FONTWEIGHT_BOLD)
        firstLine.SetMinSize((1, -1))
        
        vSizer.Add(firstLine, 0, wx.EXPAND|wx.BOTTOM, 3)
        vSizer.Add(StaticText(self, -1, "Removing from disk will move the selected item to your trash."), 0, wx.EXPAND)
        
        vSizer.AddStretchSpacer()
        
        self.newName = None
        if canEdit:
            vSizer.Add(StaticText(self, -1, "While we're at it, can you improve the name of this torrent?"), 0, wx.EXPAND|wx.BOTTOM, 3)
            self.newName = EditText(self, torrent.name)
            vSizer.Add(self.newName, 0, wx.EXPAND)
            vSizer.AddStretchSpacer()
        
        bSizer = wx.BoxSizer(wx.HORIZONTAL)
        bSizer.AddStretchSpacer()
        
        bSizer.Add(wx.Button(self, wx.ID_CANCEL), 0, wx.RIGHT, 3)
        bSizer.Add(wx.Button(self, wx.ID_DEFAULT, 'Only delete from downloads'), 0, wx.RIGHT, 3)
        bSizer.Add(wx.Button(self, wx.ID_DELETE, 'Also delete from disk'))
        
        vSizer.Add(bSizer, 0, wx.ALIGN_RIGHT|wx.TOP, 7)
        hSizer.Add(vSizer, 1, wx.EXPAND)
        
        border = wx.BoxSizer()
        border.Add(hSizer, 1, wx.ALL|wx.EXPAND, 10)
        
        self.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(event.GetId()))
        self.SetSizer(border)
        self.Layout()
        self.CenterOnParent()