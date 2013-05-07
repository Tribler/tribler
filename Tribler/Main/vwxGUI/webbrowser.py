import wx
import wx.html2

from Tribler.Main.vwxGUI.list import XRCPanel

class WebBrowser(XRCPanel):
    '''WebView is a class that allows you to browse the worldwideweb.'''
    
   
    def __init__(self, parent=None):
        XRCPanel.__init__(self, parent)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        '''Create the webview'''
        self.webview = wx.html2.WebView.New(self)        
        self.webview.LoadURL("http://www.google.com") 
        
        '''Add every component to the XRCPanel'''
        vSizer.Add(self.webview, 1, wx.EXPAND) 
        self.SetSizer(vSizer)
        self.Layout()