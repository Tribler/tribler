# Written by Niels Zeilemaker
import wx

from wx.html import HtmlWindow
from __init__ import LIST_RADIUS, LIST_HIGHTLIGHT
from list_details import AbstractDetails

from Tribler.Main.vwxGUI.widgets import BetterText as StaticText, TextCtrl
from Tribler.community.channel.community import ChannelCommunity


class ListFooter(wx.Panel):

    def __init__(self, parent, radius=0, spacers = [0, 0]):
        wx.Panel.__init__(self, parent)
        self.SetForegroundColour(parent.GetForegroundColour())

        self.originalColor = None
        self.radius = radius
        self.spacers = spacers

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        if radius + spacers[0] > 0:
            hSizer.AddSpacer((radius + spacers[0], 10))

        midSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.GetMidPanel(midSizer)
        hSizer.Add(midSizer, 1, wx.EXPAND)

        if radius + spacers[1] > 0:
            hSizer.AddSpacer((radius + spacers[1], 10))

        self.SetSizer(hSizer)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnResize)

        self.background = wx.Brush(self.GetBackgroundColour())

    def GetMidPanel(self, hSizer):
        hSizer.AddStretchSpacer()

    def SetBackgroundColour(self, colour):
        if self.originalColor == None:
            self.originalColor = colour

        self.background = wx.Brush(colour)
        return wx.Panel.SetBackgroundColour(self, colour)

    def Blink(self):
        self.HighLight(0.15)
        wx.CallLater(300, self.HighLight, 0.15)

    def HighLight(self, timeout=2.0):
        self.SetBackgroundColour(LIST_HIGHTLIGHT)
        self.Refresh()
        wx.CallLater(timeout * 1000, self.Revert)

    def Revert(self):
        self.SetBackgroundColour(self.originalColor)
        self.Refresh()

    def OnPaint(self, event):
        obj = event.GetEventObject()
        dc = wx.BufferedPaintDC(obj)
        dc.Clear()

        w, h = self.GetClientSize()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(self.background)
        if h < 2 * LIST_RADIUS:
            dc.DrawRoundedRectangle(0, h - 2 *self.radius, w, 2*self.radius, self.radius)
        else:
            dc.DrawRoundedRectangle(0, 0, w, h, self.radius)
        dc.DrawRectangle(0, 0, w, h - self.radius)

    def OnResize(self, event):
        self.Refresh()
        event.Skip()

    def Reset(self):
        pass


class TitleFooter(ListFooter):

    def GetMidPanel(self, hSizer):
        hSizer.AddStretchSpacer()

        self.title = StaticText(self)
        hSizer.Add(self.title)

        self.scrollBar = hSizer.AddSpacer((0, 0))
        self.scrollBar.sizer = hSizer

    def SetTitle(self, title):
        self.Freeze()
        self.title.SetLabel(title)
        self.Layout()
        self.Thaw()


class TotalFooter(TitleFooter):

    def __init__(self, parent, columns, radius=LIST_RADIUS):
        self.columns = columns
        ListFooter.__init__(self, parent, radius)

    def GetMidPanel(self, hSizer):
        self.totals = []

        for i in xrange(len(self.columns)):
            if self.columns[i]['width'] == wx.LIST_AUTOSIZE:
                option = 1
                size = wx.DefaultSize
            else:
                option = 0
                size = (self.columns[i]['width'], -1)

            label = StaticText(self, i, '', style= self.columns[i].get('footer_style', 0) | wx.ST_NO_AUTORESIZE, size = size)
            hSizer.Add(label, option, wx.ALIGN_CENTER_VERTICAL | wx.LEFT |wx.TOP|wx.BOTTOM, 3)

            if self.columns[i]['width'] == wx.LIST_AUTOSIZE:
                label.SetMinSize((1, -1))

            self.totals.append(label)

        self.scrollBar = hSizer.AddSpacer((3, 0))
        self.scrollBar.sizer = hSizer

    def SetTotal(self, column, total, tooltip=None):
        str_data = self.columns[column].get('fmt', str)(total)
        self.totals[column].SetLabel(str_data)
        if tooltip:
            self.totals[column].SetToolTipString(tooltip)


class ChannelResultFooter(ListFooter):

    def GetMidPanel(self, hSizer):
        self.message = StaticText(self)
        font = self.message.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.message.SetFont(font)

        hSizer.Add(self.message, 0, wx.TOP | wx.BOTTOM |wx.ALIGN_BOTTOM, 3)
        hSizer.AddStretchSpacer()

        self.channelResults = wx.Button(self, -1, "Channel Results")
        hSizer.Add(self.channelResults, 0, wx.TOP | wx.BOTTOM, 3)

    def SetLabel(self, label, nr_channels):
        haveResults = True if nr_channels and nr_channels >= 1 else False

        if label != self.message.GetLabel():
            self.message.SetLabel(label)

            if haveResults:
                self.HighLight()
            self.Layout()

        self.EnableResults(haveResults)

    def SetEvents(self, channel):
        # removing old, binding new eventhandler
        self.channelResults.Unbind(wx.EVT_BUTTON)
        self.channelResults.Bind(wx.EVT_BUTTON, channel)

    def EnableResults(self, state):
        self.channelResults.Enable(state)

    def Reset(self):
        self.EnableResults(False)
        self.message.SetLabel('')


class ChannelListFooter(ListFooter):

    def GetMidPanel(self, hSizer):
        self.manualAdd = wx.Button(self, -1, "Add Favorite channel")

        hSizer.AddStretchSpacer()
        hSizer.Add(self.manualAdd, 0, wx.TOP | wx.BOTTOM, 3)
        return hSizer

    def SetEvents(self, onAdd):
        self.manualAdd.Bind(wx.EVT_BUTTON, onAdd)

    def EnableAdd(self, state):
        self.manualAdd.Show(state)

    def Reset(self):
        self.EnableAdd(False)


class PlaylistFooter(ListFooter):

    def SetStates(self, vote, channelstate, iamModerator):
        pass

    def GetStates(self):
        return True, True


class ManageChannelFilesFooter(ListFooter):

    def __init__(self, parent, removeall, removesel, add, export):
        ListFooter.__init__(self, parent, 0)
        self.removeall.Bind(wx.EVT_BUTTON, removeall)
        self.removesel.Bind(wx.EVT_BUTTON, removesel)
        self.add.Bind(wx.EVT_BUTTON, add)
        self.export.Bind(wx.EVT_BUTTON, export)

    def GetMidPanel(self, hSizer):
        hSizer.AddStretchSpacer()

        self.removesel = wx.Button(self, -1, "Remove Selected")
        self.removeall = wx.Button(self, -1, "Remove All")
        self.add = wx.Button(self, -1, "+ Add...")
        self.export = wx.Button(self, -1, "Export All .torrents")

        hSizer.Add(self.removesel, 0, wx.TOP | wx.BOTTOM, 3)
        hSizer.Add(self.removeall, 0, wx.TOP | wx.BOTTOM, 3)
        hSizer.Add(self.add, 0, wx.TOP | wx.BOTTOM, 3)
        hSizer.Add(self.export, 0, wx.TOP | wx.BOTTOM, 3)

    def SetState(self, canDelete, canAdd):
        self.removesel.Show(canDelete)
        self.removeall.Show(canDelete)
        self.add.Show(canAdd)
        self.export.Show(canDelete)


class ManageChannelPlaylistFooter(ListFooter):

    def __init__(self, parent, createnew):
        ListFooter.__init__(self, parent, 0)
        self.addnew.Bind(wx.EVT_BUTTON, createnew)

    def GetMidPanel(self, hSizer):
        hSizer.AddStretchSpacer()

        self.addnew = wx.Button(self, -1, "Create New")
        hSizer.Add(self.addnew, 0, wx.TOP | wx.BOTTOM, 3)

    def SetState(self, canDelete, canAdd):
        self.addnew.Show(canDelete)


class CommentFooter(ListFooter, AbstractDetails):

    def __init__(self, parent, createnew, quickPost, horizontal):
        self.quickPost = quickPost
        self.horizontal = horizontal

        if quickPost and not horizontal:
            spacers = [3, 3]
        else:
            spacers = [7, 7]
        ListFooter.__init__(self, parent, 0, spacers=spacers)
        self.addnew.Bind(wx.EVT_BUTTON, createnew)

        if quickPost:
            self.quickAdd.Bind(wx.EVT_BUTTON, quickPost)

    def GetMidPanel(self, topsizer):
        vSizer = wx.BoxSizer(wx.VERTICAL)
#        self._add_header(self, vSizer, 'Post a comment', spacer = 0)

        self.commentbox = TextCtrl(self, style=wx.TE_MULTILINE)
        self.commentbox.SetDescriptiveText('Type in your comment here')
        if self.horizontal:
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.AddSpacer((-1, 7))
            self.commentbox.SetMinSize((200, -1))
            sizer.Add(self.commentbox, 1, wx.EXPAND)
        else:
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            self.commentbox.SetMinSize((-1, 70))
            sizer.Add(self.commentbox, 1, wx.EXPAND | wx.TOP, 7)

        if self.horizontal:
            sizer.AddSpacer((-1, 7))

        self.addnew = wx.Button(self, -1, 'Post')
        self.quickAdd = None
        if self.quickPost:
            if self.horizontal:
                self.quickAdd = wx.Button(self, -1, "Post 'Thanks'")
                postSizer = wx.BoxSizer(wx.HORIZONTAL)
            else:
                self.quickAdd = wx.Button(self, -1, "Post\n'Thanks'")
                postSizer = wx.BoxSizer(wx.VERTICAL)

            postSizer.Add(self.quickAdd)
            postSizer.AddStretchSpacer()
            postSizer.Add(self.addnew)
            sizer.Add(postSizer, 0, wx.EXPAND | wx.LEFT, 3)
        else:
            sizer.Add(self.addnew, 0, wx.ALIGN_BOTTOM | wx.LEFT, 3)

        vSizer.Add(sizer, 1, wx.EXPAND | wx.BOTTOM, self.spacers[0])
        topsizer.Add(vSizer, 1, wx.EXPAND)

    def GetComment(self):
        return self.commentbox.GetValue()

    def SetComment(self, value):
        self.commentbox.SetValue(value)

    def SetReply(self, reply):
        if reply:
            self.addnew.SetLabel('Reply')
        else:
            self.addnew.SetLabel('Post')
        self.Layout()

    def EnableCommeting(self, enable):
        self.commentbox.Enable(enable)
        self.addnew.Enable(enable)
        if self.quickAdd:
            self.quickAdd.Enable(enable)
