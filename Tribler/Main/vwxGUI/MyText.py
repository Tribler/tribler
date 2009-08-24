import wx

class MyText(wx.Panel):
    def __init__(self, parent, label, colour, font):
        wx.Panel.__init__(self, parent, -1)
        self._PostInit(parent, label, colour, font)
    
    def _PostInit(self, parent, label, colour, font):
        self.parent = parent
        self.label = label
        self.colour = colour
        self.font = font
        
        #self.bitmap = wx.Bitmap('../../icons/download.gif', wx.BITMAP_TYPE_ANY)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        #self.SetBackgroundColour(wx.NullColour)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.onErase)
#    def HasTransparentBackground(selfs):
#        return False


    def onPaint(self, event):
        #print 'Paint MyText'
        dc = wx.PaintDC(self)
        
        x, y = self.GetPositionTuple()
        l, h = dc.GetTextExtent(self.label)
        self.SetSize((l, h))
        dc2 = wx.BufferedPaintDC(self.parent)
        dc.Blit(0, 0, l, h, dc2, x, y)
        
        #dc.FloodFill(0,0, wx.RED)
        
        #dc.SetBackgroundMode(wx.TRANSPARENT)
        dc.SetTextBackground(wx.NullColour)
        dc.SetTextForeground(self.colour)
        #dc.DrawBitmap(self.bitmap, 10,10, True)

        #dc.DrawRectangle(0,0,l,h)
        #dc.GradientFillLinear((0,0,l,h),wx.RED,wx.BLUE,wx.WEST)
        dc.SetFont(self.font)
        dc.DrawText(self.label , 0, 0)
        #wx.StaticText.OnPaint(self, event)
        #event.Skip()


    def onErase(self, event):
        dc = event.GetDC()
        dc.Clear()
        
    def SetText(self, text):
        self.label = text
        wx.EVT_PAINT(self,self.onPaint)
        #self.Refresh()

    def SetFont(self, font):
        self.font = font
        wx.EVT_PAINT(self,self.onPaint)

    def SetColour(self, colour):
        self.colour = colour
        wx.EVT_PAINT(self,self.onPaint)

    def refresh(self):
        wx.EVT_PAINT(self,self.onPaint)



