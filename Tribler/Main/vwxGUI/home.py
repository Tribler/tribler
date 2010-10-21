import wx
import sys
import os
import random

from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.list_header import FamilyFilterHeader
from Tribler.Main.vwxGUI.list_footer import TitleFooter
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Category.Category import Category
from Tribler.Core.CacheDB.SqliteCacheDBHandler import NetworkBuzzDBHandler, UserEventLogDBHandler

class Home(wx.Panel):
    def __init__(self):
        pre = wx.PrePanel()
        # the Create step is done by XRC. 
        self.PostCreate(pre)
        if sys.platform == 'linux2': 
            self.Bind(wx.EVT_SIZE, self.OnCreate)
        else:
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)

    def OnCreate(self, event):
        if sys.platform == 'linux2': 
            self.Unbind(wx.EVT_SIZE)
        else:
            self.Unbind(wx.EVT_WINDOW_CREATE)
        
        wx.CallAfter(self._PostInit)
        event.Skip()
    
    def _PostInit(self):
        self.SetBackgroundColour(wx.WHITE)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddStretchSpacer()
        
        panel = HomePanel(self)
        buzzpanel = BuzzPanel(panel)
        header, footer = panel.setControl("Network Buzz", buzzpanel)
        header.Bind(wx.EVT_ENTER_WINDOW, lambda event: buzzpanel.OnLeaveWindow())
        footer.Bind(wx.EVT_ENTER_WINDOW, lambda event: buzzpanel.OnLeaveWindow())
        buzzpanel.setUpdatePanel(footer)
        
        vSizer.Add(panel, 0, wx.EXPAND|wx.ALL, 20)
        
        self.SetSizer(vSizer)
        self.Layout()
        
class HomePanel(wx.Panel):
    def setControl(self, title, child_control):
        self.child_control = child_control
        self.guiutility = GUIUtility.getInstance()
        utility = self.guiutility.utility
        
        images = ("tl2.png", "tr2.png", "bl2.png", "br2.png")
        images = [os.path.join(utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images",image) for image in images]
        background = '#E6E6E6'
        
        self.SetBackgroundColour(background)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.header = FamilyFilterHeader(self, images[0], images[1], background, [])
        self.header.SetTitle(title)
        self.header.SetFF(self.guiutility.getFamilyFilter())
        
        footer = TitleFooter(self, images[2], images[3], background)
        
        vSizer.Add(self.header, 0, wx.EXPAND)
        vSizer.Add(child_control, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 1)
        vSizer.Add(footer, 0, wx.EXPAND)
        
        self.SetSizer(vSizer)
        self.Layout()
        return self.header, footer
    
    def DoLayout(self):
        self.Freeze()
        self.Layout()
        self.GetParent().Layout()
        self.Thaw()
        
    def toggleFamilyFilter(self):
        self.guiutility.toggleFamilyFilter()
        self.header.SetFF(self.guiutility.getFamilyFilter())
        self.child_control.ForceUpdate()
        
class BuzzPanel(wx.Panel):
    INACTIVE_COLOR = (255, 51, 0)
    ACTIVE_COLOR = (0, 105, 156)
    
    TERM_BORDERS = [15, 8, 8]
    DISPLAY_SIZES = [3,5,5]
    
    def __init__(self, parent):
        wx.Panel.__init__(self,parent)
        self.nbdb = NetworkBuzzDBHandler.getInstance()
        self.guiutility = GUIUtility.getInstance()
        self.xxx_filter = Category.getInstance().xxx_filter 
        self.buzz_cache = [[],[],[]]
        self.last_shown_buzz = None
        
        self.SetBackgroundColour(wx.WHITE)
        
        row1_font = self.GetFont()
        row1_font.SetPointSize(row1_font.GetPointSize() + 10)
        row1_font.SetWeight(wx.FONTWEIGHT_BOLD)
        
        row2_font = self.GetFont()
        row2_font.SetPointSize(row2_font.GetPointSize() + 4)
        row2_font.SetWeight(wx.FONTWEIGHT_BOLD)
        
        row3_font = self.GetFont()
        row3_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.TERM_FONTS = [row1_font, row2_font, row3_font]
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.vSizer)

        self.Bind(wx.EVT_ENTER_WINDOW, self.OnEnterWindow)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)

        self.updatePanel = None
        self.REFRESH_EVERY = 5
        self.refresh = 1
        self.OnRefreshTimer()
        
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnRefreshTimer, self.timer)
        self.timer.Start(1000, False)
        
    def ForceUpdate(self):
        self.buzz_cache = [[],[],[]]
        self.refresh = 1
        wx.CallAfter(self.OnRefreshTimer)
    
    def OnRefreshTimer(self, event = None):
        self.refresh -= 1
        if self.refresh <= 0:
            if self.IsShownOnScreen():
                # needs fine-tuning:
                # (especially for cold-start/fresh Tribler install?)
                samplesize = NetworkBuzzDBHandler.DEFAULT_SAMPLE_SIZE
                
                # simple caching
                # (does not check for possible duplicates within display_size-window!)
                if any(len(row) < 10 for row in self.buzz_cache):
                    buzz = self.nbdb.getBuzz(samplesize, with_freq=False, flat=True)
                    for i in range(len(buzz)):
                        random.shuffle(buzz[i])
                        self.buzz_cache[i].extend(buzz[i])
                
                if self.guiutility.getFamilyFilter():
                    xxx_filter = self.xxx_filter.isXXX
                else:
                    xxx_filter = lambda *args, **kwargs: False
                
                # consume cache
                # Note: if a term is fetched from two different row caches, it is shown in the
                # higher-frequency row, regardless of which information is fresher.
                filtered_buzz = [[],[],[]]
                empty = True
                added_terms = set()
                for i in range(len(filtered_buzz)):
                    while len(added_terms) < BuzzPanel.DISPLAY_SIZES[i] and len(self.buzz_cache[i]):
                        term = self.buzz_cache[i].pop(0)
                        if term not in added_terms and not xxx_filter(term, isFilename=False):
                            filtered_buzz[i].append(term)
                            added_terms.add(term)
                            empty = False
                
                if empty:
                    filtered_buzz = None
                self.DisplayTerms(filtered_buzz)
                self.last_shown_buzz = filtered_buzz
            self.refresh = self.REFRESH_EVERY
        
        if self.updatePanel:
            self.updatePanel.SetTitle('Update in %d...'%self.refresh)
                
    def DisplayTerms(self, rows):
        old_size = len(self.vSizer.GetChildren())
        
        self.Freeze()
        self.vSizer.ShowItems(False)
        self.vSizer.Clear()
        
        if rows is None or rows == []:
            self.vSizer.Add(wx.StaticText(self, -1, '...collecting buzz information...'), 0, wx.ALIGN_CENTER)
        else:
            for i in range(len(rows)):
                row = rows[i]
                if len(row) == 0:
                    # don't bother adding an empty hsizer
                    continue
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                
                hSizer.AddStretchSpacer(2)
                
                for term in row:
                    text = wx.StaticText(self, wx.ID_ANY, term)
                    text.SetFont(self.TERM_FONTS[i])
                    text.SetForegroundColour(BuzzPanel.INACTIVE_COLOR)
                    text.SetToolTipString("Click to search for '%s'"%term)
                    
                    hSizer.Add(text, 0, wx.BOTTOM, self.TERM_BORDERS[i])
                    text.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                    
                    hSizer.AddStretchSpacer()
                hSizer.AddStretchSpacer()                    
                self.vSizer.Add(hSizer, 0, wx.EXPAND)
            
        self.vSizer.Layout()
        new_size = len(self.vSizer.GetChildren())
        if new_size != old_size:
            self.GetParent().DoLayout()
        
        self.Thaw()
    
    def setUpdatePanel(self, panel):
        self.updatePanel = panel
    
    def DoPauseResume(self):
        def IsEnter(control):
            if getattr(control, 'GetWindow', False):
                control = control.GetWindow()
                
            if getattr(control, 'enter', False): 
                return True
        
            if getattr(control, 'GetChildren', False): 
                children = control.GetChildren()
                for child in children:
                    if IsEnter(child):
                        return True
            return False
        
        enter = getattr(self, 'enter', False) or IsEnter(self)
        timerstop = not enter #stop timer if one control has enter==true
        
        if timerstop != self.timer.IsRunning():
            if enter:
                self.timer.Stop()
                self.updatePanel.SetTitle('Update has paused')
            else:
                self.timer.Start(1000, False)
                self.updatePanel.SetTitle('Resuming update')
    
    def OnMouse(self, event):
        if event.Entering() or event.Moving():
            self.OnEnterWindow(event)
        elif event.Leaving():
            self.OnLeaveWindow(event)
        elif event.LeftUp():
            self.OnClick(event)
    
    def OnEnterWindow(self, event):
        evtobj = event.GetEventObject()
        evtobj.enter = True
        self.DoPauseResume()
        
        if evtobj != self:
            self.ShowSelected(evtobj)
        
    def OnLeaveWindow(self, event = None):
        if event:
            evtobj = event.GetEventObject()
            evtobj.enter = False
        
        self.DoPauseResume()
        self.ShowSelected()

    def ShowSelected(self, statictext = None):
        if statictext:
            statictext.enter = True
            statictext.SetForegroundColour(BuzzPanel.ACTIVE_COLOR)
            statictext.Refresh()
        
        for column in self.GetChildren():
            if column != statictext and isinstance(column, wx.StaticText):
                if column.ForegroundColour != BuzzPanel.INACTIVE_COLOR:
                    column.enter = False
                    column.SetForegroundColour(BuzzPanel.INACTIVE_COLOR)
                    column.Refresh()

    def OnClick(self, event):
        evtobj = event.GetEventObject()
        term = evtobj.GetLabel()
        
        self.guiutility.dosearch(term)
        
        #Deselect all terms + doresume
        self.ShowSelected()
        self.DoPauseResume()
        
        uelog = UserEventLogDBHandler.getInstance()
        uelog.addEvent(message=repr((term, self.last_shown_buzz)))