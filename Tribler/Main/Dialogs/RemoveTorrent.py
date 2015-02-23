# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import wx

from Tribler.Main.vwxGUI.widgets import _set_font, BetterText as StaticText, EditText
from Tribler.community.channel.community import ChannelCommunity
from wx.lib.wordwrap import wordwrap


class RemoveTorrent(wx.Dialog):

    def __init__(self, parent, torrents):
        canEdit = False
        single = len(torrents) == 1
        if single and torrents[0].hasChannel():
            state = torrents[0].channel.getState()
            canEdit = state >= ChannelCommunity.CHANNEL_OPEN

        wx.Dialog.__init__(self, parent, -1, 'Are you sure you want to remove the selected torrent%s?' %
                           ('' if single else 's'), size=(600, -1), name="RemoveTorrent")
        bitmap = wx.ArtProvider.GetBitmap(wx.ART_QUESTION, wx.ART_MESSAGE_BOX)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticBitmap(self, -1, bitmap), 0, wx.RIGHT, 10)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        firstLine = StaticText(self, -1, '')
        _set_font(firstLine, fontweight=wx.FONTWEIGHT_BOLD)
        if single:
            firstLineMsg = "Delete '%s' from disk, or just remove it from your downloads?" % torrents[0].name
        else:
            firstLineMsg = "Delete %s torrents from disk, or just remove them from your downloads?" % len(torrents)
        cdc = wx.ClientDC(firstLine)
        cdc.SetFont(firstLine.GetFont())
        firstLineMsg = wordwrap(firstLineMsg, self.GetSize()[
                                0] - bitmap.GetSize()[0] - 30, cdc, breakLongWords=True, margin=0)
        firstLine.SetLabel(firstLineMsg)
        firstLine.SetMinSize((1, -1))
        vSizer.Add(firstLine, 0, wx.EXPAND | wx.BOTTOM, 3)
        vSizer.Add(StaticText(self, -1, "Removing from disk will move the selected item%s to your trash." %
                   ('' if single else 's')), 0, wx.EXPAND)

        vSizer.AddStretchSpacer()

        self.newName = None
        if single and canEdit:
            vSizer.Add(
                StaticText(self, -1, "While we're at it, can you improve the name of this torrent?"), 0, wx.EXPAND | wx.BOTTOM, 3)
            self.newName = EditText(self, torrents[0].name)
            vSizer.Add(self.newName, 0, wx.EXPAND)
            vSizer.AddStretchSpacer()

        bSizer = wx.BoxSizer(wx.HORIZONTAL)
        bSizer.AddStretchSpacer()

        bSizer.Add(wx.Button(self, wx.ID_CANCEL), 0, wx.RIGHT, 3)
        bSizer.Add(wx.Button(self, wx.ID_DEFAULT, 'Only delete from downloads'), 0, wx.RIGHT, 3)
        bSizer.Add(wx.Button(self, wx.ID_DELETE, 'Also delete from disk'))

        vSizer.Add(bSizer, 0, wx.ALIGN_RIGHT | wx.TOP, 7)
        hSizer.Add(vSizer, 1, wx.EXPAND)

        border = wx.BoxSizer()
        border.Add(hSizer, 1, wx.ALL | wx.EXPAND, 10)

        self.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(event.GetId()))
        self.SetSizer(border)
        self.SetSize((-1, self.GetBestSize()[1]))
        self.Layout()
        self.CenterOnParent()
