import wx
import time
import urlparse

from Tribler.Core.Session import Session
from Tribler.Core.TorrentDef import TorrentDef

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
    __movieTorrentIterator = None
    
    def __init__(self, pluginManager = PluginManager()):
        self.pluginmanager = pluginManager
        self.parserControl = ParserControl(pluginManager)
        self.__movieTorrentIterator = MovieTorrentIterator()
        
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
        if self.parserControl.HasParser(netloc):
            movies = self.parserControl.ParseWebsite(netloc, html)
            #Check if there a movies on the website.
            if movies is not None:
                for movie in movies:                    
                    #Find torrents corresponding to the movie.
                    torrentFinder = TorrentFinderControl(self.pluginmanager)
                    torrentFinder.FindTorrents(movie)
                    movieTorrent = MovieTorrent(movie, torrentFinder.GetHDTorrentList(), torrentFinder.GetSDTorrentList())                    
                    self.__movieTorrentIterator.append(movieTorrent)
                    self.__infoBar = TorrentInfoBar(self.webview, self, movieTorrent)
    
    def DownloadHDMovie(self):
        '''Play'''
        #Download
        self.__DownloadURL(self.__movieTorrentIterator.GetNextHDTorrent(0).GetTorrentURL())

    def DownloadSDMovie(self):
        self.__DownloadURL(self.__movieTorrentIterator.GetNextHDTorrent(0).GetTorrentURL())
    
    
    def __DownloadURL(self, url):
        """Download the URL using Tribler."""
        if url.startswith('http://'):            
            torrent  = TorrentDef.load_from_url(url)
        elif url.startswith('magnet:?'):
            torrent  = TorrentDef.retrieve_from_magnet(url, self.__MagnetCallback())
        session = Session.get_instance()
        session.start_download(torrent)
        
    def __MagnetCallback(self):
        pass
    
class MovieTorrentIterator:
    """Class that can hold movies and a HD torrentlist and a SD torrentlist"""
    
    __movies = None
    
    def __init__(self):
        self.__movies = []
    
    def append(self, movieTorrent):
        self.__movies.append(movieTorrent)
        
    def HasHDTorrent(self, n):
        return self.__movies[n].HasHDTorrent()
    
    def HasSDTorrent(self, n):
        return self.__movies[n].HasSDTorrent()
    
    def HasTorrent(self, n):
        return self.__movies[n].HasTorrent()
    
    def GetMovie(self,n):
        return self.__movies[n]
    
    def GetNextHDTorrent(self, n):
        return self.__movies[n].GetNextHDTorrent()
    
    def GetNextSDTorrent(self, n):
        return self.__movies[n].GetNextSDTorrent()
        
class MovieTorrent:
    """ Class that contains a movie and the corresponding HD and SD torrentlists."""
    
    def __init__(self, movie, hdList, sdList):
        self.movie = movie
        self.hdList = hdList
        self.sdList = sdList
    
    def HasHDTorrent(self):
        return len(self.hdList) > 0    
    
    def HasSDTorrent(self):
        return len(self.sdList) > 0
    
    def HasTorrent(self):
        return self.HasHDTorrent() or self.HasSDTorrent()
    
    def GetNextHDTorrent(self):  
        return self.hdList.pop(0)
    
    def GetNextSDTorrent(self):  
        return self.sdList.pop(0)
    
class TorrentInfoBar():
    '''Class that willl create and show the found movies'''
    
    HDCHOICE = "HD    Quality"
    SDCHOICE = "SD    Quality"
    
    __webview = None
    __comboCtrl = None
    
    def playButtonPressed(self, event):
        """Callback for when the user wants to play the movie.
        """
        #Get selection and the corresponding calls.
        selection = self.__comboCtrl.GetValue()
        if selection == self.HDCHOICE:
            self.__tuptControl.DownloadHDMovie()
        else:
            self.__tuptControl.DownloadSDMovie()
    
    def __init__(self, webview, __tuptControl, movieTorrent):
       if movieTorrent.HasTorrent():
            self.__webview = webview
            self.__tuptControl = __tuptControl
            #Add movie to the infobar    
            text = " <b>The following movie was found: " + movieTorrent.movie.dictionary['title'] + ". Do you want to watch this movie in:</b>"
            label = wx.StaticText(webview.infobaroverlay)
            label.SetLabelMarkup(text)
            
            #Create the quality selection.
            comboCtrl, popupCtrl = self.__CreateStdComboCtrl()
            if movieTorrent.HasHDTorrent():
                popupCtrl.AddItem(self.HDCHOICE)
                #Set default value to HD Quality.
                comboCtrl.SetValue(self.HDCHOICE)  
            if movieTorrent.HasSDTorrent():
                popupCtrl.AddItem(self.SDCHOICE)
            #Set default value to SD quality if no HD quality    
            if not movieTorrent.HasHDTorrent():
                comboCtrl.SetValue(self.SDCHOICE)
            
            self.__comboCtrl = comboCtrl             
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