import wx
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

class SearchSideBar(wx.Panel):
    def __init__(self, parent, size):
        wx.Panel.__init__(self, parent, size = size)
        self.torrentsearch_manager = GUIUtility.getInstance().torrentsearch_manager
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        # vliegendhart: hacking in the Bundle Button (for demonstration purposes only!!)
        self.bundlebutton = wx.Button(self, -1, '')
        self.bundlestates = ['Int', 'Lev', 'Size', None]
        self.bundlebutton.Bind(wx.EVT_BUTTON, self.OnRebundle)
        vSizer.Add(self.bundlebutton, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        
        self.SetSizer(vSizer)
        self.Reset()
    
    def Reset(self):
        self.SetBundleState(0)
    
    def OnRebundle(self, event):
        newstate = (self.bundlestate+1) % len(self.bundlestates)
        self.SetBundleState(newstate)
        
    def SetBundleState(self, newstate):
        self.bundlebutton.SetLabel('Bundle: %s' % self.bundlestates[newstate])
        self.bundlestate = newstate
        self.torrentsearch_manager.setBundleMode(self.bundlestates[self.bundlestate])        