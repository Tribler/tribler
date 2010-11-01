import wx

RADIUS = 7

class ListFooter(wx.Panel):
    def __init__(self, parent, background):
        wx.Panel.__init__(self, parent)
        self.background = wx.Brush(background)
        self.SetBackgroundColour(background)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        hSizer.AddSpacer((RADIUS, 10))
        self.GetMidPanel(hSizer)
        hSizer.AddSpacer((RADIUS, 10))
        
        self.SetSizer(hSizer)
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnResize)
        
    def GetMidPanel(self, hSizer):
        hSizer.AddStretchSpacer()
        
    def SetSpacerRight(self, diff):
        pass

    def OnPaint(self, event):
        obj = event.GetEventObject()
        dc = wx.BufferedPaintDC(obj)
        dc.Clear()
        
        w, h = self.GetClientSize()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(self.background)
        if h < 2*RADIUS:
            dc.DrawRoundedRectangle(0, h-2*RADIUS, w, 2*RADIUS, RADIUS)
        else:
            dc.DrawRoundedRectangle(0, 0, w, h, RADIUS)
        dc.DrawRectangle(0, 0, w, h-RADIUS)
    
    def OnResize(self, event):
        self.Refresh()
        event.Skip()
    
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
    def __init__(self, parent,  background, columns):
        self.columns = columns
        ListFooter.__init__(self, parent, background)
        
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
        
    def SetMessage(self, message):
        self.message.SetLabel(message)
        self.Layout()
    
    def SetEvents(self, channel):
        #removing old, binding new eventhandler
        self.channelResutls.Bind(wx.EVT_BUTTON, None)
        self.channelResutls.Bind(wx.EVT_BUTTON, channel)
        
    def EnableResults(self, state):
        self.channelResutls.Enable(state)
        
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
        self.spam.Bind(wx.EVT_BUTTON, None)
        if spam:
            self.spam.SetLabel('This is not Spam')
            self.spam.Bind(wx.EVT_BUTTON, self.remove_eventhandler)
        else:
            self.spam.SetLabel('Mark as Spam')
            self.spam.Bind(wx.EVT_BUTTON, self.spam_eventhandler)
            
        self.favorite.Bind(wx.EVT_BUTTON, None)
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