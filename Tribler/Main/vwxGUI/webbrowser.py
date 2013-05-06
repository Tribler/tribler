import wx
import wx.html2

from Tribler.Main.vwxGUI.list import XRCPanel

class WebBrowser(XRCPanel):
    '''WebView is a class that allows you to browse the worldwideweb.'''
    
   
    def __init__(self, parent=None):
        XRCPanel.__init__(self, parent)
        
        self.webview = wx.html2.WebView.New(self)
        
        self.webview.LoadURL("http://www.google.com") 
        
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(self.webview, 1, wx.EXPAND)
        self.SetSizer(sizer)
 