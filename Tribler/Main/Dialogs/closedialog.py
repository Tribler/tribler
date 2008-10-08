# Written by ABC authors
# see LICENSE.txt for license information
import sys
import wx

# Display a progress dialog that updates as threads shut down
class CloseDialog(wx.Dialog):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility

        title = self.utility.lang.get('close_title')
        
        pre = wx.PreDialog()
        pre.Create(parent, -1, title)
        self.this = pre.this
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.startval = len(self.utility.queue.proctab)
        
        self.gauge = wx.Gauge(self, -1, self.startval, size = (200, 30), style = wx.GA_SMOOTH)
        sizer.Add(self.gauge, 0, wx.ALIGN_CENTER|wx.ALL, 5)
        
        self.update()
        
        self.SetAutoLayout( True )
        self.SetSizer( sizer )
        self.Fit()
        
    def update(self):        
        left = len(self.utility.queue.activetorrents)
        
        self.gauge.SetValue(self.startval - left)