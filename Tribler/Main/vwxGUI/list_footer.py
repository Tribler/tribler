# Written by Niels Zeilemaker
import wx
from __init__ import LIST_RADIUS, LIST_HIGHTLIGHT
from list_details import AbstractDetails

from Tribler.Main.vwxGUI.tribler_topButton import BetterText as StaticText
from Tribler.community.channel.community import ChannelCommunity

from Tribler.Main.vwxGUI.tribler_topButton import BetterText as StaticText

class ListFooter(wx.Panel):
    def __init__(self, parent, radius = LIST_RADIUS):
        wx.Panel.__init__(self, parent)
        self.originalColor = None
        self.radius = radius
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        if radius > 0:
            hSizer.AddSpacer((radius, 10))
            
        self.GetMidPanel(hSizer)
        
        if radius > 0:
            hSizer.AddSpacer((radius, 10))
        
        self.SetSizer(hSizer)
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnResize)
        
        self.background = wx.Brush(self.GetBackgroundColour())
        
    def GetMidPanel(self, hSizer):
        hSizer.AddStretchSpacer()
        
    def SetSpacerRight(self, diff):
        pass

    def SetBackgroundColour(self, colour):
        if self.originalColor == None:
            self.originalColor = colour
        
        self.background = wx.Brush(colour)
        return wx.Panel.SetBackgroundColour(self, colour)

    def Blink(self):
        self.HighLight(0.15)
        wx.CallLater(300, self.HighLight, 0.15)
        
    def HighLight(self, timeout = 2.0):
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
        if h < 2*LIST_RADIUS:
            dc.DrawRoundedRectangle(0, h-2*self.radius, w, 2*self.radius, self.radius)
        else:
            dc.DrawRoundedRectangle(0, 0, w, h, self.radius)
        dc.DrawRectangle(0, 0, w, h-self.radius)
    
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
        
        self.scrollBar = hSizer.AddSpacer((0,0))
        self.scrollBar.sizer = hSizer
        
    def SetTitle(self, title):
        self.Freeze()
        self.title.SetLabel(title)
        self.Layout()
        self.Thaw()
        
    def SetSpacerRight(self, right):
        if self.scrollBar:
            right = max(3, right + 3)
            
            if self.scrollBar.GetSize()[0] != right:
                self.scrollBar.SetSpacer((right, 0))
                self.scrollBar.sizer.Layout()
        
class TotalFooter(TitleFooter):
    def __init__(self, parent, columns):
        self.columns = columns
        ListFooter.__init__(self, parent)
        
    def GetMidPanel(self, hSizer):
        self.totals = []
        
        for i in xrange(len(self.columns)):
            if self.columns[i]['width'] == wx.LIST_AUTOSIZE:
                option = 1
                size = wx.DefaultSize
            else:
                option = 0
                size = (self.columns[i]['width'],-1)
                 
            label = StaticText(self, i, '', style = self.columns[i].get('footer_style',0)|wx.ST_NO_AUTORESIZE, size = size)
            hSizer.Add(label, option, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.TOP|wx.BOTTOM, 3)
            
            if self.columns[i]['width'] == wx.LIST_AUTOSIZE:
                label.SetMinSize((1,-1))
            
            self.totals.append(label) 
        
        self.scrollBar = hSizer.AddSpacer((3,0))
        self.scrollBar.sizer = hSizer
    
    def SetTotal(self, column, total):
        str_data = self.columns[column].get('fmt', str)(total)
        self.totals[column].SetLabel(str_data)
                
class ChannelResultFooter(ListFooter):
    def GetMidPanel(self, hSizer):
        self.message = StaticText(self)
        font = self.message.GetFont()
        font.SetPointSize(font.GetPointSize()+2)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.message.SetFont(font)
        
        hSizer.Add(self.message, 0, wx.TOP|wx.BOTTOM|wx.ALIGN_BOTTOM, 3)
        hSizer.AddStretchSpacer()
        
        self.channelResults = wx.Button(self, -1, "Channel Results")
        hSizer.Add(self.channelResults, 0, wx.TOP|wx.BOTTOM, 3)
        
    def SetLabel(self, label, nr_channels):
        haveResults = True if nr_channels and nr_channels >= 1 else False
        
        if label != self.message.GetLabel():
            self.message.SetLabel(label)
            
            if haveResults:
                self.HighLight()
            self.Layout()
        
        self.EnableResults(haveResults)
    
    def SetEvents(self, channel):
        #removing old, binding new eventhandler
        self.channelResults.Unbind(wx.EVT_BUTTON)
        self.channelResults.Bind(wx.EVT_BUTTON, channel)
        
    def EnableResults(self, state):
        self.channelResults.Enable(state)
    
    def Reset(self):
        self.EnableResults(False)
        self.message.SetLabel('')
        
class ChannelFooter(ListFooter):
    def GetMidPanel(self, hSizer):
        self.hSizer = hSizer
        
        self.message = StaticText(self)
        self.message.SetMinSize((1,-1))
        font = self.message.GetFont()
        font.SetPointSize(font.GetPointSize()+2)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.message.SetFont(font)
        
        self.subtitle = wx.StaticText(self)
        self.subtitle.SetMinSize((1,-1))
        
        self.manage = wx.Button(self, -1, 'Edit this Channel')
        self.spam = wx.Button(self, -1, 'Mark as Spam')
        self.favorite = wx.Button(self, -1, 'Mark as Favorite')
        self.ortext = None
        
        self.subtitle.Show(False)
        self.favorite.Show(False)
        self.spam.Show(False)
        self.manage.Show(False)
        
    def SetEvents(self, spam, favorite, remove, manage):
        self.spam_eventhandler = spam
        self.favorite_eventhandler = favorite
        self.remove_eventhandler = remove
        self.manage.Bind(wx.EVT_BUTTON, manage)
    
    def SetStates(self, vote, channelstate, iamModerator):
        self.Freeze()
        self.hSizer.Clear()
        
        explicit_vote = vote != 0
        preview = not explicit_vote and not iamModerator
        open2edit = channelstate == ChannelCommunity.CHANNEL_CLOSED and iamModerator
        allow2edit = vote == 2 and channelstate == ChannelCommunity.CHANNEL_OPEN
        
        self.favorite.Show(False)
        self.spam.Show(False)
        self.manage.Show(False)
        
        #clean up old ortext statictext
        if not preview and self.ortext and explicit_vote:
            self.ortext.Destroy()
            self.ortext = None
        
        header = ''
        msg = ''
        buttonSizer = None
        if preview:
            header = "You are looking at a preview of this Channel."
            msg = "If you want to see more of it, press the 'Mark as Favorite' button.\nTribler will then more aggressively download updates making sure you always have access to the newest content."
            
            self.spam.SetLabel('Mark as Spam')
            self.spam.Bind(wx.EVT_BUTTON, self.spam_eventhandler)
            self.spam.Show(True)
            
            self.ortext = wx.StaticText(self, -1, 'or')
                
            self.favorite.SetLabel('Mark as Favorite')
            self.favorite.Bind(wx.EVT_BUTTON, self.favorite_eventhandler)
            self.favorite.Show(True)
            
            buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
            buttonSizer.Add(self.spam)
            buttonSizer.Add(self.ortext, 0, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTRE_VERTICAL, 3)
            buttonSizer.Add(self.favorite)
            
        else:
            if open2edit:
                header = "You can now enable community-features for this Channel."
                msg = "Allowing other users to comment, modify and improve meta-data will increase .\nEdit your channel settings to get started."
                
                self.manage.Show(True)
                buttonSizer = self.manage
                
            elif allow2edit:
                header  = "This is an open community. You can modify, comment and add new content. Feel free to do so."
                
                self.manage.Show(True)
                buttonSizer = self.manage
        
            if vote == -1:
                header = ''
                msg = "You have marked this Channel as Spam."
                    
                self.spam.SetLabel('This is not Spam')
                self.spam.Bind(wx.EVT_BUTTON, self.remove_eventhandler)
                self.spam.Show(True)
                buttonSizer = self.spam
                    
            elif vote == 2:
                if msg == '':
                    msg = "Thank you for marking this Channel as your Favorite."
                
                self.favorite.SetLabel('Remove Favorite')
                self.favorite.Bind(wx.EVT_BUTTON, self.remove_eventhandler)
                self.favorite.Show(True)
                
                if buttonSizer:
                    sizer = wx.BoxSizer(wx.HORIZONTAL)
                    sizer.Add(buttonSizer)
                    sizer.Add(self.favorite)
                    buttonSizer = sizer
                else:
                    buttonSizer = self.favorite
                
            else:
                if msg == '':
                    msg = "You can edit this channel"
                
                self.manage.Show(True)
                buttonSizer = self.manage
        
        if header != '':
            self.message.SetLabel(header)
            self.subtitle.SetLabel(msg)
            self.subtitle.Show(True)
            
            vSizer = wx.BoxSizer(wx.VERTICAL)
            vSizer.Add(self.message, 0, wx.EXPAND)
            if buttonSizer:
                if preview:
                    vSizer.Add(self.subtitle, 0, wx.EXPAND)
                    vSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, 10)
                else:
                    sizer = wx.BoxSizer(wx.HORIZONTAL)
                    sizer.Add(self.subtitle, 1, wx.EXPAND)
                    sizer.Add(buttonSizer, 0, wx.TOP|wx.BOTTOM|wx.RIGHT, 3)
                    vSizer.Add(sizer, 0, wx.EXPAND)
            else:
                vSizer.Add(self.subtitle, 0, wx.EXPAND)
            
            self.hSizer.Add(vSizer, 1, wx.EXPAND|wx.ALL, 7)
        else:
            self.message.SetLabel(msg)
            self.subtitle.Show(False)
            self.hSizer.Add(self.message, 1, wx.TOP|wx.BOTTOM|wx.ALIGN_BOTTOM|wx.LEFT, 7)
            self.hSizer.Add(buttonSizer, 0, wx.TOP|wx.BOTTOM|wx.RIGHT, 7)
                
        self.hSizer.Layout()
        self.Layout()
        self.Thaw()
    
    def GetStates(self):
        return (self.spam.GetLabel() == 'This is not Spam', self.favorite.GetLabel() == 'Remove Favorite')
    
class PlaylistFooter(ListFooter):
    
    def SetStates(self, vote, channelstate, iamModerator):
        pass
    
    def GetStates(self):
        return True, True

class ManageChannelFilesFooter(ListFooter):
    def __init__(self, parent, removeall, removesel, add):
        ListFooter.__init__(self, parent, 0)
        self.removeall.Bind(wx.EVT_BUTTON, removeall)
        self.removesel.Bind(wx.EVT_BUTTON, removesel)
        self.add.Bind(wx.EVT_BUTTON, add)
        
    def GetMidPanel(self, hSizer):
        hSizer.AddStretchSpacer()
        
        self.removesel = wx.Button(self, -1, "Remove Selected")
        self.removeall = wx.Button(self, -1, "Remove All")
        self.add = wx.Button(self, -1, "+ Add...")
        
        hSizer.Add(self.removesel, 0, wx.TOP|wx.BOTTOM, 3)
        hSizer.Add(self.removeall, 0, wx.TOP|wx.BOTTOM, 3)
        hSizer.Add(self.add, 0, wx.TOP|wx.BOTTOM, 3)
    
    def SetState(self, canDelete, canAdd):
        self.removesel.Show(canDelete)
        self.removeall.Show(canDelete)
        self.add.Show(canAdd)
        
class ManageChannelPlaylistFooter(ListFooter):
    def __init__(self, parent, createnew):
        ListFooter.__init__(self, parent, 0)
        self.addnew.Bind(wx.EVT_BUTTON, createnew)
    
    def GetMidPanel(self, hSizer):
        hSizer.AddStretchSpacer()
        
        self.addnew = wx.Button(self, -1, "Create New")
        self.removesel = wx.Button(self, -1, "Remove Selected")
        self.removeall = wx.Button(self, -1, "Remove All")
        
        hSizer.Add(self.addnew, 0, wx.TOP|wx.BOTTOM, 3)
        hSizer.Add(self.removesel, 0, wx.TOP|wx.BOTTOM, 3)
        hSizer.Add(self.removeall, 0, wx.TOP|wx.BOTTOM, 3)
        
class CommentFooter(ListFooter, AbstractDetails):
    def __init__(self, parent, createnew, quickPost):
        self.quickPost = quickPost
        
        ListFooter.__init__(self, parent, 0)
        self.addnew.Bind(wx.EVT_BUTTON, createnew)
        
        if quickPost:
            self.quickAdd.Bind(wx.EVT_BUTTON, quickPost)
    
    def GetMidPanel(self, sizer):
        vSizer = wx.BoxSizer(wx.VERTICAL)
        self._add_header(self, vSizer, 'Post a comment')
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.commentbox = wx.TextCtrl(self, style = wx.TE_MULTILINE)
        
        hSizer.Add(self.commentbox, 1, wx.EXPAND)
        
        self.addnew = wx.Button(self, -1, 'Post')
        self.quickAdd = None
        if self.quickPost:
            self.quickAdd = wx.Button(self, -1, "Post\n'Thanks'")
            
            postSizer = wx.BoxSizer(wx.VERTICAL)
            postSizer.Add(self.quickAdd)
            postSizer.AddStretchSpacer()
            postSizer.Add(self.addnew)
            hSizer.Add(postSizer, 0, wx.LEFT|wx.EXPAND, 3)
        else:
            hSizer.Add(self.addnew, 0, wx.ALIGN_BOTTOM|wx.LEFT, 3)
            
        vSizer.Add(hSizer, 0, wx.EXPAND|wx.ALL, 3)
        sizer.Add(vSizer, 1, wx.EXPAND)
    
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
