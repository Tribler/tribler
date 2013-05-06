import wx
import wx.html2

from Tribler.Main.vwxGUI.list import XRCPanel

class WebBrowser(XRCPanel):
    '''WebView is a class that allows you to browse the worldwideweb.'''
    
    def _PostInit(self):
        sizer = wx._core.BoxSizer(wx._core.VERTICAL) 
        self.browser = wx.html2.WebView.New(self) 
        sizer.Add(self.browser, 1, wx._core.EXPAND, 10) 
        self.SetSizer(sizer) 
        #self.SetSize((700, 700)) 
 