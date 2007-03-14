# Written by Jelle Roozenburg
# see LICENSE.txt for license information

import wx, math, time, os, sys, threading
from traceback import print_exc
from abcfileframe import TorrentDataManager
from Tribler.utilities import *
from Tribler.TrackerChecking.ManualChecking import SingleManualChecking
from safeguiupdate import DelayedInvocation
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.unicode import *
from copy import deepcopy

BORDER_EXPAND = wx.ALL|wx.GROW
BORDER = wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.ALIGN_LEFT


DEBUG = False

class ABCSplitterWindow(wx.SplitterWindow):
    def __init__(self, parent, id):
        wx.SplitterWindow.__init__(self, parent, id)
        self.utility = parent.utility
        self.SetMinimumPaneSize(50) # Disables the doubleClick=Unsplit functionality
        
       
        
class StaticGridPanel(wx.Panel):
    """
    A panel that shows subpanels with a static column count
    and a rowcount dependend on the size of the StaticGridPanel
    
    """
    def __init__(self, parent, cols):
        wx.Panel.__init__(self, parent, -1, size=wx.DefaultSize)
        #self.SetSize((500,500))
        
        self.parent = parent
        self.detailPanel = parent.detailPanel
        self.cols = cols
        self.currentRows = 0
        self.subPanelHeight = 100 # This will be update after first refresh
        
        self.panels = []
        self.currentData = 0
        self.Bind(wx.EVT_SIZE, self.onResize)
        
        self.addComponents()
        self.Centre()
        self.Show()
        self.Layout();
        self.Refresh()
        #print "vSizer: %s, Panel: %s"% (self.vSizer.GetSize(), self.GetSize())
        
        
    def addComponents(self):
        self.Show(False)
        self.SetBackgroundColour(wx.WHITE)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.calculateRows()
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        

    def setData(self, panelNumber, data):
        try:
            hSizer = self.vSizer.GetItem(panelNumber%self.currentRows).GetSizer()
            panel = hSizer.GetItem(panelNumber/ self.currentRows).GetWindow()
            
            panel.setData(data)
        except:
            print >>sys.stderr,"contentpanel: Error: Could not set data in panel number %d, with %d cols" % (panelNumber, self.cols)
            print_exc(file=sys.stderr)
    
    def clearAllData(self):
        for i in range(0, self.items):
            self.setData(i, None)
            
    def onResize(self, event=None):
        
        #print ".",
        self.calculateRows()
        if event:
            event.Skip()
        
    def updateSubPanelHeight(self):
        try:
            self.subPanelHeight = self.vSizer.GetItem(0).GetSizer().GetItem(0).GetWindow().GetSize()[1]
        except:
            #print 'Could not get subpanelheight'
            pass
        
    def calculateRows(self):
    
        size = self.GetSize()
        oldRows = self.currentRows
        self.updateSubPanelHeight()
        if size[1] < 50 or self.subPanelHeight == 0:
            self.currentRows = 0
            self.items = 0
        else:
            self.currentRows = size[1] / self.subPanelHeight
            self.items = self.cols * self.currentRows
        
        if oldRows != self.currentRows: #changed
            if DEBUG:
                print >>sys.stderr,'contentpanel: Size updated to %d rows and %d columns, oldrows: %d'% (self.currentRows, self.cols, oldRows)
            
            self.updatePanel(oldRows, self.currentRows)
            self.parent.gridResized(self.currentRows)
            
    def updatePanel(self, oldRows, newRows):
        #
        if newRows > oldRows:
            for i in range(oldRows, newRows):
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                self.panels.append([])
                for panel in range(0, self.cols):
                    dataPanel = TorrentPanel(self)
                    self.panels[i].append(dataPanel)
                    #dataPanel.SetSize((-1, self.subPanelHeight))
                    hSizer.Add(dataPanel, 1, wx.ALIGN_CENTER|wx.ALL|wx.GROW, 0)
                self.vSizer.Add(hSizer, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
        elif newRows < oldRows:
            #print "Destroying row %d up to %d" % (newRows, oldRows-1)
            for row in range(oldRows-1, newRows-1, -1):
                # Destroy old panels
                for col in range(self.cols-1, -1, -1): #destroy panels right to left
                    panel = self.panels[row][col]
                    panel.Destroy()
                    del self.panels[row][col]
                    
                assert self.panels[row] == [], 'We deleted all panels, still the row is %s' % self.panels[row]
                del self.panels[row]
                self.vSizer.Detach(row) # detach hSizer of the row
          
    
    def updateSelection(self):
        """Deselect all torrentPanels, but the one selected in detailPanel
        If no torrent is selected in detailPanel, let first in grid be selected
        """
        
        title = None
        # Select first item
        if not self.detailPanel.data:
            try:
                firstItem = self.panels[0][0].data
                if firstItem:
                    self.detailPanel.setData(firstItem)
                    title = self.detailPanel.data.get('content_name')
            except:
                pass
        
        if self.detailPanel.data:
            title = self.detailPanel.data.get('content_name')

            
        
        for row in self.panels:
            for pan in row:
                try:
                    paneltitle = pan.data['content_name']
                except:
                    paneltitle = None
                    
                if paneltitle != title or paneltitle == None:
                    pan.deselect()
                else:
                    pan.select()
        

class GridPanel(wx.Panel):
    """
    GridPanel adds paging functionality (a PagerPanel) to the StaticGridPanel.
    Use setData() and setPageNumber() for content selection.
    """
    def __init__(self, parent, cols):
        wx.Panel.__init__(self, parent, -1, size=wx.DefaultSize)
        #self.SetSize((500,500))
        #self.SetBackgroundColour(wx.RED)
        self.parent = parent
        self.detailPanel = parent.detailPanel
        self.utility = parent.utility
        self.cols = cols
        self.items = 0
        self.data = None
        self.currentData = 0
        
        self.addComponents()
        self.Centre()
        self.Show()
        
        
    def addComponents(self):
        self.Show(False)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.staticGrid = StaticGridPanel(self, self.cols)
        self.vSizer.Add(self.staticGrid, 1, BORDER_EXPAND, 1)
        self.pagerPanel = PagerPanel(self)
        self.vSizer.Add(self.pagerPanel, 0, BORDER_EXPAND, 1)
        
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        #print "vSizer: %s, Panel: %s"% (self.vSizer.GetSize(), self.GetSize())

    def setData(self, dataList, resetPages = True):
        #print 'SetData by thread: %s' % threading.currentThread()
        self.data = dataList
        if resetPages:
            self.currentData = 0
            self.pagerPanel.currentPage = 0
        self.refreshPanels()
        
        
    def refreshPanels(self):
        "Refresh TorrentPanels with correct data and refresh pagerPanel"
        self.pagerPanel.refresh()
                
        if self.data == None:
            self.staticGrid.clearAllData()
        else:
            for i in range(0, self.items):
                dataIndex = i+ self.currentData
                if dataIndex < len(self.data):
                    self.staticGrid.setData(i, self.data[dataIndex])
                else:
                    self.staticGrid.setData(i, None)
        
        self.staticGrid.updateSelection()
    
    def gridResized(self, rows):
        self.items = self.cols * rows
        self.refreshPanels()
        
    def setPageNumber(self, page):
        if not self.data:
            return
        old = self.currentData
        if self.items * page < len(self.data) and page>=0:
            self.currentData = self.items*page
        if old != self.currentData:
            self.refreshPanels()
            



class PagerPanel(wx.Panel):
    def __init__(self, parent, numPages=10):
        wx.Panel.__init__(self, parent, -1)

        self.beginPage = 0
        self.currentPage = 0
        self.numPages = numPages
        self.totalPages = 0
        self.totalItems = 0
        self.itemsPerPage = 0
        self.currentDots = [None, None]
        
        self.utility = parent.utility
        self.pageNumbers = []
        self.staticGrid = parent.staticGrid
        self.parent = parent
        self.SetMinSize((50, self.GetCharHeight()))
        self.addComponents()
        self.Centre()
        self.Show()

    def addComponents(self):
        self.SetBackgroundColour(wx.WHITE)
        self.normalFont = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        self.boldFont  = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        self.boldFont.SetWeight(wx.BOLD)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.number = wx.StaticText(self,-1,"",wx.Point(3,111),wx.Size(49,13))
        self.number.SetFont(self.normalFont)
        self.hSizer.Add(self.number, 3, BORDER_EXPAND, 0)
        
        # left arrows
#        self.leftPages = ImagePanel(self)
#        self.leftPages.SetBitmap(wx.Bitmap("prev2.gif",wx.BITMAP_TYPE_GIF))
#        self.hSizer.Add(self.leftPages, 0, BORDER_EXPAND, 0)
        self.left = ImagePanel(self)
        self.left.SetBackgroundColour(wx.WHITE)
        self.left.SetBitmap("left.png")
        self.left.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.hSizer.Add(self.left, 0, wx.LEFT|wx.RIGHT, 10)
        
        #page numbers
        self.refreshPageNumbers()
        
        
        self.right = ImagePanel(self)
        self.right.SetBackgroundColour(wx.WHITE)
        self.right.SetBitmap("right.png")
        self.right.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.hSizer.Add(self.right, 0, wx.LEFT|wx.RIGHT, 10)
        
       
        
        self.hSizer.SetMinSize((50,50))
        self.SetSizer(self.hSizer);self.SetAutoLayout(1);self.Layout();
        self.Refresh()
   
   
    def refreshPageNumbers(self):
        
        # Update beginPage (first page number on screen)
        if self.currentPage >= self.beginPage+self.numPages:
            self.beginPage +=1
        
        self.beginPage = max(0, min(self.totalPages-self.numPages, self.beginPage))
        if self.currentPage <= self.beginPage-1:
                self.beginPage = max(0, self.beginPage - 1)
                
        rightDots = self.beginPage+self.numPages < self.totalPages
        leftDots = self.beginPage != 0
        self.setPageNumbers(self.beginPage, min(self.numPages,self.totalPages) , self.currentPage, leftDots, rightDots)
        self.parent.setPageNumber(self.currentPage)
        
        
    def setPageNumbers(self, begin, number, current, leftDots, rightDots):
        """
        Put the right numbers in the pagefield. If necessary, create new statictexts.
        Highlight current page number
        """
        
        #print 'Begin %d, number %d, current %d' % (begin, number, current)
        
        refresh = False
        # Guarantee right amount of statictexts
        currentPageNumber = len(self.pageNumbers)
        if number > currentPageNumber:
            while (len(self.pageNumbers) < number):
                text = StaticText(self, -1, "")
                text.SetBackgroundColour(self.GetBackgroundColour())
                text.Bind(wx.EVT_LEFT_UP, self.mouseAction)
                self.pageNumbers.append(text)
                self.hSizer.Insert(len(self.pageNumbers)+1, text, 0, wx.LEFT|wx.RIGHT, 10)
            refresh = True
        elif number < currentPageNumber:
            for i in range(number, currentPageNumber):
                self.hSizer.Detach(self.pageNumbers[i])
                self.pageNumbers[i].Destroy()
                #self.pageNumbers[i].Show(False)
            self.pageNumbers = self.pageNumbers[:number]
            refresh = True
          
        # Manage dots before and after page numbers
        if rightDots and not self.currentDots[1]:
            dots = wx.StaticText(self, -1, "...")
            extra =  int(bool(self.currentDots[0]))
            
            self.hSizer.Insert(len(self.pageNumbers)+2+extra, dots, 0, wx.LEFT|wx.RIGHT, 2)
            self.currentDots[1] = dots
            refresh = True
        
        if not rightDots and self.currentDots[1]:
            self.hSizer.Detach(self.currentDots[1])
            self.currentDots[1].Destroy()
            self.currentDots[1] = None
            refresh = True
        
        if leftDots and not self.currentDots[0]:
            dots = wx.StaticText(self, -1, "...")
            
            self.hSizer.Insert(2, dots, 0, wx.LEFT|wx.RIGHT, 2)
            self.currentDots[0] = dots
            refresh = True
        
        if not leftDots and self.currentDots[0]:
            self.hSizer.Detach(self.currentDots[0])
            self.currentDots[0].Destroy()
            self.currentDots[0] = None
            refresh = True
            
        
        if refresh:
            self.hSizer.Layout()
            self.Refresh()
            self.Show(True)
            
        #print '%d statictexts' % (len(self.pageNumbers))
        # Put right numbers in statictexts
        page = begin
        for panel in self.pageNumbers:
            panel.SetLabel(str(page+1))
            if page == current:
                
                panel.SetFont(self.boldFont)
            else:
                panel.SetFont(self.normalFont)
            page+=1
    
    def refresh(self):
        "Called by Grid if size or data changes"
        self.totalItems = len(self.parent.data)
        self.itemsPerPage = self.parent.items
        
        # if dummy item "Searching for content is shown, do not count it as content
        if self.totalItems == 1 and self.parent.data[0].get('content_name','no_name') == self.utility.lang.get('searching_content'):
            self.totalItems = 0
        
        
        if self.itemsPerPage == 0:
            self.totalPages = 0
        else:
            self.totalPages = int(math.ceil(self.totalItems/float(self.itemsPerPage)))

            
        category = self.parent.parent.categorykey
        self.number.SetLabel('%d %s %s%s / %d %s%s' % (self.totalItems, category.lower(), self.utility.lang.get('item'), getPlural(self.totalItems), self.totalPages, self.utility.lang.get('page'), getPlural(self.totalPages)))
        
        if self.currentPage >= self.totalPages:
            self.currentPage = max(self.totalPages -1, 0)
        self.refreshPageNumbers()

#    def imageClicked(self, event):
#        obj = event.GetEventObject()
#        self.mouseAction(obj, event)
#        
    def mouseAction(self, event):
        
        obj = event.GetEventObject()
        
        old = self.currentPage
        #print '%s did mouse' % obj
        if obj == self.left:
            self.currentPage = max(0, self.currentPage-1)
        elif obj == self.right:
            self.currentPage = min(self.totalPages-1, self.currentPage+1)
        elif obj in self.pageNumbers:
            index = self.pageNumbers.index(obj)
            self.currentPage = self.beginPage+index
        else:
            event.Skip()
            return
        
        self.refreshPageNumbers()
        

    
TORRENTPANEL_BACKGROUND = None
        
class TorrentPanel(wx.Panel):
    """
    TorrentPanel shows one content item inside the StaticGridPanel
    Currently, TorrentPanel only shows torretname, seeders, leechers and size
    """
    def __init__(self, parent):
        global TORRENTPANEL_BACKGROUND
        
        wx.Panel.__init__(self, parent, -1)
        self.detailPanel = parent.parent.detailPanel
        self.contentFrontPanel = parent.parent.parent
        self.utility = parent.parent.utility
        self.parent = parent
        self.data = None
        self.datacopy = None
        self.titleLength = 37 # num characters
        self.selected = False
        self.warningMode = False
        self.oldCategoryLabel = None
        self.addComponents()
        #self.Centre()
        self.Show()

    def addComponents(self):
        self.Show(False)
        #self.SetMinSize((50,50))
        self.SetBackgroundColour(wx.WHITE)
        self.selectedColour = wx.Colour(245,208,120)
        try:
            self.unselectedColour = wx.Colour(0,0,0,0)
        except:
            self.unselectedColour = wx.WHITE
        
        self.vSizer = wx.StaticBoxSizer(wx.StaticBox(self,-1,""),wx.VERTICAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        # Add title
        self.title =StaticText(self,-1,"")
        #self.title.SetBackgroundColour(self.GetBackgroundColour())
        font = self.title.GetFont()
        font.SetWeight(wx.BOLD)
        self.title.SetFont(font)
        self.vSizer.Add(self.title, 0, BORDER_EXPAND, 5)
        
        # Add seeder, leecher, size
        self.seeder = StaticText(self, -1, '')
        self.seederPic = ImagePanel(self)
        self.seederBitmap = "up.png"
        self.warningBitmap = "warning.gif"
        self.leecherBitmap = "down.png"
        self.seederPic.SetBitmap(self.seederBitmap)
        self.leecher = StaticText(self, -1, '')
        self.leecherPic = ImagePanel(self)
        self.leecherPic.SetBitmap(self.leecherBitmap)
        self.size = StaticText(self, -1, '')
        self.sizePic = ImagePanel(self)
        self.sizePic.SetBitmap("size.png")
        self.recommPic = ImagePanel(self)
        self.recommPic.SetBitmap("love.png")
        self.recomm = StaticText(self, -1, '')
                
        if self.unselectedColour == wx.WHITE:
            self.seeder.SetBackgroundColour(wx.WHITE)
            self.seederPic.SetBackgroundColour(wx.WHITE)
            self.leecher.SetBackgroundColour(wx.WHITE)
            self.leecherPic.SetBackgroundColour(wx.WHITE)
            self.size.SetBackgroundColour(wx.WHITE)
            self.sizePic.SetBackgroundColour(wx.WHITE)
            self.recommPic.SetBackgroundColour(wx.WHITE)
            self.recomm.SetBackgroundColour(wx.WHITE)
            
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer.Add(self.seederPic, 0, wx.RIGHT, 1)
        self.hSizer.Add(self.seeder, 0, wx.RIGHT, 15)     
        self.hSizer.Add(self.leecherPic, 0, wx.RIGHT, 1)
        self.hSizer.Add(self.leecher, 0, wx.RIGHT, 15)
        self.hSizer.Add(self.sizePic, 0, wx.RIGHT, 5)
        self.hSizer.Add(self.size, 0, wx.RIGHT, 15)
        self.hSizer.Add(self.recommPic, 0, wx.RIGHT, 5)
        self.hSizer.Add(self.recomm, 0, wx.RIGHT, 15)
        

        self.vSizer.Add(self.hSizer, 0, wx.ALL, 3)
        self.SetBackgroundColour(wx.WHITE)

        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
                             
    def setData(self, torrent):
        # set bitmap, rating, title
        
        
        try:
            if self.datacopy['infohash'] == torrent['infohash']:
                # Do not update torrents that have no new seeders/leechers/size
                if (self.datacopy['seeder'] == torrent['seeder'] and
                    self.datacopy['leecher'] == torrent['leecher'] and
                    self.datacopy['length'] == torrent['length'] and
                    self.datacopy.get('myDownloadHistory') == torrent.get('myDownloadHistory')):
                    return
        except:
            pass
        
        self.data = torrent
        self.datacopy = deepcopy(torrent)
        
        if torrent == None:
            self.vSizer.GetStaticBox().Show(False)
            torrent = {}
        else:
            self.vSizer.GetStaticBox().Show(True)
    
        if torrent.get('content_name'):
            title = torrent['content_name'][:self.titleLength]
            self.title.Enable(True)
            self.title.SetLabel(title)
            #self.title.Wrap(-1) # no wrap
            self.title.SetToolTipString(torrent['content_name'])
        else:
            self.title.SetLabel('')
            self.title.SetToolTipString('')
            self.title.Enable(False)
            
        if torrent.get('seeder') != None and torrent.get('leecher') != None: # category means 'not my downloaded files'
            self.seederPic.SetEnabled(True)
            self.seeder.Enable(True)
                        
            if torrent['seeder'] < 0:
                self.leecherPic.SetEnabled(False)
                self.leecher.SetLabel('')
                self.leecher.Enable(False)
                self.leecher.SetToolTipString('')
                self.seederPic.SetBitmap(self.warningBitmap)
                if torrent['seeder'] == -1:
                    self.seeder.SetLabel("Outdated swarminfo")
                    self.seeder.SetToolTipString(self.utility.lang.get('swarm_outdated_tool'))
                elif torrent['seeder'] == -2:
                    self.seeder.SetLabel("Swarm not available")
                    self.seeder.SetToolTipString(self.utility.lang.get('swarm_unavailable_tool'))
                else:
                    self.seeder.SetLabel("%d, %d" % (torrent['seeder'], torrent['leecher']))
            else:
                self.leecherPic.SetEnabled(True)
                self.seederPic.SetBitmap(self.seederBitmap)
                self.seeder.Enable(True)    
                self.seeder.SetLabel(str(torrent['seeder']))
                self.seeder.SetToolTipString(self.utility.lang.get('seeder_tool'))
                self.leecher.Enable(True)
                self.leecher.SetLabel(str(torrent['leecher']))
                self.leecher.SetToolTipString(self.utility.lang.get('leecher_tool'))
        else:
            self.seeder.SetLabel('')
            self.seeder.Enable(False)
            self.seeder.SetToolTipString('')
            self.seederPic.SetEnabled(False)
            self.leecher.SetLabel('')
            self.leecher.Enable(False)
            self.leecher.SetToolTipString('')
            self.leecherPic.SetEnabled(False)
            
        if torrent.get('length'):
            self.sizePic.SetEnabled(True)
            self.size.Enable(True)
            self.size.SetLabel(self.utility.size_format(torrent['length']))
            self.size.SetToolTipString(self.utility.lang.get('size_tool'))
            
        else:
            self.size.SetLabel('')
            self.size.SetToolTipString('')
            self.size.Enable(False)
            self.sizePic.SetEnabled(False)
            
        if torrent.get('relevance', 0.0) >= 50:
            self.recomm.SetLabel("%.1f" % (torrent['relevance']/1000.0))
            self.recommPic.SetEnabled(True)
            self.recomm.Enable(True)
            self.recomm.SetToolTipString(self.utility.lang.get('recomm_relevance'))
        else:
            self.recomm.SetLabel('')
            self.recomm.SetToolTipString('')
            self.recomm.Enable(False)
            self.recommPic.SetEnabled(False)
         # Since we have only one category per torrent, no need to show it

#        if torrent.get('category') and torrent.get('myDownloadHistory', False):
#            categoryLabel = ' / '.join(torrent['category'])
#        else:
#            categoryLabel = ''
#        if self.oldCategoryLabel != categoryLabel:
#            self.vSizer.GetStaticBox().SetLabel(categoryLabel)
#            self.oldCategoryLabel = categoryLabel

        
        self.Layout()
        self.Refresh()
        self.parent.Refresh()
        
    def select(self):
        self.selected = True
        old = self.title.GetBackgroundColour()
        if old != self.selectedColour:
            self.title.SetBackgroundColour(self.selectedColour)
            self.Refresh()
        
        
    def deselect(self):
        self.selected = False
        old = self.title.GetBackgroundColour()
        if old != self.unselectedColour:
            self.title.SetBackgroundColour(self.unselectedColour)
            self.Refresh()
    
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'contentpanel: deleting'
                    contentPanel = self.parent.parent.parent
                    contentPanel.deleteTorrent(self.data)
        event.Skip()
        
    def mouseAction(self, event):
        
        self.SetFocus()
        if self.data:
            try:
                title = self.detailPanel.data['content_name']
            except:
                title = None
            if self.data.get('content_name','') != title:
                self.detailPanel.setData(self.data)
                #print "Clicked"
                self.parent.updateSelection()
            

class CategoryPanel(wx.Panel):
    """
    CategoryPanel shows the content categories and delegates the ContentFrontPanel
    to load the right torrent data in the gridPanel
    """
    def __init__(self, parent, categories, myHistory):
        
        wx.Panel.__init__(self, parent, -1)
        self.utility = parent.utility
        self.parent = parent
        self.myHistorySelected = False
        self.categories = categories
        self.myHistory = myHistory
        self.addComponents()
        self.Centre()
        self.Show()

    def addComponents(self):
        self.Show(False)
        #self.SetMinSize((50,50))
        self.SetBackgroundColour(wx.Colour(197,220,241))
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.unselFont = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        self.unselFont.SetPointSize(self.unselFont.GetPointSize()+2)
        self.selFont = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        self.selFont.SetPointSize(self.unselFont.GetPointSize())
        self.selFont.SetWeight(wx.BOLD)
        self.orderUnselFont = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        self.orderUnselFont.SetPointSize(self.unselFont.GetPointSize())
        self.orderUnselFont.SetStyle(wx.FONTSTYLE_ITALIC)
        self.orderSelFont = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        self.orderSelFont.SetPointSize(self.unselFont.GetPointSize())
        self.orderSelFont.SetStyle(wx.FONTSTYLE_ITALIC)
        self.orderSelFont.SetWeight(wx.BOLD)
        
        # Order types
        self.orderSizer = wx.BoxSizer(wx.HORIZONTAL)
        # Removed ordering, because recommendation is not effective
                
#        label1 = wx.StaticText(self, -1, self.utility.lang.get('order_by')+': ')
#        label1.SetMinSize((100, -1))
#        self.orderSizer.Add(label1, 0, wx.LEFT|wx.RIGHT, 10)
        
        self.swarmLabel = StaticText(self, -1, self.utility.lang.get('swarmsize'))
        self.swarmLabel.SetToolTipString(self.utility.lang.get('swarmsize_tool'))
        self.swarmLabel.SetBackgroundColour(self.GetBackgroundColour())
        
        
        self.swarmLabel.SetFont(self.orderSelFont)
        self.orderSizer.Add(self.swarmLabel, 0, wx.LEFT|wx.RIGHT, 10)
        
        self.recommLabel = StaticText(self, -1, self.utility.lang.get('recommended'))
        self.recommLabel.SetBackgroundColour(self.GetBackgroundColour())
        self.recommLabel.SetFont(self.orderUnselFont)
        self.recommLabel.SetToolTipString(self.utility.lang.get('recommendation_tool'))
        self.orderSizer.Add(self.recommLabel, 1, wx.LEFT|wx.RIGHT, 10)
        
        self.myHistoryLabel = StaticText(self, -1, self.myHistory)
        self.myHistoryLabel.SetBackgroundColour(self.GetBackgroundColour())
        self.myHistoryLabel.SetFont(self.unselFont)
        self.myHistoryLabel.SetToolTipString(self.utility.lang.get('myhistory_tool'))
        self.orderSizer.Add(self.myHistoryLabel, 0, wx.LEFT|wx.RIGHT, 10)
        
        self.recommLabel.Bind(wx.EVT_LEFT_UP, self.orderAction)
        self.swarmLabel.Bind(wx.EVT_LEFT_UP, self.orderAction)
        self.myHistoryLabel.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        
        
        self.lastOrdering = self.swarmLabel
        
        
        # Categories
        self.catSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.vSizer.Add(self.catSizer, 0, BORDER_EXPAND, 0)
        
        self.vSizer.Add(self.orderSizer, 0, BORDER_EXPAND, 0)
        # Label that show category header:
#        label2 =wx.StaticText(self,-1,self.utility.lang.get('categories')+': ')
#        label2.SetMinSize((100, -1))
#        self.catSizer.Add(label2, 0, wx.LEFT|wx.RIGHT, 10)
        
        
        for cat in self.categories:
            label = StaticText(self,-1,cat.title())
            label.SetBackgroundColour(self.GetBackgroundColour())
            label.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            label.SetFont(self.unselFont)
            self.catSizer.Add(label, 0, wx.LEFT|wx.RIGHT, 8)
            if cat.title() == 'Video':
                self.setSelected(label)
                self.lastSelected = label      
            
        
        self.SetSizer(self.vSizer);self.SetAutoLayout(1);self.Layout();
        self.Refresh()
        
    def orderAction(self, event):
        obj = event.GetEventObject()
        if obj == self.lastOrdering or self.myHistorySelected:
            return
        
        if obj == self.swarmLabel:
            self.parent.reorder('swarmsize')
            obj.SetFont(self.orderSelFont)
            
            
        elif obj == self.recommLabel:
            self.parent.reorder('relevance')
            obj.SetFont(self.orderSelFont)
                        
#        elif obj == self.myHistoryLabel:
#            self.parent.loadMyDownloadHistory()
#            obj.SetFont(self.selFont)
#            self.hideCategories(True)
#        
        
        if self.lastOrdering:
            self.lastOrdering.SetFont(self.orderUnselFont)
        self.lastOrdering = obj
        
    def mouseAction(self, event):
         
        obj = event.GetEventObject()
        #print 'Clicked on %s' % obj.GetLabel()
        if obj == self.lastSelected:
            return
        self.setSelected(obj)
        if self.lastSelected:
            self.setUnselected(self.lastSelected)
        self.parent.setCategory(obj.GetLabel())
        self.lastSelected = obj
        self.myHistorySelected = (obj == self.myHistoryLabel)
        self.deselectOrderings(self.myHistorySelected)
        
    def deselectOrderings(self, des):
        if des:
            self.lastOrdering.SetFont(self.orderUnselFont)
            
        else:
            self.lastOrdering.SetFont(self.orderSelFont)
            
    def setSelected(self, obj):
        obj.SetFont(self.selFont)
        self.orderSizer.Layout()
    
    def setUnselected(self, obj):
        obj.SetFont(self.unselFont)
        self.orderSizer.Layout()
        
class DetailPanel(wx.Panel):
    """
    This panel shows torrent details about the torrent that has been clicked in the
    torrent grid. Details contain: name,swarm, date, tracker, size, file info, 
    """
    def __init__(self, parent, utility):
        wx.Panel.__init__(self, parent, -1, style=wx.SIMPLE_BORDER)

        self.utility = utility
        self.parent = parent
        self.data = None
        self.oldSize = None
        self.addComponents()
        self.Centre()
        self.Show()

    def addComponents(self):
        self.Show(False)
        self.SetBackgroundColour(wx.WHITE)
        self.Bind(wx.EVT_SIZE, self.onResize)
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        # Set title
        self.title = StaticText(self,-1,"",wx.Point(3,111),wx.Size(49,13))
        font = self.title.GetFont()
        font.SetWeight(wx.BOLD)
        font.SetPointSize(font.GetPointSize()+3)
        self.title.SetFont(font)
        self.title.SetBackgroundColour(wx.Colour(245,208,120))
        self.vSizer.Add(self.title, 0, BORDER_EXPAND, 5)
        
        
        # Set download icons
        
        #downloadSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.downloadPic = ImagePanel(self)
        self.downloadPic.SetBitmap("download.png")
        self.downloadPic.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.downloadPic.SetBackgroundColour(wx.WHITE)
                
        #downloadSizer.Add(self.downloadPic, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER|wx.ALL, 10)
        #self.downloadText = StaticText(self, -1, self.utility.lang.get('download'))
        #self.downloadText.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        #self.downloadText.SetBackgroundColour(self.GetBackgroundColour())
        #downloadSizer.Add(self.downloadText, 0, wx.ALIGN_TOP|wx.ALL, 10)
        
#        refreshSizer.Add(self.refreshPic, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER, 1)
#        self.refreshText = StaticText(self, -1, self.utility.lang.get('refresh'))
#        self.refreshText.Bind(wx.EVT_LEFT_UP, self.mouseAction)
#        self.refreshText.SetBackgroundColour(self.GetBackgroundColour())
#        refreshSizer.Add(self.refreshText, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER, 1)
#        hIconSizer.Add(downloadSizer, 1, BORDER_EXPAND, 0)
#        hIconSizer.Add(refreshSizer, 1, BORDER_EXPAND, 0)
        
        self.vSizer.Add(self.downloadPic, 0, BORDER_EXPAND, 0)
        
        
        self.torrentDetailsPanel = wx.Panel(self, -1, style=wx.SIMPLE_BORDER)
        self.torrentDetailsPanel.utility = self.utility
        self.torrentDetailsPanel.SetBackgroundColour(wx.WHITE)
        torrentVSizer = wx.BoxSizer(wx.VERTICAL)
        
        # Swarm size
        swarmSizer = wx.BoxSizer(wx.HORIZONTAL)
        swarmLabel = wx.StaticText(self.torrentDetailsPanel, -1,self.utility.lang.get('swarm')+": ")
        self.swarmText = StaticText(self.torrentDetailsPanel, -1,"")
        self.swarmText.SetBackgroundColour(wx.WHITE)
        self.swarmText.Bind(wx.EVT_ENTER_WINDOW, self.updateLastCheck)
        swarmSizer.Add(swarmLabel, 1, BORDER_EXPAND, 0)
        swarmSizer.Add(self.swarmText, 0, wx.LEFT, 10)
        
        self.refreshButton = ImagePanel(self.torrentDetailsPanel)
        self.refreshButton.SetToolTipString(self.utility.lang.get('refresh_tool'))
        self.refreshButton.SetBackgroundColour(wx.WHITE)
        self.refreshButton.SetBitmap("refresh.png")
        self.refreshButton.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        swarmSizer.Add(self.refreshButton, 0, wx.TOP|wx.LEFT, 2)
        torrentVSizer.Add(swarmSizer, 1, BORDER_EXPAND, 1)
        # Last check
        checkSizer = wx.BoxSizer(wx.HORIZONTAL)
        checkLabel = wx.StaticText(self.torrentDetailsPanel, -1,self.utility.lang.get('created')+": ")
        self.checkText = wx.StaticText(self.torrentDetailsPanel, -1,"", style=wx.ALIGN_RIGHT)
        checkSizer.Add(checkLabel, 1, BORDER_EXPAND, 0)
        checkSizer.Add(self.checkText, 0, wx.LEFT, 10)
        torrentVSizer.Add(checkSizer, 1, BORDER_EXPAND, 1)
        # Tracker
        trackerSizer = wx.BoxSizer(wx.HORIZONTAL)
        trackerLabel = wx.StaticText(self.torrentDetailsPanel, -1,self.utility.lang.get('tracker')+": ")
        self.trackerText = StaticText(self.torrentDetailsPanel, -1,"", style=wx.ALIGN_RIGHT)
        self.trackerText.SetBackgroundColour(wx.WHITE)
        trackerSizer.Add(trackerLabel, 1, BORDER_EXPAND, 0)
        trackerSizer.Add(self.trackerText, 0, wx.LEFT, 10)
        torrentVSizer.Add(trackerSizer, 1, BORDER_EXPAND, 1)
        # Size
        sizeSizer = wx.BoxSizer(wx.HORIZONTAL)
        sizeLabel = wx.StaticText(self.torrentDetailsPanel, -1,self.utility.lang.get('size')+": ")
        self.sizeText = wx.StaticText(self.torrentDetailsPanel, -1,"", style=wx.ALIGN_RIGHT)
        sizeSizer.Add(sizeLabel, 1, BORDER_EXPAND, 0)
        sizeSizer.Add(self.sizeText, 0, wx.LEFT, 10)
        torrentVSizer.Add(sizeSizer, 1, BORDER_EXPAND, 1)
        
        # Recommendation
        recommSizer = wx.BoxSizer(wx.HORIZONTAL)
        recommLabel = wx.StaticText(self.torrentDetailsPanel, -1,self.utility.lang.get('recommendation')+": ")
        self.recommText = wx.StaticText(self.torrentDetailsPanel, -1,"", style=wx.ALIGN_RIGHT)
        recommSizer.Add(recommLabel, 1, BORDER_EXPAND, 0)
        recommSizer.Add(self.recommText, 0, wx.LEFT, 10)
        torrentVSizer.Add(recommSizer, 1, BORDER_EXPAND, 1)
        
        
        self.torrentDetailsPanel.SetSizer(torrentVSizer)
        
        self.vSizer.Add(self.torrentDetailsPanel, 0, BORDER_EXPAND, 1)
        
        self.fileList = wx.ListCtrl( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.LC_REPORT|wx.SUNKEN_BORDER|wx.LC_SINGLE_SEL )
        self.fileList.InsertColumn(0, self.utility.lang.get('file'))
        self.fileList.InsertColumn(1, self.utility.lang.get('size'))
        self.fileList.Bind(wx.EVT_SIZE, self.onListResize)
        self.fileList.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onListSelected)
        
        if sys.platform == 'win32':
            #print 'Using windows code'
            self.vSizer.Add(self.fileList, 1, BORDER_EXPAND, 1)
        else:
            #print 'Using unix code'
            self.fileListSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.fileListSizer.Add(self.fileList, 1, BORDER_EXPAND, 0)
            self.vSizer.Add(self.fileListSizer, 1, BORDER_EXPAND, 1)
        

        self.SetSizer(self.vSizer);self.SetAutoLayout(1);self.Layout();
        self.Refresh()
       
    
        
    def setData(self, torrent):
        
        #print 'DetailPanel.setData called by: %s' % threading.currentThread()
        # set bitmap, rating, title
        if torrent == None:
            torrent = {}
        
        self.data = torrent
        
        try:
            for key, value in torrent.items():
                if key == 'content_name':
                    self.title.SetLabel(self.breakup(value, self.title))
                    self.title.SetMinSize((100, 80))
                elif key == 'seeder':
                    if value > -1:
                        self.swarmText.SetLabel('%d %s%s + %d %s%s' % (value, self.utility.lang.get('seeder'), getPlural(value), torrent['leecher'], self.utility.lang.get('leecher'), getPlural(torrent['leecher'])))
                    else:
                        self.swarmText.SetLabel(self.utility.lang.get('no_info'))
                    self.swarmText.SetToolTipString('%s: %s' % (self.utility.lang.get('last_checked'), friendly_time(torrent.get('last_check_time'))))
                elif key == 'length':
                    self.sizeText.SetLabel(self.utility.size_format(value))
                elif key == 'info':
                    date = value.get('creation date')
                    if date:
                        self.checkText.SetLabel(friendly_time(date))
                elif key == 'tracker':
                    short = self.getShortTrackerFormat(value)
                    self.trackerText.SetLabel(short)
                    self.trackerText.SetToolTipString(value)
                elif key == 'torrent_name':
                    filelist = self.getFileList(torrent['torrent_dir'], value)
                    self.fileList.DeleteAllItems()
                    for f in filelist:
                        index = self.fileList.InsertStringItem(sys.maxint, f[0])
                        self.fileList.SetStringItem(index, 1, f[1])
                    self.onListResize(None) 
                elif key == 'relevance':
                    self.recommText.SetLabel("%.1f" % (value/1000.0))
                    
            if (torrent.get('myDownloadHistory', False) and not torrent.get('eventComingUp','') == 'notDownloading') or torrent.get('eventComingUp', '') == 'downloading':
                self.downloadPic.SetEnabled(False)
            else:
                self.downloadPic.SetEnabled(True)
                
            self.torrentDetailsPanel.GetSizer().Layout()
            self.vSizer.Layout()
        except:
            print >>sys.stderr,'contentpanel: Could not set data in detailPanel'
            print_exc(file=sys.stderr)
            print >>sys.stderr,"contentpanel: data to set was",self.data
            
    def getFileList(self, torrent_dir, torrent_file):
        # Get the file(s)data for this torrent
        try:
            
            if not os.path.exists(torrent_dir):
                torrent_dir = os.path.join(self.utility.getConfigPath(), "torrent2")
            
            torrent_filename = os.path.join(torrent_dir, torrent_file)
            
            if not os.path.exists(torrent_filename):
                if DEBUG:    
                    print >>sys.stderr,"contentpanel: Torrent: %s does not exist" % torrent_filename
                return {}
            
            metadata = self.utility.getMetainfo(torrent_filename)
            if not metadata:
                return {}
            info = metadata.get('info')
            if not info:
                return {}
            
            #print metadata.get('comment', 'no comment')
                
                
            filedata = info.get('files')
            if not filedata:
                filelist = [(dunno2unicode(info.get('name')),self.utility.size_format(info.get('length')))]
            else:
                filelist = []
                for f in filedata:
                    filelist.append((dunno2unicode('/'.join(f.get('path'))), self.utility.size_format(f.get('length')) ))
                filelist.sort()
                
            
            return filelist
        except:
            print_exc(file=sys.stderr)
            return {}                   
         
    def updateLastCheck(self, event=None):
        if self.data:
            last_time = self.data.get('last_check_time')
            if last_time and type(last_time) == int:
                self.swarmText.SetToolTipString('%s: %s' % (self.utility.lang.get('last_checked'), friendly_time(last_time)))
        event.Skip()
        
    def getShortTrackerFormat(self, n):
        i1 = n.find(':', 8)
        i2 = n.find('/', 8)
        if i1 != -1 and (i1 < i2 or i2 == -1):
            return n[:i1]
        elif i2 != -1:
            return n[:i2]
        else:
            return n
    
    def showsTorrent(self, torrent):
        return self.data != None and self.data.get('infohash', 'no_infohash') == torrent.get('infohash')
        
    def onListResize(self, event):
        size = self.fileList.GetClientSize()
        if size[0] > 50 and size[1] > 50:
            self.fileList.SetColumnWidth(1, wx.LIST_AUTOSIZE)
            self.fileList.SetColumnWidth(0, self.fileList.GetClientSize()[0]-self.fileList.GetColumnWidth(1)-15)
            self.fileList.ScrollList(-100, 0) # Removes HSCROLLBAR
        if event:
            event.Skip()
                   
    def onListSelected(self, event):
        item = event.GetItem()
        if DEBUG:
            print >>sys.stderr,"contentpanel: onListSelected",item
            print >>sys.stderr,"contentpanel: onListSelected",item.GetState()
        item.SetState(wx.LIST_STATE_SELECTED)
    
    def breakup(self, str, ctrl, depth=0):
        if depth > 10:
            return str
        
        charWidth = ctrl.GetTextExtent(str)[0]/len(str)
        begin = self.GetSize()[0] / charWidth - 5 # first part of the string where we break it
        #print 'There should fit %d chars'% begin
        
        if len(str)<=max(begin, 5) or '\n' in str[:begin+1]:
            return str
        
        for char in [' ', '.','_','[',']','(', '-', ',']:
            i = str.find(char, begin -10)
            if i>0 and i<=begin:
                return str[:i]+'\n'+self.breakup(str[i:], ctrl, depth+1)
        
        return str[:begin]+'\n'+self.breakup(str[begin:], ctrl, depth+1)
            
    def mouseAction(self, event):
        obj = event.GetEventObject()
        if not self.data:
            return
        if obj == self.downloadPic:
            self.parent.download(self.data)
        elif obj == self.refreshButton and self.refreshButton.isEnabled():
            self.swarmText.SetLabel(self.utility.lang.get('refreshing')+'...')
            self.swarmText.Refresh()
            
            self.parent.refresh(self.data)
        #print "Clicked"
    
    def onResize(self, event):
        # redo set data for new breakup
        event.Skip(True)
        if self.oldSize and (event.GetSize()[0] == self.oldSize[0]):
            return
        if not self.data:
            return
        self.oldSize = event.GetSize()
        value = self.data.get('content_name', '')
        self.title.SetLabel(self.breakup(value, self.title))
        self.title.SetMinSize((100, 80))
        
            
class ImagePanel(wx.Panel):
    def __init__(self, parent, size=None):
        wx.Panel.__init__(self, parent, -1)
        self.size = size
        self.utility = parent.utility
        self.bitmap = None  # wxPython image
        self.enabled = True
        wx.EVT_PAINT(self, self.OnPaint)
        self.path = None
        self.Show()

    def SetEnabled(self, e):
        if e != self.enabled:
            self.enabled = e
            if not self.enabled:
                self.SetMinSize((0,0))
            else:
                if self.bitmap:
                    self.SetMinSize(self.bitmap.GetSize())
                else:
                    self.SetMinSize((0,0))

            self.Refresh(True)
            
    def isEnabled(self):
        return self.enabled
    
    def SetBitmap(self, filename):
        
        path = os.path.join(self.utility.getPath(), 'icons', filename)
        
        if self.path == path:
            return
        else:
            self.path = path
        
        if not os.path.exists(path):
            if DEBUG:
                print >>sys.stderr,'contentpanel: Image file: %s does not exist' % path
            self.bitmap = None
            return
            
        bm = wx.Bitmap(path,wx.BITMAP_TYPE_ANY)
        
        if self.size != None and bm != None:
            
            image = wx.ImageFromBitmap(bm)
            image.Rescape(self.size[0], self.size[1])
            bm = image.ConvertToBitmap()
        
        self.bitmap = bm
        if self.bitmap:
            self.SetMinSize(self.bitmap.GetSize())
        else:
            self.SetMinSize((0,0))

        
        #self.Refresh() # Do not refresh before panel is shown and inited
        
    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        if self.bitmap and self.enabled:
            dc.DrawBitmap(self.bitmap, 0,0, True)
   
class ContentFrontPanel(wx.Panel, DelayedInvocation):
    """
    Combines a GridPanel, CategoryPanel and DetailPanel
    """
    def __init__(self, parent):
        
        self.utility = parent.utility
        self.imagepath = os.path.join(self.utility.getPath(), 'icons')+'/'
        #print self.imagepath
        wx.Panel.__init__(self, parent, -1)
        self.type = 'swarmsize'
        DelayedInvocation.__init__(self)
        self.doneflag = threading.Event()
        self.oldCategory = None
        self.neverAnyContent = True
        
        self.categorykey = 'video'  # start showing video files
        self.data_manager = TorrentDataManager.getInstance(self.utility)
        self.mypref_db = self.utility.mypref_db
        #self.torrent_db = self.utility.torrent_db
        self.addComponents()
        
        self.reloadData()

    
    def addComponents(self):
        self.SetBackgroundColour(wx.WHITE)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        gridColumns = 2
        
        self.detailPanel = DetailPanel(self, self.utility)
        self.grid = GridPanel(self, gridColumns)
        categories = self.data_manager.category.getCategoryKeys()
        ourCategories = ['Video', 'VideoClips', 'Audio', 'Picture', 'Compressed', 'Document', 'other', 'xxx']
        #double check our categories
        for cat in ourCategories:
            if cat not in categories:
                ourCategories.remove(cat)
        self.categoryPanel = CategoryPanel(self, ourCategories, self.utility.lang.get('mypref_list_title'))
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.categoryPanel, 0, BORDER_EXPAND, 1)
        vSizer.Add(self.grid, 1, BORDER_EXPAND, 1)
        
        self.hSizer.Add(vSizer, 3, BORDER_EXPAND, 1)
        self.hSizer.Add(self.detailPanel, 1, BORDER_EXPAND, 1)
        
        self.SetSizer(self.hSizer);self.SetAutoLayout(1);self.Layout();
        self.Refresh()
        
        
    def reorder(self, type):
        self.type = type
        self.reloadData()
    
    def addData(self, torrent):
        "When a new torrent is discovered, the grid is not directly reordered. The new torrent is added at the end of the gridlist"
        
        i = find_content_in_dictlist(self.grid.data, torrent)
        if i != -1:
            self.grid.data[i] = torrent
            self.grid.setData(self.grid.data, False)
            self.neverAnyContent = False
        else:
            if torrent.get('status') == 'good' or torrent.get('myDownloadHistory'):
                
                # Check if we have to remove the dummy content
                if len(self.grid.data) == 1 and self.grid.data[0].get('content_name') == self.utility.lang.get('searching_content'):
                    del self.grid.data[0]
                    self.detailPanel.setData(torrent)
                    self.neverAnyContent = False
                    if DEBUG:
                        print >>sys.stderr,'contentpanel: Removing dummy content'
                
                # Only add healthy torrents to grid
                self.grid.data.append(torrent)
                if DEBUG:
                    print >>sys.stderr,"contentpanel: Added torrent %s, because status was %s" % (repr(torrent['content_name']), torrent['status'])
    
                self.grid.setData(self.grid.data, False)
            else:
                if DEBUG:
                    print >>sys.stderr,"contentpanel: Did not add torrent %s, because status was %s (myDLHist: %s)" % (repr(torrent['content_name']), torrent['status'], torrent.get('myDownloadHistory', 'noMyDownloadHistory'))
                pass
    
    def deleteData(self, torrent):
        
        remove_torrent_from_list(self.grid.data, torrent)
        self.grid.setData(self.grid.data, False)
        
        
    def reloadData(self):
        
        if self.oldCategory:
            self.data_manager.unregister(self.updateFun, self.oldCategory)
        
        if False: #self.categorykey == self.utility.lang.get('mypref_list_title'):
            # load download history
            self.loadMyDownloadHistory()
        else:
            # load content category
            self.data_manager.register(self.updateFun, self.categorykey)
            self.data = self.data_manager.getCategory(self.categorykey)
            self.filtered = []
            for torrent in self.data:
                if torrent.get('status') == 'good' or torrent.get('myDownloadHistory'):
                    self.filtered.append(torrent)
        
            self.filtered = sort_dictlist(self.filtered, self.type, 'decrease')
            if self.filtered:
                self.neverAnyContent = False
            elif self.neverAnyContent:
                searchingContentStub = {'content_name':self.utility.lang.get('searching_content')}
                self.filtered.append(searchingContentStub)
            self.grid.setData(self.filtered)
            self.oldCategory = self.categorykey
        
    def setCategory(self, cat):
        self.categorykey = cat
        self.reloadData()
        
    def download(self, torrent):
        src1 = os.path.join(torrent['torrent_dir'], 
                            torrent['torrent_name'])
        src2 = os.path.join(self.utility.getConfigPath(), 'torrent2', torrent['torrent_name'])
        if torrent['content_name']:
            name = torrent['content_name']
        else:
            name = showInfoHash(torrent['infohash'])
        #start_download = self.utility.lang.get('start_downloading')
        #str = name + "?"
        if os.path.isfile(src1):
            src = src1
        else:
            src = src2
            
        if os.path.isfile(src):
            ret = self.utility.queue.addtorrents.AddTorrentFromFile(src)
            if ret == 'OK':
                self.setRecommendedToMyDownloadHistory(torrent)
        else:
        
            # Torrent not found            
            str = self.utility.lang.get('delete_torrent') % name
            dlg = wx.MessageDialog(self, str, self.utility.lang.get('delete_dead_torrent'), 
                                wx.YES_NO|wx.NO_DEFAULT|wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                infohash = torrent['infohash']
                self.data_manager.deleteTorrent(infohash, delete_file = True)
        
    def refresh(self, torrent):
        if DEBUG:
            print >>sys.stderr,'contentpanel: refresh ' + repr(torrent.get('content_name', 'no_name'))
        check = SingleManualChecking(torrent)
        check.start()
        
    def deleteTorrent(self, torrent):
        "User wants to delete torrent from browsed content of download history"
        
        infohash = torrent.get('infohash')
        result = None
        if DEBUG:
            print >>sys.stderr,'contentpanel: deleting %s' % torrent
        if not torrent.has_key('myDownloadHistory'):
            # delete in browsed content
            str = self.utility.lang.get('delete_sure') % torrent.get('content_name','')+'?'
            dlg = wx.MessageDialog(self, str, self.utility.lang.get('delete'), 
                                        wx.YES_NO|wx.NO_DEFAULT|wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                self.data_manager.deleteTorrent(infohash, True)
        else: 
            # we are deleting a torrent from "my download history"
            str = self.utility.lang.get('delete_mypref_sure') % torrent.get('content_name','')+'?'
            dlg = wx.MessageDialog(self, str, self.utility.lang.get('delete') , 
                                        wx.YES_NO|wx.NO_DEFAULT|wx.ICON_INFORMATION)
            result = dlg.ShowModal(    )
            dlg.Destroy()
            if result == wx.ID_YES:       
                self.setMyDownloadHistoryToRecommended(torrent)
        
    def setRecommendedToMyDownloadHistory(self, torrent):
        infohash = torrent['infohash']
        self.data_manager.setBelongsToMyDowloadHistory(infohash, True)
        
        
    def setMyDownloadHistoryToRecommended(self, torrent):
        infohash = torrent['infohash']
        self.mypref_db.deletePreference(infohash)
        self.mypref_db.sync()
        self.data_manager.setBelongsToMyDowloadHistory(infohash, False)
        self.refresh(torrent)
                        
    def __del__(self):
        if self.categorykey != self.utility.lang.get('mypref_list_title'):
            self.data_manager.unregister(self.updateFun, self.categorykey)
        
    def updateFun(self, torrent, operate):
        if DEBUG:
            print 'contentpanel: Updatefun called: %s %s (s: %d, l: %d) '% (repr(torrent.get('content_name','no_name')), operate, torrent.get('seeder', -1), torrent.get('leecher', -1))
        # operate = {add, update, delete}
        if operate in ['update', 'delete']:
            if self.detailPanel.showsTorrent(torrent):
                self.invokeLater(self.detailPanel.setData, [torrent])
        
        if operate in ['update', 'add']:
            self.invokeLater(self.addData, [torrent])
        else:
            self.invokeLater(self.deleteData, [torrent])
            
    def keyTyped(self, event):
        if DEBUG:
            print >>sys.stderr,'contentpanel: typed'
        pass
        

