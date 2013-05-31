import wx
import wx.html2
import urlparse
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
        self.infobaroverlay.SetSizeHints(-1,0,-1,0)
        self.infobaroverlay.SetBackgroundColour(wx.Colour(255,255,153))
        self.infobaroverlay.vSizer = vSizer
        vSizer.Add(self.infobaroverlay, 1, wx.EXPAND | wx.ALL, 1)
        
        self.infobaroverlay.COLOR_BACKGROUND = wx.Colour(255,255,153)
        self.infobaroverlay.COLOR_FOREGROUND = wx.Colour(50,50,50)
        self.infobaroverlay.COLOR_BACKGROUND_SEL = wx.Colour(255,255,230)
        self.infobaroverlay.COLOR_FOREGROUND_SEL = wx.Colour(0,0,0)
        
        self.SetBackgroundColour(wx.Colour(205,190,112))
        
        '''Create the webview'''
        self.webview = wx.html2.WebView.New(self)
        #Clear the blank page loaded on startup.        
        self.webview.ClearHistory()
        
        vSizer.Add(self.webview, 2, wx.EXPAND) 
        
        '''Add all components'''
        self.SetSizer(vSizer)
        self.Layout()
        
        '''Add observerlist for checking load events'''
        self.loadlisteners = []
        
        '''Register the action on the event that a URL is being loaded and when finished loading'''
        self.Bind(wx.html2.EVT_WEBVIEW_NAVIGATING, self.onURLNavigating, self.webview)
        self.Bind(wx.html2.EVT_WEBVIEW_LOADED, self.onURLLoaded, self.webview)
        
        self.infobaroverlay.Bind(wx.EVT_ENTER_WINDOW, self.OnInfoBarMouseOver, self.infobaroverlay)
        self.infobaroverlay.Bind(wx.EVT_LEAVE_WINDOW, self.OnInfoBarMouseOut, self.infobaroverlay)
        
        self.webview.LoadURL("http://www.imdb.com/title/tt0458525/")       
        
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
    
    def onURLNavigating(self, event):
        self.HideInfoBar()
    
    def onURLLoaded(self, event):
        '''Actions to be taken when an URL is loaded.'''
        #Update the adressbar
        self.adressBar.SetValue(self.webview.GetCurrentURL())
        for listener in self.loadlisteners:
            try:
                listener.webpageLoaded(event, self.webview.GetPageSource())
            except:
                #Anything can go wrong with custom listeners, not our problem
                print >> sys.stderr, "WebBrowser: An error occurred in LoadedListener " + str(listener)
                traceback.print_exc()
    
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
            self.infobaroverlay.Layout()
        #Overwrite with new sizer and contents
        infobarSizer = wx.BoxSizer(wx.HORIZONTAL)
        i = 0
        for contentTuple in orderedContents:
            flags = wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT if len(contentTuple)==1 else contentTuple[1]
            infobarSizer.Add(contentTuple[0], i, flags)
            i += 1
        self.infobaroverlay.SetSizer(infobarSizer)
        infobarSizer.Fit(self.infobaroverlay)
    
    def HideInfoBar(self):     
        """Hide the InfoBar immediately
        """ 
        self.infobaroverlay.SetSizeHints(-1,0,-1,0)
        self.infobaroverlay.vSizer.Layout()
        self.Refresh()
        
    def ShowInfoBar(self, animtime=0.3, smoothness=10, finalHeight=28.0):      
        """Animated InfoBar drop down.
            Will attempt to be done in 'animtime' seconds
            Will chop the animation frames up in 'animtime'/'smoothness' iterations
            Will grow to a maximum of finalHeight if the sizer deems it appropriate
        """
        for i in range(smoothness):
            start = time.time()
            self.infobaroverlay.SetSizeHints(-1, -1,-1, int(finalHeight/smoothness*(i+1)))
            self.infobaroverlay.vSizer.Layout()
            self.infobaroverlay.Layout()
            self.Refresh()
            remtime = animtime/smoothness-(time.time() - start)
            time.sleep(remtime if remtime > 0 else 0)
        