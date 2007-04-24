import wx, os, sys
import wx.xrc as xrc

class TriblerProgressbar(wx.Panel):
    """
    Progressbar with percentage and ETA
    """
    def __init__(self, *args, **kw):
        if len(args) == 0: 
            self.backgroundColour = wx.WHITE 
            self.percentage = 0.0
            self.eta = '?'
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            self.backgroundColour = wx.WHITE
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
        
        # draw around rect
        dc.SetPen(wx.BLACK_PEN)
        dc.SetBrush(wx.NullBrush)
        dc.DrawRectangle(0,0, size[0], size[1])
        # draw progression rect
        dc.SetPen(wx.NullPen)
        dc.SetBrush(wx.Brush(wx.Colour(213,213,213)))
        dc.DrawRectangle(0,0,fillwidth, size[1])
        dc.SetPen(wx.Pen(wx.Colour(102,102,102), 1))
        dc.DrawLine(fillwidth-1, 0, fillwidth-1, size[1])
        
        # print text
        dc.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False))
        percString = '%.1f%%' % self.percentage 
        textSize = dc.GetTextExtent(percString)
        dc.DrawText(percString, 3, (size[1]-textSize[1])/2)
        if self.eta.find('unknown') == -1 and not '?' in self.eta:
            etaSize = dc.GetTextExtent(self.eta)
            dc.DrawText(self.eta, size[0]-3-etaSize[0], (size[1]-etaSize[1])/2)
        evt.Skip()
        

