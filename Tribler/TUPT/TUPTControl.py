import wx
import time

from threading import Event

from Tribler.Core.Session import Session
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import DuplicateDownloadException

from Tribler.Main.vwxGUI.SearchGridManager import LibraryManager
from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager
from Tribler.Main.Utility.GuiDBTuples import CollectedTorrent, Torrent
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.globals import DefaultDownloadStartupConfig

from Tribler.PluginManager.PluginManager import PluginManager

from Tribler.TUPT.Matcher.IMatcherPlugin import IMatcherPlugin
from Tribler.TUPT.Matcher.MatcherControl import MatcherControl

from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Parser.ParserControl import ParserControl

from Tribler.TUPT.TorrentFinder.ITorrentFinderPlugin import ITorrentFinderPlugin
from Tribler.TUPT.TorrentFinder.TorrentFinderControl import TorrentFinderControl


class TUPTControl:
    '''Class that controls the flow for parsing, matching and finding movies'''
    
    __infoBar = None
    __torrentFinder = None
    __movieTorrentIterator = None
    __callbackTDEvent = Event()
    __callbackTorrentdef = None
    
    def __init__(self, pluginManager = PluginManager()):
        self.pluginmanager = pluginManager
        self.parserControl = ParserControl(pluginManager)
        self.matcherControl = MatcherControl(pluginManager)
        self.__movieTorrentIterator = MovieTorrentIterator()
        
        #Setup the plugins.
        self.pluginmanager.RegisterCategory("Matcher", IMatcherPlugin)
        self.pluginmanager.RegisterCategory("Parser", IParserPlugin)
        self.pluginmanager.RegisterCategory("TorrentFinder", ITorrentFinderPlugin)
        self.pluginmanager.LoadPlugins()
        
    def CoupleGUI(self, gui):
        webview = gui.frame.webbrowser
        webview.AddLoadedListener(self)
        self.webview = webview
        self.mainFrame = gui.frame
        
    def webpageLoaded(self, event, html):
        """Callback for when a webpage was loaded
            We can now start feeding our parser controller.
        """
        #Parse the Website
        if self.parserControl.HasParser(event.GetURL()):
            movies, trust = self.parserControl.ParseWebsite(event.GetURL(), html)
            #Check if there a movies on the website.
            if movies is not None:
                self.__movieTorrentIterator = MovieTorrentIterator()
                for movie in movies:     
                    #Correct movie information
                    if trust == 1:
                        #If we fully trust the parser, skip correction
                        cmovie = movie
                    else:
                        cmovie = self.matcherControl.CorrectMovie(movie)
                    #Find torrents corresponding to the movie.
                    self.__torrentFinder = TorrentFinderControl(self.pluginmanager)
                    self.__torrentFinder.FindTorrents(cmovie)
                    movieTorrent = MovieTorrent(cmovie, self.__torrentFinder)                    
                    self.__movieTorrentIterator.append(movieTorrent)
                self.__infoBar = TorrentInfoBar(self.webview, self, self.__movieTorrentIterator)
    
    def DownloadHDMovie(self, n = 0):
        """Start downloading the selected movie in HD quality"""
        #Download the torrent.
        if self.__movieTorrentIterator.HasHDTorrent(n):
           self.__DownloadURL(self.__movieTorrentIterator.GetNextHDTorrent(n).GetTorrentURL())
        #Update the infobar. This has to be done regardless of if a torrent was added or not.
        if not self.__movieTorrentIterator.HasSDTorrent(n):
            self.__infoBar.RemoveSDQuality() 

    def DownloadSDMovie(self, n = 0):
        """Start downliading the selected movie in SD quality"""
       #Check if a torrent exists.
        if self.__movieTorrentIterator.HasSDTorrent(n):
            self.__DownloadURL(self.__movieTorrentIterator.GetNextSDTorrent(n).GetTorrentURL())
        #Update the infobar. This has to be done regardless of if a torrent was added or not.
        if not self.__movieTorrentIterator.HasSDTorrent(n):
            self.__infoBar.RemoveSDQuality()
    
    def __DownloadURL(self, url):
        """Download the URL using Tribler and start playing."""
        #Start downloading the torrent.
        if url.startswith('http://'):            
            torrentDef  = TorrentDef.load_from_url(url)
        elif url.startswith('magnet:?'):
            TorrentDef.retrieve_from_magnet(url, self.__MagnetCallback)
            self.__callbackTDEvent.wait()
            torrentDef = self.__callbackTorrentdef
            self.__callbackTorrentdef = None
            self.__callbackTDEvent.clear()
            
        session = Session.get_instance()
        #Check if a torrent is already added.        
        downloadState = self.__FindDownloadStateByInfoHash(torrentDef.infohash)   
        if downloadState == None:
            #Add the torrent if is not already added
            downloadState = session.start_download(torrentDef).network_get_state(None, False, sessioncalling=True)
         
        libraryManager = LibraryManager.getInstance()
        libraryManager.PlayDownloadState(downloadState)      
        
    def __MagnetCallback(self, torrentdef):
        self.__callbackTorrentdef = torrentdef
        self.__callbackTDEvent.set()    
 
    def __FindDownloadStateByInfoHash(self, infohash):
        downloadStateList = LibraryManager.getInstance().dslist  
        for dls in downloadStateList:
            if dls.download.tdef.infohash == infohash:
                return dls
        return None 
        
class TorrentInfoBar():
    '''Class that willl create and show the found movies'''
    
    HDCHOICE = "HD    Quality"
    SDCHOICE = "SD    Quality"
    
    __webview = None
    __tuptControl = None
    __comboBox = None
    __comboboxMovieTorrent = None
    __comboboxMovieTorrentMap = None
    
    
    def __init__(self, webview, __tuptControl, movieTorrentIterator):
        #Get all the movies with torrents
        validMovieIndices = []
        for i in range(movieTorrentIterator.GetSize()):
            if movieTorrentIterator.GetMovie(i).HasTorrent():
                validMovieIndices.append(i)
        #Set movie infobar information
        if len(validMovieIndices)>0:
            self.__webview = webview
            self.__tuptControl = __tuptControl
            
            # Label1
            text = " <b>The following movie was found: </b>"
            if len(validMovieIndices) > 1:
                text = " <b>The following movies were found: </b>"
            label1 = wx.StaticText(webview.infobaroverlay)
            label1.SetLabelMarkup(text)
            
            # ComboboxMovieTorrent
            self.__comboboxMovieTorrent = self.__CreateStdComboCtrl(200, self.MovieSelectionUpdated)
            for i in validMovieIndices:
                self.__comboboxMovieTorrent.Append(movieTorrentIterator.GetMovie(i).movie.dictionary['title'])
            self.__comboboxMovieTorrent.SetValue(movieTorrentIterator.GetMovie(validMovieIndices[0]).movie.dictionary['title']) 
            
            #Register mapping of valid indices
            self.__comboboxMovieTorrentMap = validMovieIndices
            
            # Label2
            text2 = "<b>. Do you want to watch this movie in:</b>"
            label2 = wx.StaticText(webview.infobaroverlay)
            label2.SetLabelMarkup(text2)
            label2.SetSizeHints(-1,-1,220,-1)
            
            #Create the quality selection.
            self.__comboBox = self.__CreateStdComboCtrl()
            movieTorrent = movieTorrentIterator.GetMovie(validMovieIndices[0])
            if movieTorrent.HasHDTorrent():
                self.__comboBox.Append(self.HDCHOICE)
                #Set default value to HD Quality.
                self.__comboBox.SetValue(self.HDCHOICE)  
            if movieTorrent.HasSDTorrent():
                self.__comboBox.Append(self.SDCHOICE)
            #Set default value to SD quality if no HD quality    
            if not movieTorrent.HasHDTorrent():
                self.__comboBox.SetValue(self.SDCHOICE)
                       
            #Create play button.
            button = wx.Button(self.__webview.infobaroverlay)
            button.SetLabel("Play!")
            button.SetBackgroundColour(self.__webview.infobaroverlay.COLOR_BACKGROUND_SEL)
            button.SetSizeHints(-1,-1,150,-1)
            
            #Register action.
            self.__webview.Bind(wx.EVT_BUTTON, self.playButtonPressed, button)
            
            #Add all elements to the infobar.
            self.__webview.SetInfoBarContents((label1,), (self.__comboboxMovieTorrent,), (label2,), (self.__comboBox,), (button,))
            self.__webview.ShowInfoBar()
    
    def playButtonPressed(self, event):
        """Callback for when the user wants to play the movie.
        """
        #Get selected movie
        rawMovieSelection = self.__comboboxMovieTorrent.GetSelection()
        movieSelection = self.__comboboxMovieTorrentMap[rawMovieSelection]
        #Get selection and the corresponding calls.
        qualitySelection = self.__comboBox.GetValue()
        if qualitySelection == self.HDCHOICE:
            self.__tuptControl.DownloadHDMovie(movieSelection)
        else:
            self.__tuptControl.DownloadSDMovie(movieSelection)

    def RemoveHDQuality(self):
        """Remove SDQuality from the choices."""
        self.__RemoveComboBoxtem(self.HDCHOICE)          

    def RemoveSDQuality(self):
        """Remove SDQuality from the choices."""
        self.__RemoveComboBoxtem(self.SDCHOICE)
      
    def __RemoveComboBoxtem(self, item):
        #Find index of item.
        index =  self.__comboBox.FindString(item)
        #Remove item.
        self.__comboBox.Delete(index)
        #Check if a item exists
        if self.__comboBox.IsEmpty():        
            #Remove infobar
            self.__webview.HideInfoBar()
        else:        
            #Set selection to 0
            self.__comboBox.SetSelection(0)
    
    def MovieSelectionUpdated(self, event):
        #Get selected movie
        rawMovieSelection = self.__comboboxMovieTorrent.GetSelection()
        movieSelection = self.__comboboxMovieTorrentMap[rawMovieSelection]
        #Remove old available definitions
        self.__RemoveComboBoxtem(self.SDCHOICE)
        self.__RemoveComboBoxtem(self.HDCHOICE)
        #We changed our movie selection, update the available definitions
        movieTorrent = movieTorrentIterator.GetMovie(movieSelection)
        if movieTorrent.HasHDTorrent():
            self.__comboBox.Append(self.HDCHOICE)
            #Set default value to HD Quality.
            self.__comboBox.SetValue(self.HDCHOICE)  
        if movieTorrent.HasSDTorrent():
            self.__comboBox.Append(self.SDCHOICE)
        #Set default value to SD quality if no HD quality    
        if not movieTorrent.HasHDTorrent():
            self.__comboBox.SetValue(self.SDCHOICE)
        self.__webview.infobaroverlay.Refresh()
            
    def __CreateStdComboCtrl(self, width = 150, callback = None):
        """Create a dropdown control set (comboBox and popupCtrl) in our theme
        """
        comboBox = wx.ComboBox(self.__webview.infobaroverlay)
        comboBox.SetSizeHints(-1,-1,width,-1)
        comboBox.SetEditable(False)
        
        comboBox.SetBackgroundColour(self.__webview.infobaroverlay.COLOR_BACKGROUND_SEL)
        comboBox.SetForegroundColour(self.__webview.infobaroverlay.COLOR_FOREGROUND)
        
        if callback is not None:
            self.__webview.Bind(wx.EVT_CHOICE, callback, comboBox) 

        return comboBox  
    
class MovieTorrentIterator:
    """Class that can hold movies and a HD torrentlist and a SD torrentlist"""
    
    __movies = None
    
    def __init__(self):
        self.__movies = []
    
    def append(self, movieTorrent):
        self.__movies.append(movieTorrent)
        
    def GetSize(self):
        return len(self.__movies)
        
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
    
    def __init__(self, movie, torrentFinder):
        self.movie = movie
        self.torrentFinder = torrentFinder
    
    def HasHDTorrent(self):
        return len(self.torrentFinder.GetHDTorrentList()) > 0    
    
    def HasSDTorrent(self):
        return len(self.torrentFinder.GetSDTorrentList()) > 0
    
    def HasTorrent(self):
        return self.HasHDTorrent() or self.HasSDTorrent()
    
    def GetNextHDTorrent(self):  
        return self.torrentFinder.GetHDTorrentList().pop(0)
    
    def GetNextSDTorrent(self):  
        return self.torrentFinder.GetSDTorrentList().pop(0)
   