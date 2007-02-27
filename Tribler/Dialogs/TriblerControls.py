import wx

class ImageButton(wx.Panel):
    """
    Button that changes the image shown if you move your mouse over it.
    It redraws the background of the parent Panel, if this is an imagepanel with
    a variable self.bitmap.
    """
    def __init__(self, parent, mouseOverFilename, mouseOutFilename = None, parentImage = None):
        wx.Panel.__init__(self, parent, -1)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        
        self.onbitmap = wx.Bitmap(mouseOverFilename, wx.BITMAP_TYPE_ANY)
        if mouseOutFilename:
            self.offbitmap = wx.Bitmap(mouseOutFilename, wx.BITMAP_TYPE_ANY)
            self.bitmap = self.offbitmap
        else:
            self.offbitmap = self.onbitmap
            self.bitmap = self.onbitmap
        
        self.parentImage = parentImage

        self.SetMinSize(self.onbitmap.GetSize())
        self.SetSize(self.onbitmap.GetSize())
    
        
        wx.EVT_PAINT(self, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.Refresh(True)
        self.Update()
        
    def mouseAction(self, event):
        if event.Entering():
            print 'enter' 
            self.bitmap = self.onbitmap
            self.Refresh()
        elif event.Leaving():
            self.bitmap = self.offbitmap
            print 'leave'
            self.Refresh()
        elif event.ButtonUp():
            self.ClickedButton()
        #event.Skip()
        
    def ClickedButton(self):
        print 'Click'
        
    
    def OnErase(self, event):
        pass
        #event.Skip()
        
        
#        dc = event.GetDC()
#        dc.SetBackgroundMode(wx.TRANSPARENT)
#        brush = wx.Brush(wx.NullColour, wx.TRANSPARENT)
#        dc.SetBackground(brush)
#        dc.Clear()
        #dc.Clear()
#        print 'DownImage background'
#        if event.GetEventObject() != self:
#            print 'DownImage bg called by %s'% event.GetEventObject()
                
    def getParentBitmap(self):
        try:
            parent = self.GetParent()
            bitmap = parent.bitmap
        except:
            return None
        location = self.GetPosition()
        location[0] -= parent.GetPosition()[0]
        location[1] -= parent.GetPosition()[1]
        if bitmap:
            newBitmap = bitmap.GetSubBitmap(wx.Rect(location[0], location[1], self.GetSize()[0], self.GetSize()[1]))
            return newBitmap
        else:
            return None
                                            
        
    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        dc.Clear()
        if self.parentImage:
            dc.DrawBitmap(self.parentImage, 0,0, True)
        else:
            parentBitmap = self.getParentBitmap()
            if parentBitmap:
                dc.DrawBitmap(parentBitmap, 0,0, True)
        
        if self.bitmap:
            dc.DrawBitmap(self.bitmap, 0,0, True)
        

