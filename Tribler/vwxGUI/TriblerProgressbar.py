import wx, os, sys
import wx.xrc as xrc

class TriblerProgressbar(wx.Panel):
    """
    Progressbar with percentage and ETA
    """
    def __init__(self, *args, **kw):
        if len(args) == 0: 
            self.backgroundColour = wx.Colour(102,102,102) 
            self.percentage = 0.0
            self.eta = '?'
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            self.backgroundColour = wx.Colour(102,102,102) 
            self.percentage = 0
            self.eta = '?'
            wx.Panel.__init__(self, *args, **kw) 
            self._PostInit()
            
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.createBackgroundImage()
        self.Refresh(True)
        self.Update()
        
        
    def setPercentage(self, p):
        self.percentage = p
        self.Refresh()
        
    def setETA(self, eta):
        self.eta = eta
        self.Refresh()
    
    def createBackgroundImage(self):
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        
        
        
    def OnErase(self, event):
        pass
        #event.Skip()
        
    def OnPaint(self, evt):
        obj = evt.GetEventObject()
        dc = wx.BufferedPaintDC(obj)
        dc.SetBackground(wx.Brush(self.backgroundColour))
        dc.Clear()
        size = self.GetSize()
        fillwidth = int((size[0])*self.percentage/100.0)
        dc.SetPen(wx.BLACK_PEN)
        dc.SetBrush(wx.BLUE_BRUSH)
        dc.DrawRoundedRectangle(0,0,fillwidth, size[1], 3)
        dc.SetFont(wx.Font(6, wx.SWISS, wx.NORMAL, wx.NORMAL, False))
        dc.DrawText('%.1f %%' % self.percentage, 3, 3)
        dc.DrawText(self.eta, size[0]-50, 3)
        evt.Skip()
        

