import wx
from __init__ import LIST_RADIUS, LIST_HIGHTLIGHT

class ListFooter(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.originalColor = None
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        hSizer.AddSpacer((LIST_RADIUS, 10))
        self.GetMidPanel(hSizer)
        hSizer.AddSpacer((LIST_RADIUS, 10))
        
        self.SetSizer(hSizer)
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnResize)
        
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
            dc.DrawRoundedRectangle(0, h-2*LIST_RADIUS, w, 2*LIST_RADIUS, LIST_RADIUS)
        else:
            dc.DrawRoundedRectangle(0, 0, w, h, LIST_RADIUS)
        dc.DrawRectangle(0, 0, w, h-LIST_RADIUS)
    
    def OnResize(self, event):
        self.Refresh()
        event.Skip()
    
    def Reset(self):
        pass
    
class TitleFooter(ListFooter):
    
    def GetMidPanel(self, hSizer):
        hSizer.AddStretchSpacer()
        
        self.title = wx.StaticText(self)
        hSizer.Add(self.title)
        
        self.scrollBar = hSizer.AddSpacer((0,0))
        self.scrollBar.Show(False)
        self.scrollBar.sizer = hSizer
        
    def SetTitle(self, title):
        self.Freeze()
        self.title.SetLabel(title)
        self.Layout()
        self.Thaw()
        
    def SetSpacerRight(self, right):
        if right > 0:
            dirty = False
            if self.scrollBar.GetSize()[0] != right:
                self.scrollBar.SetSpacer((right, 0))
                dirty = True
            if not self.scrollBar.IsShown():
                self.scrollBar.Show(True)
                dirty = True
            
            if dirty:
                self.scrollBar.sizer.Layout()
        else:
            if self.scrollBar.IsShown():
                self.scrollBar.Show(False)
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
                 
            label = wx.StaticText(self, i, '', style = self.columns[i].get('footer_style',0)|wx.ST_NO_AUTORESIZE, size = size)
            hSizer.Add(label, option, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
            
            if self.columns[i]['width'] == wx.LIST_AUTOSIZE:
                label.SetMinSize((1,-1))
            
            self.totals.append(label) 
        
        self.scrollBar = hSizer.AddSpacer((0,0))
        self.scrollBar.Show(False)
        self.scrollBar.sizer = hSizer
    
    def SetTotal(self, column, total):
        str_data = self.columns[column].get('fmt', str)(total)
        
        if str_data != self.totals[column].GetLabel():
            self.totals[column].SetLabel(str_data)
                
class ChannelResultFooter(ListFooter):
    def GetMidPanel(self, hSizer):
        self.message = wx.StaticText(self)
        font = self.message.GetFont()
        font.SetPointSize(font.GetPointSize()+2)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.message.SetFont(font)
        
        hSizer.Add(self.message, 0, wx.TOP|wx.BOTTOM|wx.ALIGN_BOTTOM, 3)
        hSizer.AddStretchSpacer()
        
        self.channelResutls = wx.Button(self, -1, "Channel Results")
        hSizer.Add(self.channelResutls, 0, wx.TOP|wx.BOTTOM, 3)
        
        self.blinkTimer = None
        
    def SetNrResults(self, nr_channels, keywords):
        if nr_channels == 0:
            label = 'No matching channels for "%s"'%keywords
        elif nr_channels == 1:
            label = 'Additionally, got 1 channel for "%s"'%keywords
        else:
            label = 'Additionally, got %d channels for "%s"'%(nr_channels, keywords)
        
        if label != self.message.GetLabel():
            self.message.SetLabel(label)
            if nr_channels >= 1:
                self.HighLight()
                
            if self.blinkTimer:
                self.blinkTimer.Stop()
            self.Layout()
            
        self.EnableResults(nr_channels > 0)
    
    def Revert(self):
        ListFooter.Revert(self)
        if self.blinkTimer:
            self.blinkTimer.Restart(10000)
        else:
            self.blinkTimer = wx.CallLater(10000, self.Blink)
    
    def SetEvents(self, channel):
        #removing old, binding new eventhandler
        self.channelResutls.Bind(wx.EVT_BUTTON, None)
        self.channelResutls.Bind(wx.EVT_BUTTON, channel)
        
    def EnableResults(self, state):
        self.channelResutls.Enable(state)
    
    def Reset(self):
        self.EnableResults(False)
        self.message.SetLabel('')
        if self.blinkTimer:
            self.blinkTimer.Stop()
        
class ChannelFooter(ListFooter):
    def GetMidPanel(self, hSizer):
        self.message = wx.StaticText(self)
        self.message.SetMinSize((1,-1))
        font = self.message.GetFont()
        font.SetPointSize(font.GetPointSize()+2)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.message.SetFont(font)
        hSizer.Add(self.message, 1, wx.TOP|wx.BOTTOM|wx.ALIGN_BOTTOM, 3)
        
        self.spam = wx.Button(self, -1, 'Mark as Spam')
        self.favorite = wx.Button(self, -1, 'Mark as Favorite')
        hSizer.Add(self.spam, 0, wx.TOP|wx.BOTTOM, 3)
        hSizer.Add(self.favorite, 0, wx.TOP|wx.BOTTOM, 3)
        
    def SetEvents(self, spam, favorite, remove):
        self.spam_eventhandler = spam
        self.favorite_eventhandler = favorite
        self.remove_eventhandler = remove
    
    def SetStates(self, spam, favorite):
        self.Freeze()
        self.spam.Unbind(wx.EVT_BUTTON)
        if spam:
            self.spam.SetLabel('This is not Spam')
            self.spam.Bind(wx.EVT_BUTTON, self.remove_eventhandler)
        else:
            self.spam.SetLabel('Mark as Spam')
            self.spam.Bind(wx.EVT_BUTTON, self.spam_eventhandler)
            
        self.favorite.Unbind(wx.EVT_BUTTON)
        if favorite:
            self.favorite.SetLabel('Remove Favorite')
            self.favorite.Bind(wx.EVT_BUTTON, self.remove_eventhandler)
        else:
            self.favorite.SetLabel('Mark as Favorite')
            self.favorite.Bind(wx.EVT_BUTTON, self.favorite_eventhandler)
            
        if spam:
            self.message.SetLabel("You have marked this Channel as Spam.")
        elif favorite:
            self.message.SetLabel("Thank you for marking this Channel as your Favorite.")
        else:
            self.message.SetLabel("What do you think of this Channel? Mark it as Spam or as a Favorite.")
        
        self.Layout()
        self.Thaw()
    
    def GetStates(self):
        return (self.spam.GetLabel() == 'This is not Spam', self.favorite.GetLabel() == 'Remove Favorite')