import wx
import time
import urlparse

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.PluginManager.PluginManager import PluginManager


from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Parser.ParserControl import ParserControl

from Tribler.TUPT.TorrentFinder.ITorrentFinderPlugin import ITorrentFinderPlugin
from Tribler.TUPT.TorrentFinder.TorrentFinderControl import TorrentFinderControl

from ListCtrlComboPopup import ListCtrlComboPopup as ListViewComboPopup

class TUPTControl:
    '''Class that controls the flow for parsing, matching and finding movies'''
    
    __infoBar = None
    
    def __init__(self, pluginManager = PluginManager()):
        self.pluginmanager = pluginManager
        self.parserControl = ParserControl(pluginManager)
        
        #Setup the plugins.
        self.pluginmanager.RegisterCategory("Matcher", object)
        self.pluginmanager.RegisterCategory("Parser", IParserPlugin)
        self.pluginmanager.RegisterCategory("TorrentFinder", ITorrentFinderPlugin)
        self.pluginmanager.LoadPlugins()
        
    def CoupleGUI(self, gui):
        webview = gui.frame.webbrowser
        webview.AddLoadedListener(self)
        self.webview = webview
        
    def webpageLoaded(self, event, html):
        """Callback for when a webpage was loaded
            We can now start feeding our parser controller
        """
        netloc = urlparse.urlparse(event.GetURL()).netloc   #The url identifier, ex 'www.google.com'   
        #Parse the Website.
        results =[]
        if self.parserControl.HasParser(netloc):
            movies = self.parserControl.ParseWebsite(netloc, html)
            if movies is not None:
                for movie in movies:                    
                    #Find torrents corresponding to the movie.
                    torrentFinder = TorrentFinderControl(self.pluginmanager)
                    torrentFinder.FindTorrents(movie)                    
                    results.append((movie,torrentFinder))
                    self.__movies = results   
                    self.__infoBar = TorrentInfoBar(self.webview, results)
    
class TorrentInfoBar():
    '''Class that willl create and show the found movies'''
    
    __webview = None
    
    def playButtonPressed(self, event):
        """Callback for when the user wants to play the movie.
        """
        pass
    
    def __init__(self, webview, movies):
       if movies[0][1].HasTorrent():
            self.__webview = webview
            #Add movie to the infobar    
            text = " <b>The following movie was found: " + movies[0][0].dictionary['title'] + ". Do you want to watch this movie in:</b>"
            label = wx.StaticText(webview.infobaroverlay)
            label.SetLabelMarkup(text)
            
            #Create the quality selection.
            comboCtrl, popupCtrl = self.__CreateStdComboCtrl()
            if movies[0][1].HasHDTorrent():
                popupCtrl.AddItem("HD    Quality")
                #Set default value to HD Quality.
                comboCtrl.SetValue("HD    Quality")  
            if movies[0][1].HasSDTorrent():
                popupCtrl.AddItem("SD    Quality")
            #Set default value to SD quality if no HD quality    
            if not movies[0][1].HasHDTorrent():
                comboCtrl.SetValue("SD    Quality")
                         
            #Create play button.
            button = wx.Button(self.__webview.infobaroverlay)
            button.SetLabel("Play!")
            button.SetBackgroundColour(self.__webview.infobaroverlay.COLOR_BACKGROUND_SEL)
            button.SetSizeHints(-1,-1,150,-1)
            #Register action.
            self.__webview.Bind(wx.EVT_BUTTON, self.playButtonPressed, button)
            
            #Add all elements to the infobar.
            self.__webview.SetInfoBarContents((label,),(comboCtrl,), (button,))
            self.__webview.ShowInfoBar()
            
    def __CreateStdComboCtrl(self, width = 150):
        """Create a dropdown control set (comboCtrl and popupCtrl) in our theme
        """
        comboCtrl = wx.ComboCtrl(self.__webview.infobaroverlay)
        comboCtrl.SetSizeHints(-1,-1,width,-1)
        
        comboCtrl.SetBackgroundColour(self.__webview.infobaroverlay.COLOR_BACKGROUND_SEL)
        comboCtrl.SetForegroundColour(self.__webview.infobaroverlay.COLOR_FOREGROUND)

        popupCtrl = ListViewComboPopup()
        
        popupCtrl.SetBackgroundColour(self.__webview.infobaroverlay.COLOR_BACKGROUND)
        popupCtrl.SetForegroundColour(self.__webview.infobaroverlay.COLOR_FOREGROUND)
        
        comboCtrl.SetPopupControl(popupCtrl)

        return comboCtrl, popupCtrl  