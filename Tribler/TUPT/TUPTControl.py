import wx
import time
import urlparse

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.PluginManager.PluginManager import PluginManager


from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Parser.ParserControl import ParserControl

from Tribler.TUPT.TorrentFinder.ITorrentFinderPlugin import ITorrentFinderPlugin

from ListCtrlComboPopup import ListCtrlComboPopup as ListViewComboPopup

class TUPTControl:
    '''Class that controls the flow for parsing, matching and finding movies'''
    
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
                #Find torrents corresponding to the movie.
                for movie in movies:
                    results.append((movie,['SD'],['HD']))
                    self.ShowInfoBar(results)
                    
        
                                
    
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
        
    def ShowInfoBar(self,results):
        '''Display found movies and their corresponding torrents.
        Args:
            results (movie,[torrents]) = all found movies and their corresponding movie.
        '''
        #Add movie to the infobar
        if results[0][1] or results[0][2]:
            text = " <b>The following movie was found: " + results[0][0].dictionary['title'] + ". Do you want to watch this movie in:</b>"
            label = wx.StaticText(self.webview.infobaroverlay)
            label.SetLabelMarkup(text)
            
            #Create the quality selection.
            comboCtrl, popupCtrl = self.__CreateStdComboCtrl()
            if results[0][2]:
                popupCtrl.AddItem("HD    Quality")  
            if results[0][1]:
                popupCtrl.AddItem("SD    Quality")          
                         
            #Create play button.
            button = wx.Button(self.webview.infobaroverlay)
            button.SetLabel("Play!")
            button.SetBackgroundColour(self.webview.infobaroverlay.COLOR_BACKGROUND_SEL)
            button.SetSizeHints(-1,-1,150,-1)
            #Register action
            self.webview.Bind(wx.EVT_BUTTON, self.playButtonPressed, button)
            
            #Add all elements to the infobar.
            self.webview.SetInfoBarContents((label,),(comboCtrl,), (button,))
            self.webview.ShowInfoBar()  
     
    def playButtonPressed(self, event):
        """Callback for when the user wants to play the movie.
        """
        pass
        
          
