import wx
import wx.html2

from Tribler.Main.vwxGUI.list import XRCPanel

import sys
import urllib2
import urlparse
import os
import string
import time
from Tribler.SiteRipper.WebPage import WebPage
from Tribler.SiteRipper.ResourceSniffer import ResourceSniffer
from Tribler.SiteRipper.pagenotfound import NotFoundFile

class WebBrowser(XRCPanel):
    """WebView is a class that allows you to browse the worldwideweb."""
   
    WebViewModes = {'UNKNOWN':0,          # Unknown webpage
                    'INTERNET':1,         # Webpage retrieved from the internet
                    'SWARM_CACHE':2}      # Webpage downloaded from the swarm

    WebViewModeColors = [(255,255,255),     # Unknown webpage
                    (255,255,255),          # Webpage retrieved from the internet
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
    __viewmodeswitcher = None   #Handler for webpage viewmode switch requests
    URL_REQ = None      #Set this if we get an internetmode URL request from the webpage
    __condonedredirect = False  #Have we allowed the webbrowser to switch pages
   
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
        self.__reshandler = ViewmodeResourceHandler(self.__sniffer)
        self.webview.RegisterHandler(self.__reshandler)
        
        """Register Viewmode Switcher with webview"""
        self.__viewmodeswitcher = ViewmodeSwitchHandler(self)
        self.webview.RegisterHandler(self.__viewmodeswitcher)
        
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
        
    def __LoadURLNotFound(self, url):
        """Load our pagenotfound.html and give it the HTML URL parameter of the page we tried to reach
        """
        import Tribler.SiteRipper
        fs = wx.FileSystem()
        notfoundpath = NotFoundFile.getFilenameCreate()
        notfoundurl = fs.FileNameToURL(notfoundpath) + "?" + url
        self.webview.LoadURL(notfoundurl)    
    
    def __LoadURLFromLocal(self, url):
        """Load a URL from the swarm cache.
        """
        webPage = WebPage(url)
        expectedFile = webPage.GetTarFilepath()
        if os.path.isfile(expectedFile):
            #Tar exists, unpack and show
            self.loadTorrentFile(WebPage.GetTarName(webPage.GetUrl()))
        else:
            #Redirect to URL not found page
            self.__LoadURLNotFound(self.__normalizeAddress(url))
    
    def __LoadURLFromInternet(self, url):
        """Load a URL 'normally' from the internet
        """
        self.webview.LoadURL(self.__normalizeAddress(url))
        
    def LoadURL(self, url):
        """Load a URL, automaticly delegates call to appropriate url handler
            depending on our viewmode.
        """
        self.webview.Stop()
        if self.getViewMode() == WebBrowser.WebViewModes['SWARM_CACHE']:
            self.__condonedredirect = True
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
      
    def loadTorrentFile(self, tarFileName):
        """Load a webpage from a webpage Torrent created by the seed button"""
        webPage = WebPage()
        webPage.CreateFromFile(tarFileName)
        self.__condonedredirect = True
        self.__loadHTMLSource(webPage.GetUrl(), webPage.GetContent())
        self.setViewMode(WebBrowser.WebViewModes['SWARM_CACHE'])
    
    def __loadHTMLSource(self, url, source):
        """Load a webpage from HTML Source.
        Args:
            source (string): The HTML source to be loaded.
            url    (string): The URL that accompanies the HTML source."""
        self.webview.SetPage(source, url)

    def onURLLoading(self, event):
        """Actions to be taken when an URL start to be loaded."""
        #Notify our sniffer that we are constructing a new WebPage
        url = self.webview.GetCurrentURL()
        self.__sniffer.StartLoading(url, self.webview.GetPageSource())
        #Avoid a page being able to leave swarm mode without our consent
        if self.getViewMode() == WebBrowser.WebViewModes['SWARM_CACHE'] and not self.__condonedredirect:
            event.Veto()
            self.LoadURL(event.GetURL())
            return
        #Update the adressbar
        self.adressBar.SetValue(url)
    
    def onURLLoaded(self, event):
        """Actions to be taken when an URL is loaded."""
        self.__condonedredirect = False
        #Remove temporary webpage files if we are in swarm mode
        if self.getViewMode() == WebBrowser.WebViewModes['SWARM_CACHE']:
            page = WebPage(self.webview.GetCurrentURL())
            page.RemoveTempFiles(WebPage.GetTarName(page.GetUrl()))
        #We got a 'switch to internet' request
        if self.URL_REQ:
            redirection = self.URL_REQ
            self.URL_REQ = None
            if self.__handleWebpageViewmodeSwitch(redirection):
                return
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
        #Update our resource handler
        self.__reshandler.SetViewMode(self.__viewmode)
    
    def getViewMode(self):
        """Get the view mode we are currently using.
            Can be:
                - WebViewModes['UNKNOWN']
                - WebViewModes['INTERNET']
                - WebViewModes['SWARM_CACHE']
        """
        return self.__viewmode
    
    def toggleViewMode(self, event):
        """Switch viewmode depending on our current viewmode.
            Ergo, toggle between Internet and Swarm mode
        """
        if self.getViewMode() == WebBrowser.WebViewModes['INTERNET']:
            self.setViewMode(WebBrowser.WebViewModes['SWARM_CACHE'])
        elif self.getViewMode() == WebBrowser.WebViewModes['SWARM_CACHE']:
            self.setViewMode(WebBrowser.WebViewModes['INTERNET'])
        #Fallthrough if we are in unknown mode for some reason
        
    def __handleWebpageViewmodeSwitch(self, url):
        """Callback for a webpage's request to switch to internet mode
            Prompts the user if switching to the internet is O.K.
        """
        dialog = wx.MessageDialog(self, "The current page is requesting you to leave SwarmMode and\nstart browsing the world wide web. Do you accept the redirection to:\n"+url, "Redirection to internet", wx.YES_NO|wx.CENTRE)
        answer = dialog.ShowModal()
        dialog.Destroy()
        if (answer == wx.ID_YES):
            self.setViewMode(WebBrowser.WebViewModes['INTERNET'])
            self.LoadURL(url)
            return True
        return False
        
    def seed(self, event):
        """Start seeding the images on the website"""
        self.seedButton.SetLabel("Seeding")
        #disable seed button
        self.seedButton.Disable()
        #Start seeding webpage.
        self.__sniffer.Seed()

        self.seedButton.SetLabel("Seeded")
    
    def __normalizeAddress(self, url):
        """Check wether we have a valid http scheme in our url and
            try to retrieve the universal address from the DNS.
        """
        redirurl = self.__assertHttp(url)   # Make sure we are following an http protocol
        try:
            redirurl = str(self.__cookieprocessor.open(redirurl).geturl())
        except:
            pass    #We cannot get a redirection on our URL, so it must've been correct to begin with
        return redirurl
        
    def __assertHttp(self, url):
        """Prefix the http scheme to our url if we forgot it 
        """
        parts = urlparse.urlparse(url)
        if parts.scheme == '':
            return 'http://' + url
        return url
    
    def __otherviewmode(self):
        """Get the viewmode we are NOT using.
            Ex. if we are in Internet mode return Swarm mode, and vice versa 
        """
        return WebBrowser.WebViewModes['INTERNET'] if self.__viewmode == WebBrowser.WebViewModes['SWARM_CACHE'] else WebBrowser.WebViewModes['SWARM_CACHE']
        
class ViewmodeResourceHandler(wx.html2.WebViewHandler):
    """ViewmodeResourceHandler:
        Decorator for a normal WebViewFSHandler.
        In internet mode:
            Forwards requested resources to ResourceSniffer to be downloaded.
        In swarm mode:
            Retrieves requested resources from mapped local filesystem
            resources.
    """
    
    __sniffer = None        #Resource Sniffer (for fetching local copies)
    __httphandler = None    #Handler for http requests
    __viewmode = WebBrowser.WebViewModes['INTERNET'] #Viewmode we are using

    def __init__(self, sniffer):
        wx.html2.WebViewHandler.__init__(self, "http")
        self.__httphandler = wx.html2.WebViewFSHandler("http")
        self.__sniffer = sniffer
        
    def __GetFileInternet(self, uri):
        """Retrieve a resource from the internet and let our sniffer sniff
            the uri's.
        """
        self.__sniffer.GetFile(uri)             #Deliver to sniffer
        return self.__httphandler.GetFile(uri)  #Actual internet resource
    
    def __GetFileLocal(self, uri):
        """Retrieve a resource from our local filesystem
        """
        webPage = self.__sniffer._ResourceSniffer__webPage
        filename = webPage.MapResource(uri)
        fs = wx.FileSystem()
        fileuri = fs.FileNameToURL(filename)
        return fs.OpenFile(fileuri)
    
    def GetFile(self, uri):
        """Returns the wxFile descriptor for the WebView to retrieve the resource
        """
        if self.__viewmode == WebBrowser.WebViewModes['INTERNET']:
            return self.__GetFileInternet(uri)
        elif self.__viewmode == WebBrowser.WebViewModes['SWARM_CACHE']:
            return self.__GetFileLocal(uri)
        return None
    
    def SetViewMode(self, viewmode):
        self.__viewmode = viewmode
        
    def GetViewMode(self):
        return self.__viewmode
    
class ViewmodeSwitchHandler(wx.html2.WebViewHandler):
    """ViewmodeSwitchHandler:
        Handle requests by a website for the WebBrowser to swith modes.
    """
    
    def __init__(self, parent):
        wx.html2.WebViewHandler.__init__(self, "internetmode")
        self.webbrowser = parent
        
    def GetFile(self, uri):
        """Forward request for a webpage in internetmode to our WebBrowser
        """
        #Strip down the url to remove the internetmode:// scheme
        #This leaves the url the webpage is requesting to be shown in internetmode
        stripped = uri[15:]
        url = string.replace(stripped, "&#58;", ":")
        #We cannot load a different webpage while we are loading the current one
        #Reloading the current page from cache and hooking into the URLLoaded callback
        #is the cheapest way to avoid mid-load reloading crashes
        self.webbrowser.URL_REQ = url
        self.webbrowser.webview.Reload()