import wx
import time
import urlparse

from yapsy.IPlugin import IPlugin

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.PluginManager.PluginManager import PluginManager

from ListCtrlComboPopup import ListCtrlComboPopup as ListViewComboPopup

class TUPTControl:
    
    def __init__(self):
        self.pluginmanager = PluginManager()
        self.pluginmanager.RegisterCategory("Matcher", IPlugin)
        self.pluginmanager.RegisterCategory("Parser", IPlugin)
        self.pluginmanager.RegisterCategory("TorrentFinder", IPlugin)
        self.pluginmanager.LoadPlugins()
        
    def CoupleGUI(self, gui):
        webview = gui.frame.webbrowser
        webview.AddLoadedListener(self)
        self.webview = webview
        
    def webpageLoaded(self, event):
        """Callback for when a webpage was loaded
            We can now start feeding our parser controller
        """
        netloc = urlparse.urlparse(event.GetURL()).netloc   #The url identifier, ex 'www.google.com'   
        pass
            
    def piracyButtonPressed(self, event):
        """Callback for when the user wants to commit piracy.
            We can patch our parser result through the Matcher and
            the TorrentFinder now.
        """
        pass
    
    def ShowInfoBarCommitPiracy(self):
        textlabel = wx.StaticText(self.webview.infobaroverlay)
        textlabel.SetLabelMarkup(" <b>We have found a torrent for you: </b>")
        
        button = wx.Button(self.webview.infobaroverlay)
        button.SetLabel("Commit Piracy!")
        button.SetBackgroundColour(self.webview.infobaroverlay.COLOR_BACKGROUND_SEL)
        button.SetSizeHints(-1,-1,150,-1)
        
        self.webview.Bind(wx.EVT_BUTTON, self.piracyButtonPressed, button)
        
        emptylabel = wx.StaticText(self.webview.infobaroverlay)
        
        self.webview.SetInfoBarContents((textlabel,), (button,), (emptylabel,wx.EXPAND))
        self.webview.ShowInfoBar()    