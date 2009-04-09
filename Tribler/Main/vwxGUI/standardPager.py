from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from wx.lib.stattext import GenStaticText as StaticText
from font import *

import wx, os, sys, os.path, math

DEBUG = True

# font sizes
if sys.platform == 'darwin':
    FS_ITEMNORMAL = 11
    FS_ITEMBOLD = 13
else:
    FS_ITEMNORMAL = 8
    FS_ITEMBOLD = 10

class standardPager(wx.Panel):
    """
    Panel with automatic backgroundimage control.
    """
    def __init__(self, *args):
        if len(args) == 0:
            self.initReady = False
            pre = wx.PrePanel()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Panel.__init__(self, args[0], args[1], args[2], args[3])
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        self.initPager()
        self.Refresh(True)
        self.Update()
        
        
        
    def initPager(self, numPages=10):
        
       
        self.beginPage = 0
        self.currentPage = 0
        self.left = None
        self.right = None
        self.numPages = numPages
        self.totalPages = 0
        self.totalItems = 0
        self.itemsPerPage = 0
        self.currentDots = [None, None]
        self.pagerColour = wx.Colour(230,230,230)

        self.pageNumbers = []
        self.utility = self.guiUtility.utility
        self.addComponents()
        self.initReady = True
        self.refresh()
   
    def addComponents(self):
        self.Show(False)
        self.SetBackgroundColour(self.pagerColour)
        self.normalFont = wx.Font(FS_ITEMNORMAL,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE) # was Arial
        self.boldFont  = wx.Font(FS_ITEMNORMAL,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE) # was Arial
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        #self.number = wx.StaticText(self,-1,"",wx.Point(3,111),wx.Size(49,13))
        #self.number.SetLabel('0 %s' % self.utility.lang.get('item')+'s')
        #self.number.SetFont(self.normalFont)
        #self.hSizer.Add(self.number, 3, wx.ALL, 0)
        
        # left arrows
#        self.leftPages = ImagePanel(self)
#        self.leftPages.SetBitmap(wx.Bitmap("prev2.gif",wx.BITMAP_TYPE_GIF))
#        self.hSizer.Add(self.leftPages, 0, BORDER_EXPAND, 0)
        self.left = SwitchButton(self, name='prevpage')
        self.left.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        ##self.left.setBackground(self.guiUtility.triblerRed)
        #self.hSizer.AddSpacer(wx.Size(25))
        self.hSizer.Add(self.left, 0, wx.TOP, 0)
        
        #page numbers
        self.refreshPageNumbers()
        
        
        self.right = SwitchButton(self, name='nextpage')
        self.right.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        ##self.right.setBackground(self.guiUtility.triblerRed)
        self.hSizer.AddSpacer(wx.Size(20))
        self.hSizer.AddSpacer(wx.Size(20))
        self.hSizer.Add(self.right, 0, wx.TOP, 0)
       
        
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1)
        self.Layout()
        self.Refresh()
        self.Show()
        
        
   
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
        if self.hasGrid():
            self.grid.gridManager.set_page(self.currentPage)
        
        
    def setPageNumbers(self, begin, number, current, leftDots, rightDots):
        """
        Put the right numbers in the pagefield. If necessary, create new statictexts.
        Highlight current page number
        """
        
        #print 'Pagenumbers: Begin %d, number %d, current %d' % (begin, number, current)
        
        refresh = False
        # Guarantee right amount of statictexts
        currentPageNumber = len(self.pageNumbers)
        if number > currentPageNumber:
            while (len(self.pageNumbers) < number):
                text = self.getDefaultTextField()
                text.Bind(wx.EVT_LEFT_UP, self.mouseAction)
                self.pageNumbers.append(text)
                self.hSizer.Insert(len(self.pageNumbers)+1, text, 0, wx.TOP|wx.LEFT|wx.RIGHT, 2)

            refresh = True
        elif number < currentPageNumber:
            for i in range(number, currentPageNumber):
                self.hSizer.Detach(self.pageNumbers[i])
                self.pageNumbers[i].Destroy()
                #self.pageNumbers[i].Show(False)
            self.pageNumbers = self.pageNumbers[:number]
            refresh = True
          
        # Manage dots before and after page numbers
        #if rightDots and not self.currentDots[1]:
        #    dots = self.getDefaultTextField('...')
        #    extra =  int(bool(self.currentDots[0]))
            
        #    self.hSizer.Insert(len(self.pageNumbers)+2+extra, dots, 0, wx.LEFT|wx.RIGHT, 2)
        #    self.currentDots[1] = dots
        #    refresh = True
        
        #if not rightDots and self.currentDots[1]:
        #    self.hSizer.Detach(self.currentDots[1])
        #    self.currentDots[1].Destroy()
        #    self.currentDots[1] = None
        #    refresh = True
        
        #if leftDots and not self.currentDots[0]:
        #    dots = self.getDefaultTextField('...')
            
        #    self.hSizer.Insert(2, dots, 0, wx.LEFT|wx.RIGHT, 2)
        #    self.currentDots[0] = dots
        #    refresh = True
        
        #if not leftDots and self.currentDots[0]:
        #    self.hSizer.Detach(self.currentDots[0])
        #    self.currentDots[0].Destroy()
        #    self.currentDots[0] = None
        #    refresh = True
            
            
        #print '%d statictexts' % (len(self.pageNumbers))
        # Put right numbers in statictexts
        page = begin
        for panel in self.pageNumbers:
            panel.SetLabel(' ' + str(page+1) + ' ')
            if page == current:
                
                panel.SetFont(self.boldFont)
                panel.SetForegroundColour(wx.WHITE) ## 0,110,149
                panel.SetBackgroundColour((0,110,149))

            else:
                panel.SetFont(self.normalFont)
                panel.SetForegroundColour((255,51,0))
                panel.SetBackgroundColour(self.pagerColour)

            page+=1

        if refresh:
            self.hSizer.Layout()
            self.Refresh()
            self.Show(True)

        if self.right is not None:
            self.right.setToggled(self.currentPage != (self.totalPages - 1))
        if self.left is not None:
            self.left.setToggled(self.currentPage != 0)

        
        
        
        
    def getDefaultTextField(self, t=""):
        text = StaticText(self, -1, t)
        text.SetForegroundColour((255,51,0))
        text.SetBackgroundColour(self.pagerColour)
        return text




    
    def refresh(self):
        "Called by Grid if size or data changes"
        
        if not self.hasGrid() or not self.initReady:
            if DEBUG:
                print >>sys.stderr,'standardPager: no refresh, not ready yet or no grid'
            return
        
                
        grid = self.grid
        try:
            self.totalItems = grid.gridManager.get_total_items()
            self.itemsPerPage = grid.items
        except:
            self.totalItems = 0
            self.itemsPerPage = 0
        
        
        # if dummy item "Searching for content is shown, do not count it as content
        if self.totalItems == 1 and len(grid.data) > 0 and grid.data[0].get('content_name','no_name') == self.utility.lang.get('searching_content'):
            self.totalItems = 0
        
        
        if self.itemsPerPage == 0:
            self.totalPages = 0
        else:
            self.totalPages = int(math.ceil(self.totalItems/float(self.itemsPerPage)))

        #self.number.SetLabel('%d %s%s / %d %s%s' % (self.totalItems, self.utility.lang.get('item'), getPlural(self.totalItems), self.totalPages, self.utility.lang.get('page'), getPlural(self.totalPages)))
        
        if self.currentPage >= self.totalPages:
            self.currentPage = max(self.totalPages -1, 0)
        self.refreshPageNumbers()
        
#    def imageClicked(self, event):
#        obj = event.GetEventObject()
#        self.mouseAction(obj, event)
#        
    def mouseAction(self, event):
        if DEBUG:
            print >>sys.stderr,'standardPager: mouseaction'
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
        
    def hasGrid(self):
        try:
            if self.grid:
                #print 'pager has grid'
                return True
        except:
            #print 'pager has no grid'
            return False
        
    def setGrid(self, grid):
        #print 'setGrid called: %s' % grid
        self.grid = grid
        if grid:
            self.grid.setPager(self)
      
