import wx


class ThreadSafeProgressDialog():

    def __init__(self, title, message, maximum, parent, style):
        wx.CallAfter(self.wx_init, title, message, maximum, parent, style)

    def wx_init(self, title, message, maximum, parent, style):
        self.dlg = wx.ProgressDialog(title=title, message=message, maximum=maximum, parent=parent, style=style)
        self.dlg.Raise()

    def Update(self, value, newmsg=''):
        wx.CallAfter(lambda: self.dlg.Update(value, newmsg))

    def UpdatePulse(self, newmsg=''):
        wx.CallAfter(lambda: self.dlg.UpdatePulse(newmsg))

    def Pulse(self, newmsg=''):
        wx.CallAfter(lambda: self.dlg.Pulse(newmsg))

    def Destroy(self):
        wx.CallAfter(lambda: wx.CallLater(10000, lambda: self.dlg.Destroy()))
