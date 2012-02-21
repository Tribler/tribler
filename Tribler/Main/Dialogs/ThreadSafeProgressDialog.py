import wx

class ThreadSafeProgressDialog():
    
    def __init__(self, title, message, maximum, parent, style):
        wx.CallAfter(self.wx_init, title, message, maximum, parent, style)
        
    def wx_init(self, title, message, maximum, parent, style):
        self.dlg = wx.ProgressDialog(title = title, message = message, maximum = maximum, parent=parent, style=style)
    
    def Update(self, value, newmsg = ''):
        wx.CallAfter(self.dlg.Update, value, newmsg)
    
    def UpdatePulse(self, newmsg = ''):
        wx.CallAfter(self.dlg.UpdatePulse, newmsg)
    
    def Pulse(self, newmsg = ''):
        wx.CallAfter(self.dlg.Pulse, newmsg)
    
    def Destroy(self):
        wx.CallAfter(self.dlg.Destroy)