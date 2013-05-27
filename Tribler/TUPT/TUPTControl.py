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
            We can now start feeding our controllers
        """
        netloc = urlparse.urlparse(event.GetURL()).netloc   #The url identifier, ex 'www.google.com'   
        # DEBUG
        self.webview.HideInfoBar()
        if (netloc == "www.wxpython.org"):
            time.sleep(1)
            self.ShowInfoBarQuality()
    
    def __CreateStdComboCtrl(self, width = 150):
        """Create a dropdown control set (comboCtrl and popupCtrl) in our theme
        """
        comboCtrl = wx.ComboCtrl(self.webview.infobaroverlay)
        comboCtrl.SetSizeHints(-1,-1,width,-1)
        
        comboCtrl.SetBackgroundColour(self.webview.infobaroverlay.COLOR_BACKGROUND_SEL)
        comboCtrl.SetForegroundColour(self.webview.infobaroverlay.COLOR_FOREGROUND)

        popupCtrl = ListViewComboPopup()
        
        popupCtrl.SetBackgroundColour(self.webview.infobaroverlay.COLOR_BACKGROUND)
        popupCtrl.SetForegroundColour(self.webview.infobaroverlay.COLOR_FOREGROUND)
        
        comboCtrl.SetPopupControl(popupCtrl)

        return comboCtrl, popupCtrl
        
    
    def ShowInfoBarQuality(self):
        textlabel = wx.StaticText(self.webview.infobaroverlay)
        textlabel.SetLabelMarkup(" <b>We have found the following video qualties for you: </b>")
        
        comboCtrl, popupCtrl = self.__CreateStdComboCtrl()
        
        popupCtrl.AddItem("Bad    Quality")
        popupCtrl.AddItem("Normal Quality")
        popupCtrl.AddItem("High   Quality")
        
        self.webview.SetInfoBarContents((textlabel,wx.CENTER), (comboCtrl, wx.CENTER))
        self.webview.ShowInfoBar()