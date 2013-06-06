import wx
import wx.html2
import urlparse
import urllib2
import time
import thread
import sys
import traceback

from Tribler.Main.vwxGUI.list import XRCPanel

class WebBrowser(XRCPanel):
    '''WebView is a class that allows you to browse the worldwideweb.'''    
   
    def __init__(self, parent=None):
        XRCPanel.__init__(self, parent)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
             
        '''Create the toolbar'''
        toolBarPanel = wx.Panel(self)
        toolBarPanel.SetBackgroundColour(wx.Colour(255,255,255))
        toolBar = wx.BoxSizer(wx.HORIZONTAL)
        toolBarPanel.SetSizer(toolBar)
        #Create the toolbar buttons.
        backwardButton = wx.Button(toolBarPanel, label="Backward")
        forwardButton = wx.Button(toolBarPanel, label="Forward")    
        goButton = wx.Button(toolBarPanel, label="Go")
        #Register the actions
        self.Bind(wx.EVT_BUTTON, self.goBackward, backwardButton)
        self.Bind(wx.EVT_BUTTON, self.goForward, forwardButton)
        self.Bind(wx.EVT_BUTTON, self.loadURLFromAdressBar, goButton)
        #Create the adressbar.
        self.adressBar = wx.TextCtrl(toolBarPanel,1, style = wx.TE_PROCESS_ENTER)
        #Register the enterkey.
        self.Bind(wx.EVT_TEXT_ENTER, self.loadURLFromAdressBar, self.adressBar)
        #Add all the components to the toolbar.
        toolBar.Add(backwardButton, 0)
        toolBar.Add(forwardButton, 0)
        toolBar.Add(self.adressBar, 1, wx.EXPAND)
        toolBar.Add(goButton, 0)
        toolBarPanel.Layout()
        #Add the toolbar to the panel.
        vSizer.Add(toolBarPanel, 0, wx.EXPAND)
        
        '''Add the overlay for the info bar'''
        self.infobaroverlay = wx.Panel(self)
        self.infobaroverlay.SetBackgroundColour(wx.Colour(255,255,153))
        self.infobaroverlay.vSizer = vSizer
        vSizer.Add(self.infobaroverlay, 1, wx.EXPAND | wx.ALL, 1)
        
        self.infobaroverlay.COLOR_BACKGROUND = wx.Colour(255,255,153)
        self.infobaroverlay.COLOR_FOREGROUND = wx.Colour(50,50,50)
        self.infobaroverlay.COLOR_BACKGROUND_SEL = wx.Colour(255,255,230)
        self.infobaroverlay.COLOR_FOREGROUND_SEL = wx.Colour(0,0,0)
        
        self.SetBackgroundColour(wx.Colour(205,190,112))
        
        '''Create the webview'''
        self.webviewPanel = wx.Panel(self)
        wvPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.webviewPanel.SetSizer(wvPanelSizer)
        self.webview = wx.html2.WebView.New(self.webviewPanel)
        wvPanelSizer.Add(self.webview, 0, wx.EXPAND)
        self.webviewPanel.Layout()
        #Clear the blank page loaded on startup.        
        self.webview.ClearHistory()
        
        self.currentURL = ''
        
        vSizer.Add(self.webviewPanel, 2, wx.EXPAND) 
        
        '''Add all components'''
        self.SetSizer(vSizer)
        self.Layout()
        
        '''Add observerlist for checking load events'''
        self.loadlisteners = []
        
        '''Register the action on the event that a URL is being loaded and when finished loading'''
        self.Bind(wx.html2.EVT_WEB_VIEW_NAVIGATING, self.onURLNavigating, self.webview)
        self.Bind(wx.html2.EVT_WEB_VIEW_LOADED, self.onURLLoaded, self.webview)
        
        self.infobaroverlay.Bind(wx.EVT_ENTER_WINDOW, self.OnInfoBarMouseOver, self.infobaroverlay)
        self.infobaroverlay.Bind(wx.EVT_LEAVE_WINDOW, self.OnInfoBarMouseOut, self.infobaroverlay)

        self.HideInfoBar()
        
        self.webview.SetMinSize((2000, -1))   #Fix initial expansion, 2.9.4.0 bug
        
        if (False):
            self.webviewPanel.SetBackgroundColour(wx.Colour(255,255,255)) #Hide inital expansion, 2.9.4.0 bug
            wx.CallAfter(self.webview.LoadURL, "http://www.imdb.com/title/tt0458525/")       
    
    def goBackward(self, event):
        if self.webview.CanGoBack():
            self.webview.GoBack()
        
    def goForward(self, event):
        if self.webview.CanGoForward():
            self.webview.GoForward()
    
    def loadURLFromAdressBar(self, event):
        '''Load an URL from the adressbar'''
        url = self.adressBar.GetValue()
        if not urlparse.urlparse(url).scheme:
            url = 'http://' + url
        self.webview.LoadURL(url)
    
    def AddLoadedListener(self, listener):
        """Loaded listeners must expose a webpageLoaded(event) method
        """
        self.loadlisteners.append(listener)
        
    def RemoveLoadedListener(self, listener):
        self.loadlisteners.remove(listener)
    
    def __UrlToPageSrc(self, url):
        try:
            req = urllib2.Request(url, headers={'User-Agent':"Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11"})
            opener = urllib2.build_opener()
            contents = opener.open(req)
            return contents.read()
        except urllib2.URLError, e:
            return ''   # URL unknown, probably about:blank
    
    def __notifyLoadedListeners(self, event):
        for listener in self.loadlisteners:
            try:
                listener.webpageLoaded(event, self.__UrlToPageSrc(event.GetURL()))
            except:
                #Anything can go wrong with custom listeners, not our problem
                print >> sys.stderr, "WebBrowser: An error occurred in LoadedListener " + str(listener)
                traceback.print_exc()
    
    class MockEvent(object):
        
        def __init__(self, url):
            self.url = url
            
        def GetURL(self):
            return self.url
    
    def onURLNavigating(self, event):
        mainUrl = self.webview.GetCurrentURL()
        if self.currentURL != mainUrl:
            self.currentURL = mainUrl
            self.HideInfoBar()
            mockEvent = WebBrowser.MockEvent(mainUrl)
            thread.start_new(self.__notifyLoadedListeners, (mockEvent,))
    
    def onURLLoaded(self, event):
        '''Actions to be taken when an URL is loaded.'''
        #Update the adressbar
        self.adressBar.SetValue(self.webview.GetCurrentURL())
    
    def OnInfoBarMouseOver(self, event):
        """When we roll over the InfoBar, set our background to be brighter
            Set the foreground if any of our children want to stick to our style
        """
        self.infobaroverlay.SetBackgroundColour(self.infobaroverlay.COLOR_BACKGROUND_SEL)
        self.infobaroverlay.SetForegroundColour(self.infobaroverlay.COLOR_FOREGROUND_SEL)
        
    def OnInfoBarMouseOut(self, event):
        """When we roll off the InfoBar, set our background to be darker
            Set the foreground if any of our children want to stick to our style
        """
        self.infobaroverlay.SetBackgroundColour(self.infobaroverlay.COLOR_BACKGROUND)
        self.infobaroverlay.SetForegroundColour(self.infobaroverlay.COLOR_FOREGROUND)
    
    def SetInfoBarContents(self, *orderedContents):
        """Add content to the infobar in left -> right ordering
            Expects a list of tuples of a wxObject and a set of wxFlags
            For example:
                textlabel = wx.StaticText(webbrowser.infobaroverlay)
                textlabel.SetLabelMarkup(" <b>I am bold text</b>")
                webbrowser.SetInfoBarContents((textlabel,wx.CENTER))
        """
        #Remove all previous children
        previousContent = self.infobaroverlay.GetSizer()
        if previousContent:
            windows = []
            for child in previousContent.GetChildren():
                windows.append(child.GetWindow())
            for window in windows:
                if window:
                    self.infobaroverlay.RemoveChild(window)
                    window.Destroy()
            self.infobaroverlay.Layout()
        self.infobaroverlay.ClearBackground()
        #Overwrite with new sizer and contents
        infobarSizer = wx.BoxSizer(wx.HORIZONTAL)
        width = 0
        for contentTuple in orderedContents:
            flags = wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT if len(contentTuple)==1 else contentTuple[1]
            width += contentTuple[0].GetMaxWidth() if contentTuple[0].GetMaxWidth() != -1 else 0
            infobarSizer.Add(contentTuple[0], 0, flags)
        width = self.GetSize().width - width
        infobarSizer.Add((width,1))
        self.infobaroverlay.SetSizer(infobarSizer)
        infobarSizer.FitInside(self.infobaroverlay)
    
    def __fixInfobarHeight(self, height):
        """In wxPython 2.9.0 SetSizeHints does not function properly,
            we are only interested in fixing the height of the infobar
            and the webview here.
            Call this after laying out the vSizer of the main panel.
        """
        width, oHeight = self.infobaroverlay.GetSize()
        #Fix infobar
        self.infobaroverlay.SetSize((width, height))
        diffHeight = oHeight-height
        self.infobaroverlay.vSizer.SetItemMinSize(self.infobaroverlay, (width, height))
        self.infobaroverlay.vSizer.Fit(self.infobaroverlay)
        #Fix webview
        width, oHeight = self.webviewPanel.GetSize()
        self.infobaroverlay.vSizer.SetItemMinSize(self.webviewPanel, (width, oHeight + diffHeight))
        self.infobaroverlay.vSizer.Fit(self.webviewPanel)
        self.webviewPanel.GetSizer().SetItemMinSize(self.webview, (width, oHeight + diffHeight))
        self.webviewPanel.GetSizer().Fit(self.webview)
    
    def HideInfoBar(self):     
        """Hide the InfoBar immediately
        """ 
        self.infobaroverlay.SetSizeHints(-1,0,-1,0)
        self.infobaroverlay.vSizer.Layout()
        self.infobaroverlay.Hide()
        self.__fixInfobarHeight(0)
        self.Refresh()
        
    def ShowInfoBar(self, animtime=0.3, smoothness=10, finalHeight=28.0):      
        """Animated InfoBar drop down.
            Will attempt to be done in 'animtime' seconds
            Will chop the animation frames up in 'animtime'/'smoothness' iterations
            Will grow to a maximum of finalHeight if the sizer deems it appropriate
        """
        self.infobaroverlay.Show()
        for i in range(smoothness):
            start = time.time()
            height = int(finalHeight/smoothness*(i+1))
            self.infobaroverlay.SetSizeHints(-1, -1,-1, height)
            self.infobaroverlay.vSizer.Layout()
            self.infobaroverlay.Layout()
            self.__fixInfobarHeight(height)
            self.Refresh()
            remtime = animtime/smoothness-(time.time() - start)
            time.sleep(remtime if remtime > 0 else 0)
        