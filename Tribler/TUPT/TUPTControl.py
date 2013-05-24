import wx
import time

from yapsy.IPlugin import IPlugin

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.PluginManager.PluginManager import PluginManager

class TUPTControl:
    
    def __init__(self):
        self.pluginmanager = PluginManager()
        self.pluginmanager.RegisterCategory("Matcher", IPlugin)
        self.pluginmanager.RegisterCategory("Parser", IPlugin)
        self.pluginmanager.RegisterCategory("TorrentFinder", IPlugin)
        self.pluginmanager.LoadPlugins()
        self.pluginmanager.RegisterAsSingleton()
        
    def CoupleGUI(self, gui):
        webview = gui.frame.webbrowser
        webview.AddLoadedListener(self)
        self.webview = webview
        
    def webpageLoaded(self, event):
        """Callback for when a webpage was loaded
            We can now start feeding our controllers
        """
        # DEBUG
        self.webview.HideInfoBar()
        if (event.GetURL() == "http://www.wxpython.org/"):
            time.sleep(1)
            self.ShowInfoBarQuality()
    
    def ShowInfoBarQuality(self):
        textlabel = wx.StaticText(self.webview.infobaroverlay)
        textlabel.SetLabelMarkup(" <b>We have found the following video qualties for you: </b>")
        self.webview.SetInfoBarContents((textlabel,wx.CENTER))
        self.webview.ShowInfoBar()