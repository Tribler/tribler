import wx
import wx.html2

from Tribler.Main.vwxGUI.list import XRCPanel

from Tribler.SiteRipper.SiteRipper import seedImages

import sys

class WebBrowser(XRCPanel):
    '''WebView is a class that allows you to browse the worldwideweb.'''
   
    __onLoadListeners = []  # Listener functions for webpage URL changes
    instances = []          # All webbrowser instances exposed
   
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
        #Clear the blank page loaded on startup.        
        self.webview.ClearHistory()
        self.webview.LoadURL("http://www.google.com/") 
        
        vSizer.Add(self.webview, 1, wx.EXPAND) 
        
        '''Add all components'''
        self.SetSizer(vSizer)
        self.Layout()
        
        '''Register the action on the event that a URL is being loaded and when finished loading'''
        self.Bind(wx.html2.EVT_WEB_VIEW_LOADED, self.onURLLoaded, self.webview)
        self.Bind(wx.html2.EVT_WEB_VIEW_NAVIGATED, self.onURLLoading, self.webview)
        
        WebBrowser.instances.append(self)
        
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
        
    def getCurrentURL(self):
        '''Return the current URL from the addressbar'''
        return self.adressBar.GetValue()
    
    def onURLLoading(self, event):
        '''Actions to be taken when an URL start to be loaded.'''
        #Update the adressbar
        self.adressBar.SetValue(self.webview.GetCurrentURL())
    
    def addOnLoadListener(self, listener):
        '''Add handler function to be called when a webpage is loaded'''
        self.__onLoadListeners.append(listener)
        
    def removeOnLoadListener(self, listener):
        '''Remove handler function which would be called when a webpage is loaded'''
        self.__onLoadListeners.remove(listener)
        
    def __notifyOnLoadListeners(self):
        '''Calls all registered OnLoad functions'''
        for listener in self.__onLoadListeners:
            value = listener(self)
            if value:
                self.removeOnLoadListener(listener)
    
    def onURLLoaded(self, event):
        '''Actions to be taken when an URL is loaded.'''        
        #Update the seedbutton
        self.seedButton.SetLabel("Seed")
        self.seedButton.Enable()
        self.__notifyOnLoadListeners()
        
    def seed(self, event):
        '''Start seeding the images on the website'''
        self.seedButton.SetLabel("Seeding")
        #disable seed button
        self.seedButton.Disable()
        #Start seeding images.
        seedImages(self.webview.GetCurrentURL())
        self.seedButton.SetLabel("Seeded")
        
        
