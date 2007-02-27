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
        #dc.Clear()
        if self.parentImage:
            dc.DrawBitmap(self.parentImage, 0,0, True)
        else:
            parentBitmap = self.getParentBitmap()
            if parentBitmap:
                dc.DrawBitmap(parentBitmap, 0,0, True)
        
        if self.bitmap:
            dc.DrawBitmap(self.bitmap, 0,0, True)
        



    
class MyText(wx.StaticText):
    def __init__(self, parent, id, label):
        wx.StaticText.__init__(self, parent, id, label)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.onErase)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.bitmap = wx.Bitmap('../../icons/download.gif', wx.BITMAP_TYPE_ANY)
        #self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.SetBackgroundColour(None)
#    def HasTransparentBackground(selfs):
#        return False
    
    def onPaint(self, event):
        print 'Paint MyText'
        dc = wx.PaintDC(self)
        
        #dc.FloodFill(0,0, wx.RED)
        
        dc.SetBackgroundMode(wx.TRANSPARENT)
        #dc.DrawBitmap(self.bitmap, 10,10, True)
        dc.DrawText(self.GetLabel() , 0,0)
        #wx.StaticText.OnPaint(self, event)
        #event.Skip()
        
        
    def onErase(self, event):
        
        #event.Skip()
        dc = event.GetDC()
        dc.Clear()
        #dc = wx.ClientDC(self)
        #dc.DrawBitmap(self.bitmap, 0,0, True)
        print 'MyText background'
        #event.Skip()
        #print event.GetEventObject()
        

    
class ImagePanel(wx.Panel):
    def __init__(self, parent, size=None):
        wx.Panel.__init__(self, parent, -1)
        self.size = size
        self.bitmap = None  # wxPython image
        self.enabled = True
        #wx.EVT_PAINT(self, self.OnPaint)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.onErase)
         
    
    def onErase(self, event):
        pass
    
    def SetEnabled(self, e):
        if e != self.enabled:
            self.enabled = e
            if not self.enabled:
                self.SetMinSize((0,0))
            else:
                if self.bitmap:
                    self.SetMinSize(self.bitmap.GetSize())
                    self.SetSize(self.bitmap.GetSize())
                else:
                    self.SetMinSize((0,0))
                    self.SetSize((0,0))

            self.Refresh(True)
        
    def SetBitmap(self, bm):
        if bm == self.bitmap:
            return
        
        if self.size != None and bm != None:
            image = wx.ImageFromBitmap(bm)
            image.Rescape(self.size[0], self.size[1])
            bm = image.ConvertToBitmap()
        self.bitmap = bm
        if self.bitmap:
            self.SetMinSize(self.bitmap.GetSize())
            self.SetSize(self.bitmap.GetSize())
        else:
            self.SetMinSize((0,0))

        
        self.Refresh(True)
        
    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
     
        if self.bitmap and self.enabled:
            dc.DrawBitmap(self.bitmap, 0,0, True)
        
        
class SuperImagePanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1)
        
        #self.SetBackgroundColour(wx.RED)
        
        
        
        #self.up = UpImagePanel(self)
        
        
        self.up = ImageButton(self, '../../icons/download.gif', '../../icons/refresh.gif')
        #self.up.SetBitmap(wx.Bitmap('../../icons/download.gif', wx.BITMAP_TYPE_ANY))
        self.up.SetSize((50,50))
        self.up.SetPosition((0,0))
        
        self.down = ImagePanel(self)
        self.down.SetBitmap(wx.Bitmap('C:\Documents and Settings\Jan Roozenburg\Mijn documenten\Mijn afbeeldingen/147-4730_IMG.JPG', wx.BITMAP_TYPE_ANY))
        self.down.SetSize((100,100))
        self.down.SetPosition((0,0))
        
        
        #self.text.Bind(wx.EVT_PAINT, self.onErase)
        #self.Bind(wx.EVT_ERASE_BACKGROUND, self.onErase)
        #self.Bind(wx.EVT_ERASE_BACKGROUND, self.onErase)
        #self.text.SetPosition((0,0))
        #self.
        self.Show(True)

class MyApp(wx.App):
    
    def OnInit(self):
        wx.InitAllImageHandlers()
        frame = wx.Frame( None, -1, "Tribler wxPrototype", [20,20], [400,300] )
        frame.window = SuperImagePanel(frame)
        frame.CenterOnScreen()
        
        frame.Show(True)
        print "Started"
        return True

if __name__ == '__main__':
    app = MyApp(0)
    app.MainLoop()