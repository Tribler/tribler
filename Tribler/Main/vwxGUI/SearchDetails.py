# Written by Jelle Roozenburg, Maarten ten Brinke 
# see LICENSE.txt for license information
import wx, os
from traceback import print_stack
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

class SearchDetailsPanel(wx.Panel):
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        
        self.addComponents()
        
        
    def addComponents(self):
        
        
        #(self, -1, wx.DefaultPosition, wx.Size(16,16),name='down')
        self.vSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.textPanel = wx.Panel(self)        
        
        self.text = wx.StaticText(self.textPanel, -1, '')
        self.text.SetForegroundColour(wx.Colour(150,150,150))
        sizer.Add(self.text, 1, wx.ALL, 0)
        
        self.textPanel.SetSizer(sizer)
        self.textPanel.SetAutoLayout(1)
        self.textPanel.SetForegroundColour(wx.WHITE)        
        self.textPanel.SetBackgroundColour(wx.Colour(255,255,255))        
        self.text.SetSize((100, 15))
        self.hSizer.Add(self.textPanel, 1, wx.TOP|wx.EXPAND, 3)
        self.vSizer.Add(self.hSizer, 1, wx.TOP|wx.EXPAND, 3)

        ##self.hSizer2 = wx.BoxSizer(wx.HORIZONTAL)       
        ##self.stopMoreButton = SwitchButton(self, -1, wx.DefaultPosition, wx.DefaultSize, name='searchStop')
        ##self.stopMoreButton.Bind(wx.EVT_LEFT_UP, self.stopMoreClicked)
        ##self.stopMoreButton.SetToolTipString(self.guiUtility.utility.lang.get('searchStop'))        
        ##self.clearButton = tribler_topButton(self, -1, wx.DefaultPosition, wx.DefaultSize, name='searchClear')        
        ##self.clearButton.SetToolTipString(self.guiUtility.utility.lang.get('searchClear'))
        ##self.hSizer2.Add([9,5],0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        ##self.hSizer2.Add(self.stopMoreButton, 0, wx.ALL, 1)
        ##self.hSizer2.Add(self.clearButton, 0, wx.ALL, 1)
        ##self.vSizer.Add(self.hSizer2, 0, wx.TOP|wx.EXPAND, 3)
        
        #self.hSizer.Add([8,5],0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        self.SetMinSize((-1, 40))
        self.SetBackgroundColour(wx.Colour(255,255,255))
        self.vSizer.Layout()
        self.Layout()
        self.searchBusy = True #??
        #self.Show(True)
        self.results = {}
        
    def setMessage(self, stype, finished, num, keywords = []):
        if stype:
            self.results[stype] = num # FIXME different remote search overwrite eachother
        
        total = sum([v for v in self.results.values() if v != -1])
        
        if keywords:
            if type(keywords) == list:
                self.keywords = " ".join(keywords)
            else:
                self.keywords = keywords

        if finished:  
            msg = self.guiUtility.utility.lang.get('finished_search') % (self.keywords, total)
            self.searchFinished(set_message=False)
        else:
            msg = self.guiUtility.utility.lang.get('going_search') % (self.keywords, total)
        
            
        self.text.SetLabel(msg)
        tt = []
        
        for pair in self.results.items():
            key, value = pair
            if value == -1:
                continue
            tt.append(self.guiUtility.utility.lang.get('search_'+key) % value)
            
        tt.sort()
        tt = os.linesep.join(tt)
        self.textPanel.SetToolTipString(tt)
        self.text.SetToolTipString(tt)
        
    def startSearch(self):
        ##self.stopMoreButton.setToggled(False)
        self.searchBusy = True
        
    def stopSearch(self):
        # call remoteSearch and Web2.0 search to stop
        self.guiUtility.stopSearch()
    
#    def findMoreSearch(self):
#        # call remoteSearch and Web2.0 search to find more
#        self.startSearch()
#        grid = self.guiUtility.standardOverview.getGrid()
#        if grid.dod:
#            grid.dod.requestMore(grid.items)
    
    def searchFinished(self, set_message = True):
        self.searchBusy = False
        ##self.stopMoreButton.setToggled(True)
        if set_message:
            self.setMessage(None, True, 0, None)
    
    def stopMoreClicked(self, event = None):
        if event:
            event.Skip()
        if self.searchBusy:
            self.stopSearch()
            self.searchFinished()
        #else: # find more
        #    self.findMoreSearch()
            
