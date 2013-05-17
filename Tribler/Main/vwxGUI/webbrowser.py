import wx
import wx.html2

from Tribler.Main.vwxGUI.list import XRCPanel

import sys
import urllib2
import urlparse
import os
from Tribler.SiteRipper.WebPage import WebPage
from Tribler.SiteRipper.ResourceSniffer import ResourceSniffer

class SeedingResourceHandler(wx.html2.WebViewHandler):
    """SeedingResourceHandler:
        Decorator for a normal WebViewFSHandler.
        Forwards requested resources to ResourceSniffer to be downloaded.
    """
    
    __sniffer = None        #Resource Sniffer (for fetching local copies)
    __httphandler = None    #Handler for http requests

    def __init__(self, sniffer):
        wx.html2.WebViewHandler.__init__(self, "http")
        self.__httphandler = wx.html2.WebViewFSHandler("http")
        self.__sniffer = sniffer
        
    def GetFile(self, uri):
        """Returns the wxFile descriptor for the WebView to retrieve the resource
        """
        self.__sniffer.GetFile(uri)
        return self.__httphandler.GetFile(uri)


class WebBrowser(XRCPanel):
    """WebView is a class that allows you to browse the worldwideweb."""
   
    WebViewModes = {'UNKNOWN':0,          # Unknown webpage
                    'INTERNET':1,         # Webpage retrieved from the internet
                    'SWARM_CACHE':2}      # Webpage downloaded from the swarm

    WebViewModeColors = [(255,255,255),     # Unknown webpage
                    (220,255,220),          # Webpage retrieved from the internet
                    (255,255,220)]          # Webpage downloaded from the swarm
    
    WebViewModeTooltips = ["%s Not on the internet or in the swarm",       # Unknown webpage
                    "Visiting %s via the internet",                        # Webpage retrieved from the internet
                    "Eternal webpage %s downloaded from the swarm"]        # Webpage downloaded from the swarm
    
    WebViewModeLabels = ["SwitchMode",       # Unknown webpage
                    "SwarmMode",           # Webpage retrieved from the internet
                    "InternetMode"]          # Webpage downloaded from the swarm
   
    __sniffer = None    #Resource Sniffer (for fetching local copies)
    __reshandler = None #Resource Handler 
    __viewmode = 0      #What type of webpage are we visiting
    __cookieprocessor = urllib2.build_opener(urllib2.HTTPCookieProcessor()) # Redirection handler
   
    def __init__(self, parent=None):
        XRCPanel.__init__(self, parent)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
             
        """Create the toolbar"""
        self.toolBar = wx.BoxSizer(wx.HORIZONTAL)
        #Create the toolbar buttons.
        backwardButton = wx.Button(self, label="Backward")
        forwardButton = wx.Button(self, label="Forward")    
        goButton = wx.Button(self, label="Go")
        self.seedButton = wx.Button(self, label="Seed")
        self.viewmodeButton = wx.Button(self, label="OfflineMode")
        #Register the actions
        self.Bind(wx.EVT_BUTTON, self.goBackward, backwardButton)
        self.Bind(wx.EVT_BUTTON, self.goForward, forwardButton)
        self.Bind(wx.EVT_BUTTON, self.loadURLFromAdressBar, goButton)
        self.Bind(wx.EVT_BUTTON, self.seed, self.seedButton)
        self.Bind(wx.EVT_BUTTON, self.toggleViewMode, self.viewmodeButton)
        #Create the adressbar.
        self.adressBar = wx.TextCtrl(self,1, style = wx.TE_PROCESS_ENTER)
        #Register the enterkey.
        self.Bind(wx.EVT_TEXT_ENTER, self.loadURLFromAdressBar, self.adressBar)
        #Add all the components to the toolbar.
        self.toolBar.Add(backwardButton, 0)
        self.toolBar.Add(forwardButton, 0)
        self.toolBar.Add(self.adressBar, 1, wx.EXPAND)
        self.toolBar.Add(goButton, 0)
        self.toolBar.Add(self.viewmodeButton, 0)
        self.toolBar.Add(self.seedButton,0)
        #Add the toolbar to the panel.
        vSizer.Add(self.toolBar, 0, wx.EXPAND)
        
        """Create the webview"""
        self.webview = wx.html2.WebView.New(self)
        
        """Register Resource Sniffer with webview"""
        self.__sniffer = ResourceSniffer()
        self.__reshandler = SeedingResourceHandler(self.__sniffer)
        self.webview.RegisterHandler(self.__reshandler)
        
        #Clear the blank page loaded on startup.        
        self.webview.ClearHistory()
        self.LoadURL("about:blank")
        self.setViewMode('INTERNET')
              
        vSizer.Add(self.webview, 1, wx.EXPAND) 
        
        """Add all components"""
        self.SetSizer(vSizer)
        self.Layout()
        
        """Register the action on the event that a URL is being loaded and when finished loading"""
        self.Bind(wx.html2.EVT_WEBVIEW_LOADED, self.onURLLoaded, self.webview)
        self.Bind(wx.html2.EVT_WEBVIEW_NAVIGATED, self.onURLLoading, self.webview)
        
    def __LoadURLFromLocal(self, url):
        import Tribler.SiteRipper
        self.webview.LoadURL(os.path.dirname("file:" + os.sep + os.sep + Tribler.SiteRipper.__file__) + os.sep + "pagenotfound.html?" + url)
        wx.CallAfter(self.adressBar.SetValue, url)
    
    def __LoadURLFromInternet(self, url):
        redirurl = self.__assertHttp(url)   # Make sure we are following an http protocol
        try:
            redirurl = str(self.__cookieprocessor.open(redirurl).geturl())
        except:
            pass    #We cannot get a redirection on our URL, so it must've been correct to begin with
        self.webview.LoadURL(redirurl)
        
    def LoadURL(self, url):
        if self.getViewMode() == WebBrowser.WebViewModes['SWARM_CACHE']:
            self.__LoadURLFromLocal(url)
        else:
            self.__LoadURLFromInternet(url)
        
    def goBackward(self, event):
        if self.webview.CanGoBack():
            self.webview.GoBack()
        
    def goForward(self, event):
        if self.webview.CanGoForward():
            self.webview.GoForward()
    
    def loadURLFromAdressBar(self, event):
        """Load an URL from the adressbar"""
        url = self.adressBar.GetValue()
        self.adressBar.SetValue(url)
        self.LoadURL(url)
      
    def loadTorrentFile(self, filename):
        """Load a webpage from a webpage Torrent created by the seed button"""
        webPage = WebPage()
        webPage.CreateFromFile(filename)
        self.__loadHTMLSource(webPage.GetUrl(), webPage.GetContent())
    
    def __loadHTMLSource(self, url, source):
        """Load a webpage from HTML Source.
        Args:
            source (string): The HTML source to be loaded.
            url    (string): The URL that accompanies the HTML source."""
        self.webview.SetPage(source, url)

    def onURLLoading(self, event):
        """Actions to be taken when an URL start to be loaded."""
        url = self.webview.GetCurrentURL()
        #Notify our sniffer that we are constructing a new WebPage
        self.__sniffer.StartLoading(url, self.webview.GetPageSource())
        #Update the adressbar
        self.adressBar.SetValue(url)
    
    def onURLLoaded(self, event):
        """Actions to be taken when an URL is loaded."""        
        #Show the actual page address in the address bar
        self.adressBar.SetValue(self.webview.GetCurrentURL())
        #Update the seedbutton
        self.seedButton.SetLabel("Seed")
        self.seedButton.Enable()
        
    def setViewMode(self, mode):
        """Set the view mode we are currently using.
            Mode can be either an integer or a string:
                - WebViewModes['UNKNOWN'] or 'UNKNOWN'
                - WebViewModes['INTERNET'] or 'INTERNET'
                - WebViewModes['SWARM_CACHE'] or 'SWARM_CACHE'
        """
        if isinstance(mode, basestring):
            self.__viewmode = WebBrowser.WebViewModes.__getitem__(mode)
        else:
            self.__viewmode = mode
        #Addressbar modifications
        self.adressBar.SetBackgroundColour(WebBrowser.WebViewModeColors[self.__viewmode])
        tooltip = WebBrowser.WebViewModeTooltips[self.__viewmode] % (self.adressBar.GetValue())
        self.adressBar.SetToolTip(tooltip)
        #Viewmodeswitch modifications
        self.viewmodeButton.SetLabel(WebBrowser.WebViewModeLabels[self.__viewmode])
        self.viewmodeButton.SetBackgroundColour(WebBrowser.WebViewModeColors[self.__otherviewmode()])
        #Refresh toolbar
        self.toolBar.Layout()
    
    def getViewMode(self):
        """Get the view mode we are currently using.
            Can be:
                - WebViewModes['UNKNOWN']
                - WebViewModes['INTERNET']
                - WebViewModes['SWARM_CACHE']
        """
        return self.__viewmode
    
    def toggleViewMode(self, event):
        if self.getViewMode() == WebBrowser.WebViewModes['INTERNET']:
            self.setViewMode(WebBrowser.WebViewModes['SWARM_CACHE'])
        elif self.getViewMode() == WebBrowser.WebViewModes['SWARM_CACHE']:
            self.setViewMode(WebBrowser.WebViewModes['INTERNET'])
        #Fallthrough if we are in unknown mode for some reason
        
    def seed(self, event):
        """Start seeding the images on the website"""
        self.seedButton.SetLabel("Seeding")
        #disable seed button
        self.seedButton.Disable()
        #Start seeding webpage.
        self.__sniffer.Seed()

        self.seedButton.SetLabel("Seeded")
        
    def __assertHttp(self, url):
        parts = urlparse.urlparse(url)
        if parts.scheme == '':
            return 'http://' + url
        return url
    
    def __otherviewmode(self):
        return 1 if self.__viewmode == 2 else 2
        
