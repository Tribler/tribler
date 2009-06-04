import wx
 
class NewStaticText(wx.StaticText):
    def __init__(self, parent, label, colour, font):
        wx.Panel.__init__(self, parent, -1)
        self.parent = parent
        self.label = label
        self.font = font
        self.colour = colour
        #self.SetLabel(label)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.Bind(wx.EVT_PAINT, self.OnPaint)        
        
    def OnPaint(self, event):
        x, y = self.GetPositionTuple()
        dc = wx.PaintDC(self)
        l, h = dc.GetTextExtent(self.label)
        self.SetSize((l, h))
        dc = wx.PaintDC(self)
        dc2 = wx.BufferedPaintDC(self.parent)
        dc.Blit(0, 0, l, h, dc2, x, y)
        dc.SetTextBackground(wx.NullColour)
        dc.SetTextForeground(self.colour)
        ##dc.SetBackgroundMode(wx.TRANSPARENT)
        ##dc.SetBrush(wx.Brush((0,0,0),wx.TRANSPARENT))
        dc.SetFont(self.font)
        dc.DrawText(self.label, 0, 0)


    def SetColour(self, colour):
        self.colour = colour
        wx.EVT_PAINT(self,self.OnPaint)


    def SetText(self, text):
        self.label = text
        #self.Refresh()
        
        wx.EVT_PAINT(self,self.OnPaint)



    def OnErase(self, evt):
        pass


    def Paint(self, evt):
        dc = wx.PaintDC(self)
        dc.Clear()
        dc.SetTextForeground((0,105,156))
        dc.SetFont(self.font)
        dc.DrawText(self.label, 0, 0)
