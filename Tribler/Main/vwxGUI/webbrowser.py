import wx
import wx.html2

from Tribler.Main.vwxGUI.list import XRCPanel

from Tribler.SiteRipper.SiteRipper import seedWebPage

import sys
from Tribler.SiteRipper.WebPage import WebPage
from Tribler.SiteRipper.ResourceSniffer import ResourceSniffer

class SeedingResourceHandler(wx.html2.WebViewHandler):
    '''SeedingResourceHandler:
        Decorator for a normal WebViewFSHandler.
        Forwards requested resources to ResourceSniffer to be downloaded.
    '''
    
    __sniffer = None        #Resource Sniffer (for fetching local copies)
    __httphandler = None    #Handler for http requests

    def __init__(self, sniffer):
        wx.html2.WebViewHandler.__init__(self, "http")
        self.__httphandler = wx.html2.WebViewFSHandler("http")
        self.__sniffer = sniffer
        
    def GetFile(self, uri):
        '''Returns the wxFile descriptor for the WebView to retrieve the resource
        '''
        self.__sniffer.GetFile(uri)
        return self.__httphandler.GetFile(uri)


class WebBrowser(XRCPanel):
    '''WebView is a class that allows you to browse the worldwideweb.'''
   
    __sniffer = None    #Resource Sniffer (for fetching local copies)
    __reshandler = None #Resource Handler 
   
    def __init__(self, parent=None):
        XRCPanel.__init__(self, parent)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
             
        '''Create the toolbar'''
        toolBar = wx.BoxSizer(wx.HORIZONTAL)
        #Create the toolbar buttons.
        backwardButton = wx.Button(self, label="Backward")
        forwardButton = wx.Button(self, label="Forward")    
        goButton = wx.Button(self, label="Go")
        self.seedButton = wx.Button(self, label="Seed")
        #Register the actions
        self.Bind(wx.EVT_BUTTON, self.goBackward, backwardButton)
        self.Bind(wx.EVT_BUTTON, self.goForward, forwardButton)
        self.Bind(wx.EVT_BUTTON, self.loadURLFromAdressBar, goButton)
        self.Bind(wx.EVT_BUTTON, self.seed, self.seedButton)
        #Create the adressbar.
        self.adressBar = wx.TextCtrl(self,1, style = wx.TE_PROCESS_ENTER)
        #Register the enterkey.
        self.Bind(wx.EVT_TEXT_ENTER, self.loadURLFromAdressBar, self.adressBar)
        #Add all the components to the toolbar.
        toolBar.Add(backwardButton, 0)
        toolBar.Add(forwardButton, 0)
        toolBar.Add(self.adressBar, 1, wx.EXPAND)
        toolBar.Add(goButton, 0)
        toolBar.Add(self.seedButton,0)
        #Add the toolbar to the panel.
        vSizer.Add(toolBar, 0, wx.EXPAND)
        
        '''Create the webview'''
        self.webview = wx.html2.WebView.New(self)
        
        '''Register Resource Sniffer with webview'''
        self.__sniffer = ResourceSniffer()
        self.__reshandler = SeedingResourceHandler(self.__sniffer)
        self.webview.RegisterHandler(self.__reshandler)
        
        #Clear the blank page loaded on startup.        
        self.webview.ClearHistory()
        self.webview.LoadURL("http://www.google.com/") 
              
        vSizer.Add(self.webview, 1, wx.EXPAND) 
        
        '''Add all components'''
        self.SetSizer(vSizer)
        self.Layout()
        
        '''Register the action on the event that a URL is being loaded and when finished loading'''
        
        self.Bind(wx.html2.EVT_WEBVIEW_LOADED, self.onURLLoaded, self.webview)
        self.Bind(wx.html2.EVT_WEBVIEW_NAVIGATED, self.onURLLoading, self.webview)
        
    def __del__(self):
        WebBrowser.instances.remove(self)
        
    def goBackward(self, event):
        if self.webview.CanGoBack():
            self.webview.GoBack()
        
    def goForward(self, event):
        if self.webview.CanGoForward():
            self.webview.GoForward()
    
    def loadURLFromAdressBar(self, event):
        '''Load an URL from the adressbar'''
        url = self.adressBar.GetValue()
        self.adressBar.SetValue(url)
        self.webview.LoadURL(url)
      
    def loadTorrentFile(self, filename):
        '''Load a webpage from a webpage Torrent created by the seed button'''
        webPage = WebPage()
        webPage.createFromFile(filename)
        self.__loadHTMLSource(webPage.getContent(), webPage.getUrl())
    
    def __loadHTMLSource(self, source, url):
        '''Load a webpage from HTML Source.
        Args:
            source (string): The HTML source to be loaded.
            url    (string): The URL that accompanies the HTML source.'''
        self.webview.SetPage(source, url)

    def onURLLoading(self, event):
        '''Actions to be taken when an URL start to be loaded.'''
        #Update the adressbar
        self.adressBar.SetValue(self.webview.GetCurrentURL())
    
    def onURLLoaded(self, event):
        '''Actions to be taken when an URL is loaded.''' 
        #Notify our sniffer that the current page can be saved
        self.__sniffer.FinishedLoading()       
        #Show the actual page address in the address bar
        self.adressBar.SetValue(self.webview.GetCurrentURL())
        #Update the seedbutton
        self.seedButton.SetLabel("Seed")
        self.seedButton.Enable()
        
    def seed(self, event):
        '''Start seeding the images on the website'''
        self.seedButton.SetLabel("Seeding")
        #disable seed button
        self.seedButton.Disable()
        #Start seeding webpage.
        self.__sniffer.Seed()

        self.seedButton.SetLabel("Seeded")
        
        
