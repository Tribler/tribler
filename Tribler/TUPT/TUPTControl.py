import wx
import time
import urlparse

from Tribler.Core.Session import Session
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import DuplicateDownloadException

from Tribler.Main.vwxGUI.SearchGridManager import LibraryManager
from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager
from Tribler.Main.Utility.GuiDBTuples import CollectedTorrent, Torrent
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility


from Tribler.PluginManager.PluginManager import PluginManager

from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Parser.ParserControl import ParserControl

from Tribler.TUPT.TorrentFinder.ITorrentFinderPlugin import ITorrentFinderPlugin
from Tribler.TUPT.TorrentFinder.TorrentFinderControl import TorrentFinderControl

from ListCtrlComboPopup import ListCtrlComboPopup as ListViewComboPopup
from Tribler.Video.VideoPlayer import VideoPlayer

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
        """Start downloading the selected movie in HD quality"""
        #Download the torrent.
        if self.__movieTorrentIterator.HasHDTorrent(0):
            try:
                self.__DownloadURL(self.__movieTorrentIterator.GetNextHDTorrent(0).GetTorrentURL())
            except DuplicateDownloadException:
                #Download the next torrent.
                self.DownloadHDMovie()
        #Update the infobar. This has to be done regardless of if a torrent was added or not.
        if not self.__movieTorrentIterator.HasSDTorrent(0):
            self.__infoBar.RemoveSDQuality()
        

    def DownloadSDMovie(self):
        """Start downliading the selected movie in SD quality"""
       #Check if a torrent exists.
        if self.__movieTorrentIterator.HasSDTorrent(0):
            try:
                 #Download the torrent.
                self.__DownloadURL(self.__movieTorrentIterator.GetNextSDTorrent(0).GetTorrentURL())
            except DuplicateDownloadException:
                #Dpwnload the next torrent.
                self.DownloadSDMovie()
        #Update the infobar. This has to be done regardless of if a torrent was added or not.
        if not self.__movieTorrentIterator.HasSDTorrent(0):
            self.__infoBar.RemoveSDQuality()
    
    def __DownloadURL(self, url):
        """Download the URL using Tribler and start playing."""
        #Start downloading the torrent.
        if url.startswith('http://'):            
            torrent  = TorrentDef.load_from_url(url)
        elif url.startswith('magnet:?'):
            torrent  = TorrentDef.retrieve_from_magnet(url, self.__MagnetCallback())
        session = Session.get_instance()
        session.start_download(torrent)
        download = session.get_download(torrent.infohash)
        
        #Find the correct downloadstate.
        downloadStateList = LibraryManager.getInstance().dslist     
        for dls in downloadStateList:
            if dls.download.tdef.infohash == download.tdef.infohash:
                downloadState = dls
                break       
                  
        #Play the torrent.
        videoplayer = VideoPlayer.getInstance()
        videoplayer.recreate_videopanel()
        videoplayer.stop_playback()
        videoplayer.show_loading()
        videoplayer.play(downloadState,None) 
        
        
    def __MagnetCallback(self):
        pass    
 
class TorrentInfoBar():
    '''Class that willl create and show the found movies'''
    
    HDCHOICE = "HD    Quality"
    SDCHOICE = "SD    Quality"
    
    __webview = None
    __tuptControl = None
    __comboBox = None
    
    def playButtonPressed(self, event):
        """Callback for when the user wants to play the movie.
        """
        #Get selection and the corresponding calls.
        selection = self.__comboBox.GetValue()
        if selection == self.HDCHOICE:
            self.__tuptControl.DownloadHDMovie()
        else:
            self.__tuptControl.DownloadSDMovie()

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
    
    def __init__(self, webview, __tuptControl, movieTorrent):
       if movieTorrent.HasTorrent():
            self.__webview = webview
            self.__tuptControl = __tuptControl
            #Add movie to the infobar    
            text = " <b>The following movie was found: " + movieTorrent.movie.dictionary['title'] + ". Do you want to watch this movie in:</b>"
            label = wx.StaticText(webview.infobaroverlay)
            label.SetLabelMarkup(text)
            
            #Create the quality selection.
            self.__comboBox = self.__CreateStdComboCtrl()
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
            self.__webview.SetInfoBarContents((label,),(self.__comboBox,), (button,))
            self.__webview.ShowInfoBar()
            
    def __CreateStdComboCtrl(self, width = 150):
        """Create a dropdown control set (comboBox and popupCtrl) in our theme
        """
        comboBox = wx.ComboBox(self.__webview.infobaroverlay)
        comboBox.SetSizeHints(-1,-1,width,-1)
        
        comboBox.SetBackgroundColour(self.__webview.infobaroverlay.COLOR_BACKGROUND_SEL)
        comboBox.SetForegroundColour(self.__webview.infobaroverlay.COLOR_FOREGROUND)

        return comboBox  
    
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
   