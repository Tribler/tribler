import wx, sys
from Tribler.vwxGUI.bgPanel import ImagePanel
from Tribler.vwxGUI.GuiUtility import GUIUtility

class ColumnHeader(wx.Panel):
    
    bitmapOrderUp = 'upSort'
    bitmapOrderDown = 'downSort'
    
    def __init__(self, parent, title, picture, order, tip, sorting, reverse, colours):
        wx.Panel.__init__(self, parent, -1)
        self.type = None
        self.selectedColour = colours[0]
        self.unselectedColour = colours[1]
        self.addComponents(title, picture, tip)
        self.setOrdering(order)
        self.sorting = sorting
        if reverse:
            self.reverse = True
        else:
            self.reverse = False
        
        
        
    def addComponents(self, title, picture, tip):
        self.SetBackgroundColour(self.unselectedColour)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.text = None
        self.icon = None
        
        if picture:
            self.icon = ImagePanel(self)
            self.icon.setBitmapFromFile(picture)
            self.icon.setBackground(self.unselectedColour)
            self.hSizer.Add(self.icon, 0, wx.TOP,1 )
        if title:
            if not picture:
                self.hSizer.Add([15,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
            self.text = wx.StaticText(self, -1, title)
            self.hSizer.Add(self.text, 1, wx.TOP, 3)            
        
        self.dummy = not picture and not title
        if picture == None and title == None:
            raise Exception('No text nor an icon in columnheader')
        
        self.sortIcon = ImagePanel(self)
        self.sortIcon.setBackground(self.unselectedColour)
        self.sortIcon.Hide()
        self.hSizer.Add(self.sortIcon, 0, wx.TOP, 1)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(True)
        self.hSizer.Layout()
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

        # 2.8.4.2 return value of GetChildren changed
        wl = [self]
        for c in self.GetChildren():
            wl.append(c)
        for element in wl:
            element.Bind(wx.EVT_LEFT_UP, self.clicked)
            element.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
            element.SetToolTipString(tip)
        
    def setText(self, t):
        self.text.SetLabel(t)
        
    def setOrdering(self, type):
        # up, down or none
        #print 'Set ordering to %s' % type
        self.type = type
        if type == 'up':
            self.sortIcon.setBitmapFromFile(self.bitmapOrderUp)
            self.setColour(self.selectedColour)
            if not self.sortIcon.IsShown():
                self.sortIcon.Show()
        elif type == 'down':
            self.sortIcon.setBitmapFromFile(self.bitmapOrderDown)
            self.setColour(self.selectedColour)
            if not self.sortIcon.IsShown():
                self.sortIcon.Show()
        else:
            self.sortIcon.setBitmapFromFile(self.bitmapOrderDown)
            self.sortIcon.Hide()
            self.setColour(self.unselectedColour)
        self.GetSizer().Layout()
    
    def clicked(self, event):
        if self.dummy:
            return
        if not self.type or self.type == 'up':
            newType = 'down'
        elif self.type == 'down':
            newType = 'up'
        self.setOrdering(newType)
        self.GetParent().setOrdering(self, newType)
        
        
        
    def mouseAction(self, event):
        event.Skip()
        if self.type:
            return
        colour = None
        if event.Entering():
            colour = self.selectedColour

        elif event.Leaving():
            if sys.platform == 'win32':
                position = event.GetPosition()
                for i in xrange(2):
                    position[i]+=event.GetEventObject().GetPosition()[i]
                    position[i]-=self.GetPosition()[i]
                size = self.GetSize()

                if position[0]<0 or position[0]>=size[0] or position[1]<0 or position[1]>=size[1]:
                    colour = self.unselectedColour
            else:
                colour = self.unselectedColour
        if colour:
            self.setColour(colour)
            
        
    def setColour(self, colour):
        for element in [self, self.icon, self.sortIcon, self.text]:
            if element:
                if element.__class__ == ImagePanel:
                    element.setBackground(colour)
                element.SetBackgroundColour(colour)
        self.Refresh()
                
class ColumnHeaderBar(wx.Panel):
    
    
    def __init__(self, parent, itemPanel):
        self.itemPanel = itemPanel
        wx.Panel.__init__(self, parent, -1)
        self.columns = []
        self.guiUtility = GUIUtility.getInstance()
        self.addComponents()
        #self.SetMinSize((-1,30))
        self.Show(True)
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        #self.hSizer.Add([0,20],0,wx.FIXED_MINSIZE,0)
        columns = self.itemPanel.getColumns()
        currentSorting = self.guiUtility.standardOverview.getSorting()
        #print 'currentSorting: %s' % str(currentSorting)
        for dict in columns:
            colours = (wx.Colour(203,203,203), wx.Colour(223,223,223))
            if (type(currentSorting) == str and currentSorting == dict['sort'] or
                type(currentSorting) == tuple and currentSorting[0] == dict['sort']):
                if (len(currentSorting) == 2 and currentSorting[1] == 'increase') ^ dict.get('reverse', False):
                    beginorder = 'up'
                else:
                    beginorder = 'down'
            else:
                beginorder = None
            header = ColumnHeader(self, dict.get('title'), dict.get('pic'), beginorder, dict['tip'], dict['sort'], dict.get('reverse'), colours)
            

            self.hSizer.Add(header, dict.get('weight',0), wx.EXPAND|wx.BOTTOM, 0)

            self.columns.append(header)
            if columns.index(dict) != len(columns)-1:
                line = wx.StaticLine(self,-1,wx.DefaultPosition, wx.DefaultSize, wx.LI_VERTICAL)
                self.SetBackgroundColour(colours[0])
                self.hSizer.Add(line, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 0)
                if dict.get('width'):
                    header.SetSize((dict['width']+6, -1))
                    header.SetMinSize((dict['width']+6, -1))
            else:
                if dict.get('width'):
                    header.SetSize((dict['width']+3, -1))
                    header.SetMinSize((dict['width']+3, -1))
        
        #self.SetBackgroundColour(wx.Colour(100,100,100))
        self.hSizer.Layout()
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(True)
        
    def setOrdering(self, column, ordering):
        for header in self.columns:
            if header != column:
                header.setOrdering(None)
        if ordering == 'up' and not column.reverse or ordering == 'down' and column.reverse:
            self.sorting = (column.sorting, 'increase')
        else:
            self.sorting = (column.sorting, 'decrease')
        self.guiUtility.standardOverview.filterChanged([None, self.sorting])
        
    def getSorting(self):
        return self.sorting
    
    
     
