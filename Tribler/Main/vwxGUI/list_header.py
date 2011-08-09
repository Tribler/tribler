# Written by Niels Zeilemaker
from Tribler.Main.vwxGUI.tribler_topButton import LinkStaticText, ImageScrollablePanel,\
    NativeIcon
from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

from __init__ import LIST_RADIUS
import sys
import wx
import os

class ListHeaderIcon:
    __single = None
    def __init__(self):
        if ListHeaderIcon.__single:
            raise RuntimeError, "ListHeaderIcon is singleton"
        ListHeaderIcon.__single = self
        self.icons = {}
        
    def getInstance(*args, **kw):
        if ListHeaderIcon.__single is None:
            ListHeaderIcon(*args, **kw)
        return ListHeaderIcon.__single
    getInstance = staticmethod(getInstance)
    
    def getBitmaps(self, parent, background):
        assert isinstance(background, wx.Colour), "we require a wx.colour object here"
        if not isinstance(background, wx.Colour):
            background = wx.Brush(background).GetColour()
        
        key = background.Get()
        if key not in self.icons:
            self.icons[key] = self.__createBitmap(parent, background, 'arrow')
        return self.icons[key]
    
    def __createBitmap(self, parent, background, type, flag=0):
        print >> sys.stderr, "Creating new sorting bitmaps", parent, background, type
        nativeIcon = NativeIcon.getInstance()
        down = nativeIcon.getBitmap(parent, type, background, flag)
        
        img = down.ConvertToImage()
        up = img.Rotate90().Rotate90().ConvertToBitmap()
        
        empty = wx.EmptyBitmap(up.GetWidth(), up.GetHeight())
        dc = wx.MemoryDC(empty)
        dc.SetBackground(wx.Brush(background))
        dc.Clear()
        dc.SelectObject(wx.NullBitmap)
        del dc
        
        return [down, up, empty]

class ListHeader(wx.Panel):
    def __init__(self, parent, parent_list, columns, radius = LIST_RADIUS):
        wx.Panel.__init__(self, parent)
        self.parent_list = parent_list
        self.columnHeaders = []
        
        self.columns = columns
        self.radius = radius

        self.sortedColumn = -1
        self.defaultSort = -1
        self.sortedDirection = False
        
        self.scrollBar = None

        self.AddComponents(columns)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnResize)

    def AddComponents(self, columns):
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        if self.radius > 0:
            hSizer.AddSpacer((self.radius,10))
            
        self.AddColumns(hSizer, self, columns)
        
        if self.radius > 0:
            hSizer.AddSpacer((self.radius,10))
        
        self.SetSizer(hSizer)
        
    def AddColumns(self, sizer, parent, columns):
        self.columnHeaders = []
        
        if len(columns) > 0:
            down, _, empty = ListHeaderIcon.getInstance().getBitmaps(self, self.GetBackgroundColour())
            for i in xrange(len(columns)):
                if columns[i].get('name', '') != '':
                    label = wx.StaticText(parent, i, columns[i]['name'], style = columns[i].get('style',0)|wx.ST_NO_AUTORESIZE)
                    label.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                    label.SetToolTipString('Click to sort table by %s.'%columns[i]['name'])
                    label.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                    sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.TOP|wx.BOTTOM, 3)
                
                    if columns[i].get('defaultSorted', False):
                        label.sortIcon = wx.StaticBitmap(self, -1, down)
                        self.sortedColumn = i
                        self.defaultSort = i
                    else:
                        label.sortIcon = wx.StaticBitmap(self, -1, empty)
                    sizer.Add(label.sortIcon, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
                
                    if columns[i]['width'] == wx.LIST_AUTOSIZE_USEHEADER:
                        columns[i]['width'] = label.GetBestSize()[0] + down.GetWidth()
                    
                    elif columns[i]['width'] == wx.LIST_AUTOSIZE:
                        sizer.AddStretchSpacer()

                    else:
                        if isinstance(columns[i]['width'], basestring) and columns[i]['width'].endswith('em'):
                            test_string = 'T' * int(columns[i]['width'][:-2])
                            columns[i]['width'] = self.GetTextExtent(test_string)[0] + 6
                        
                    self.columnHeaders.append(label)
                else:
                    spacer = sizer.Add((columns[i]['width'], -1), 0, wx.LEFT|wx.RIGHT, 3)
                    self.columnHeaders.append(spacer)
        
        self.scrollBar = sizer.AddSpacer((0,0))
        self.scrollBar.Show(False)
        self.scrollBar.sizer = sizer
    
    def ResizeColumn(self, column, width):
        item = self.columnHeaders[column]
        if item.GetSize()[0] != width:
            if getattr(item, 'SetSize', None):
                item.SetSize((width, -1))
            else:
                item.SetSpacer((width, -1))
            
            if self.scrollBar:
                self.scrollBar.sizer.Layout()

    def SetSpacerRight(self, right):
        if self.scrollBar:
            if right > 0:
                dirty = False
                if self.scrollBar.GetSize()[0] != right:
                    self.scrollBar.SetSpacer((right, 0))
                    dirty = True
                if not self.scrollBar.IsShown():
                    self.scrollBar.Show(True)
                    dirty = True
                
                if dirty:
                    self.scrollBar.sizer.Layout()
            else:
                if self.scrollBar.IsShown():
                    self.scrollBar.Show(False)
                    self.scrollBar.sizer.Layout()
    
    def OnMouse(self, event):
        if event.Entering() or event.Moving():
            label = event.GetEventObject()
            if not getattr(label, 'selected', False):
                font = label.GetFont()
                
                #Niels: Underline not working on Linux, using italic instead
                if sys.platform == 'linux2': 
                    font.SetStyle(wx.ITALIC)
                else:
                    font.SetUnderlined(True)
                label.SetFont(font)
                
                label.selected = True
                
                for column in self.columnHeaders:
                    if column != label and isinstance(column, wx.StaticText):
                        column.selected = False
                        font = column.GetFont()
                        if sys.platform == 'linux2':
                            font.SetStyle(wx.NORMAL)
                        else:
                            font.SetUnderlined(False)
                        column.SetFont(font)
                
        elif event.Leaving():
            label = event.GetEventObject()
            if getattr(label, 'selected', False):
                font = label.GetFont()
                
                if sys.platform == 'linux2':
                    font.SetStyle(wx.NORMAL)
                else:
                    font.SetUnderlined(False)
                label.SetFont(font)
                
                label.selected = False
        
        elif event.LeftUp():
            self.OnClick(event)
            
        event.Skip() #Allow for windows button hovering
    
    def OnClick(self, event):
        newColumn = event.Id
        
        if event.Id == self.sortedColumn:
            newDirection = not self.sortedDirection
            
            if newDirection == self.columns[newColumn].get('sortAsc', False): #back to default, treat as off
                newColumn = -1
        else:
            newDirection = self.columns[newColumn].get('sortAsc', False)
        
        self.parent_list.OnSort(newColumn, newDirection)
        self._SetSortedIcon(newColumn, newDirection)
    
    def ShowSortedBy(self, column):
        direction = self.columns[column].get('sortAsc', False)
        self._SetSortedIcon(column, direction)
    
    def _SetSortedIcon(self, newColumn, newDirection):
        down, up, empty = ListHeaderIcon.getInstance().getBitmaps(self, self.GetBackgroundColour())
        
        if self.sortedColumn != -1 and newColumn != self.sortedColumn:
            prevSort = self.columnHeaders[self.sortedColumn].sortIcon
            prevSort.SetBitmap(empty)
            prevSort.Refresh()
        
        if newColumn != -1:
            newSort = self.columnHeaders[newColumn].sortIcon
            if newDirection: 
                newSort.SetBitmap(up)
            else:
                newSort.SetBitmap(down)
            newSort.Refresh()
        
        self.sortedColumn = newColumn
        self.sortedDirection = newDirection
        
    def Reset(self):
        if self.defaultSort != -1:
            defaultDirection = self.columns[self.defaultSort].get('sortAsc', False)
        else:
            defaultDirection = False
        self._SetSortedIcon(self.defaultSort, defaultDirection)
    
    def SetBackgroundColour(self, colour):
        self.backgroundBrush = wx.Brush(colour)
        colour = self.backgroundBrush.GetColour()
        
        down, up, empty = ListHeaderIcon.getInstance().getBitmaps(self, colour)
        for i in range(len(self.columnHeaders)):
            if getattr(self.columnHeaders[i], 'sortIcon', False):
                bitmap = self.columnHeaders[i].sortIcon
                
                if i == self.sortedColumn:
                    if self.sortedDirection:
                        bitmap.SetBitmap(up)
                    else:
                        bitmap.SetBitmap(down)
                else:
                    bitmap.SetBitmap(empty)
                bitmap.Refresh()
        return wx.Panel.SetBackgroundColour(self, colour)
    
    def OnPaint(self, event):
        obj = event.GetEventObject()
        dc = wx.BufferedPaintDC(obj)
        dc.Clear()
        
        w, h = self.GetClientSize()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(self.backgroundBrush)
        
        if self.radius > 0:
            dc.DrawRoundedRectangle(0, 0, w, 2*self.radius, self.radius)
        dc.DrawRectangle(0, self.radius, w, h-self.radius)
    
    def OnResize(self, event):
        self.Refresh()
        event.Skip()
        
class TitleHeader(ListHeader):
    def __init__(self, parent, parent_list, columns, font_increment = 2, fontweight = wx.FONTWEIGHT_BOLD, radius = LIST_RADIUS):
        self.font_increment = font_increment
        self.fontweight = fontweight
        ListHeader.__init__(self, parent, parent_list, columns, radius = radius)
    
    def AddComponents(self, columns):
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddSpacer((-1, 3))
        
        self.title = wx.StaticText(self)
        font = self.title.GetFont()
        font.SetPointSize(font.GetPointSize() + self.font_increment)
        font.SetWeight(self.fontweight)
        self.title.SetFont(font)
        
        titlePanel = self.GetTitlePanel(self)
        subtitlePanel = self.GetSubTitlePanel(self)
        righttitlePanel = self.GetRightTitlePanel(self)
        belowPanel = self.GetBelowPanel(self)
        
        if titlePanel:
            subSizer = wx.BoxSizer(wx.HORIZONTAL)
            subSizer.Add(self.title, 0, wx.RIGHT, 3)
            subSizer.Add(titlePanel, 0, wx.ALIGN_CENTER_VERTICAL)
            titlePanel = subSizer
        else:
            titlePanel = self.title

        if subtitlePanel:
            subSizer = wx.BoxSizer(wx.VERTICAL)
            subSizer.Add(titlePanel, 0, wx.BOTTOM, 3)
            subSizer.Add(subtitlePanel)
            subtitlePanel = subSizer
        else:
            subtitlePanel = titlePanel
        
        if righttitlePanel:
            subSizer = wx.BoxSizer(wx.HORIZONTAL)
            subSizer.Add(subtitlePanel, 0, wx.RIGHT, 3)
            subSizer.Add(righttitlePanel, 1)
            righttitlePanel = subSizer
        else:
            righttitlePanel = subtitlePanel
        
        vSizer.Add(righttitlePanel, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, self.radius + 3)
        if belowPanel:
            vSizer.Add(belowPanel, 1, wx.EXPAND|wx.TOP, 3)

        if len(columns) > 0:
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.AddColumns(hSizer, self, columns)
            vSizer.AddSpacer((-1, 3))
            vSizer.Add(hSizer, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, self.radius)
        self.SetSizer(vSizer)
    
    def GetTitlePanel(self, parent):
        pass
    def GetSubTitlePanel(self, parent):
        pass
    def GetRightTitlePanel(self, parent):
        pass
    def GetBelowPanel(self, parent):
        pass
    
    def SetTitle(self, title):
        if title != self.title.GetLabel():
            self.Freeze()
            
            self.title.SetLabel(title)
            self.title.Refresh()
            self.Layout()
            self.Thaw()

class SearchHeaderHelper():
    def GetRightTitlePanel(self, parent):
        self.filter = wx.SearchCtrl(parent)
        self.filter.SetDescriptiveText('Search within results')
        self.filter.Bind(wx.EVT_TEXT, self.OnKey)
        self.filter.SetMinSize((175,-1))
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.filter, 0, wx.ALIGN_CENTER_VERTICAL)
        return hSizer
    
    def FilterCorrect(self, regex_correct):
        pass

    def OnKey(self, event):
        self.parent_list.OnFilter(self.filter.GetValue().strip())
    
    def Reset(self):
        self.filter.Clear()

class SubTitleHeader(TitleHeader):
    def GetSubTitlePanel(self, parent):
        self.subtitle = wx.StaticText(parent)
        return self.subtitle

    def SetSubTitle(self, subtitle):
        if subtitle != self.subtitle.GetLabel():
            self.Freeze()
            
            self.subtitle.SetLabel(subtitle)
            self.subtitle.Refresh()
            
            self.Thaw()
            
class SubTitleSeachHeader(SearchHeaderHelper, SubTitleHeader):
    
    def SetSubTitle(self, subtitle):
        SubTitleHeader.SetSubTitle(self, subtitle)
        self.curSubtitle = subtitle
    
    def SetNrResults(self, nr = None):
        if nr is not None:
            SubTitleHeader.SetSubTitle(self, 'Discovered %d after filter'%nr)
        else:
            SubTitleHeader.SetSubTitle(self, self.curSubtitle)
        
class ButtonHeader(TitleHeader):
    def GetRightTitlePanel(self, parent):
        self.add = wx.Button(parent, -1, "+ Add...", style = wx.BU_EXACTFIT)
        self.add.SetToolTipString('Add a .torrent from an external source.')
        
        self.resume = wx.Button(parent, -1, "Resume")
        self.stop = wx.Button(parent, -1, "Stop")
        self.delete = wx.Button(parent, -1, "Delete")

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.add)
        hSizer.Add(self.resume)
        hSizer.Add(self.stop)
        hSizer.Add(self.delete)
        self.SetStates(False, False, False)
        return hSizer

    def SetEvents(self, add, resume, stop, delete):
        self.add.Bind(wx.EVT_BUTTON, add)
        self.resume.Bind(wx.EVT_BUTTON, resume)
        self.stop.Bind(wx.EVT_BUTTON, stop)
        self.delete.Bind(wx.EVT_BUTTON, delete)
        
    def SetStates(self, resume, stop, delete):
        self.resume.Enable(resume)
        self.stop.Enable(stop)
        self.delete.Enable(delete)

        if resume:
            self.resume.SetToolTipString('Click to start downloading/seeding this torrent.')
        else:
            self.resume.SetToolTip(None)

        if stop:
            self.stop.SetToolTipString('Click to stop downloading/seeding this torrent.')
        else:
            self.stop.SetToolTip(None)
        
        if delete:
            self.delete.SetToolTipString('Click to remove this torrent from your library.')
        else:
            self.delete.SetToolTip(None)
        
class ManageChannelHeader(SubTitleHeader):
    def __init__(self, parent, parent_list):
        TitleHeader.__init__(self, parent, parent_list, [])
        
    def SetName(self, name):
        self.SetTitle(name)
        
    def GetRightTitlePanel(self, parent):
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        self.back = wx.Button(parent, wx.ID_BACKWARD, "Go back")
        hSizer.Add(self.back, 0, wx.LEFT, 5)
        return hSizer

    def SetEvents(self, back):
        self.back.Bind(wx.EVT_BUTTON, back)
        
    def SetNrTorrents(self, nr, nr_favorites = None):
        subtitle = ''
        if nr == 1:
            subtitle = 'Sharing %d torrent'%nr
        else:
            subtitle = 'Sharing %d torrents'%nr
        
        if nr > 0 and nr_favorites:
            if nr_favorites == 0:
                subtitle += ', but not marked as a favorite yet.'
            elif nr_favorites == 1:
                subtitle += ' and 1 Tribler user marked it as one of its favorites.'
            else:
                subtitle += ' and '+str(nr_favorites)+' Tribler users marked it as one of their favorites.'
        self.SetSubTitle(subtitle)
    
    def AddColumns(self, sizer, parent, columns):
        SubTitleHeader.AddColumns(self, sizer, parent, [])

class FamilyFilterHeader(TitleHeader):
    
    def GetSubTitlePanel(self, parent):
        self.family_filter = None
        self.nrfiltered = 0
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.ff = wx.StaticText(parent)
        self.ffbutton = LinkStaticText(parent, '', None)
        self.ffbutton.Bind(wx.EVT_LEFT_UP, self.toggleFamilyFilter)
        
        hSizer.Add(self.ff)
        hSizer.Add(self.ffbutton)
        wx.CallAfter(self.SetFF, True)
        return hSizer
    
    def SetFF(self, family_filter):
        self.family_filter = family_filter
        self._SetLabels()
        
    def SetFiltered(self, nr):
        self.nrfiltered = nr
        self._SetLabels()
    
    def SetBackgroundColour(self, colour):
        TitleHeader.SetBackgroundColour(self, colour)
        if getattr(self, 'ffbutton', False):
            self.ffbutton.SetBackgroundColour(colour)
        
    def toggleFamilyFilter(self, event):
        self.parent_list.toggleFamilyFilter()
    
    def _SetLabels(self):
        self.Freeze()
        if self.family_filter:
            if self.nrfiltered > 0:
                self.ff.SetLabel('%d results blocked by Family Filter, '%self.nrfiltered)
            else:
                self.ff.SetLabel('Family Filter is On, ')
            self.ffbutton.SetLabel('turn off')
        else:
            self.ff.SetLabel('Family Filter is Off, ')
            self.ffbutton.SetLabel('turn on')
        self.Layout()
        self.Thaw()

class SearchHeader(SearchHeaderHelper, FamilyFilterHeader):
    
    def GetTitlePanel(self, parent):
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.subtitle = wx.StaticText(parent)
        hSizer.Add(self.subtitle)
        panel = FamilyFilterHeader.GetTitlePanel(self, parent)
        if panel:
            hSizer.Add(panel)
        return hSizer
    
    def SetSubTitle(self, subtitle):
        self.subtitle.SetLabel('( %s )'%subtitle)
    
    def SetNrResults(self, nr = None):
        if nr is not None:
            self.SetSubTitle('Discovered %d after filter'%nr)
    
    def Reset(self):
        FamilyFilterHeader.Reset(self)
        SearchHeaderHelper.Reset(self)
        self.subtitle.SetLabel('')
        
class SearchHelpHeader(SearchHeader):
    def GetRightTitlePanel(self, parent):
        hSizer = SearchHeader.GetRightTitlePanel(self, parent)

        #filename = os.path.join(os.path.dirname(__file__), "images", "help.png")
        gui_utility = GUIUtility.getInstance()
        filename = os.path.join(gui_utility.vwxGUI_path, "images", "help.png")
        help = wx.StaticBitmap(parent, -1, wx.Bitmap(filename, wx.BITMAP_TYPE_ANY))
        help.Bind(wx.EVT_LEFT_UP, self.helpClick)
        help.SetCursor(wx.StockCursor(wx.CURSOR_HAND))

        hSizer.Add(help, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)

        return hSizer

    def GetSubTitlePanel(self, parent):
        pass
   
    def helpClick(self,event=None):
        title = 'Search within results'
        html = """<p>
        <u>Search within results</u> allows you to filter a list with ease.<br>
        Typing a simple string, will allow you to filter items. <br>
        If you type 'ab', only items matching it will be shown: 
        <ul>
            <li><b>AB</b>C</li>
            <li><b>ab</b>c</li>
            <li>d<b>ab</b>c</li>
        </ul>
        <hr>
        But you can specify more advanced queries. Search within results will additionally allow you to use regex and size filters.
        I.e. 
        <ul>
            <li>'\d{4}' will show only items with a 4 digit number</li>
            <li>'size=100:200' will show items between 100 and 200 Mbytes</li>
            <li>'size=:200' will show items smaller than 200 Mbytes</li>
            <li>'size=100:' will show items larger than 100 Mbytes</li>
        </ul>
        </p>"""
        
        dlg = wx.Dialog(None, -1, title, style=wx.DEFAULT_DIALOG_STYLE, size=(500,300))
        dlg.SetBackgroundColour(wx.WHITE)

        sizer = wx.FlexGridSizer(2,2)
        
        icon = wx.StaticBitmap(dlg, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_MESSAGE_BOX))
        sizer.Add(icon, 0, wx.TOP, 10)
        
        hwin = wx.html.HtmlWindow(dlg, -1, size = (500, 300))
        hwin.SetPage(html)
        sizer.Add(hwin)
        
        sizer.Add((10,0))
        
        btn = wx.Button(dlg, wx.ID_OK, 'Ok')
        sizer.Add(btn, 0, wx.ALIGN_RIGHT, 5)
        
        border = wx.BoxSizer()
        border.Add(sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        dlg.SetSizerAndFit(border)
        dlg.ShowModal()
        dlg.Destroy()

class ChannelHeader(SearchHeader):
    DESCRIPTION_MAX_HEIGTH = 100
    
    def GetRightTitlePanel(self, parent):
        hSizer = SearchHeader.GetRightTitlePanel(self, parent)
        self.back = wx.Button(parent, wx.ID_BACKWARD, "Go back")
        hSizer.Add(self.back, 0, wx.LEFT, 5)
        return hSizer

    def GetBelowPanel(self, parent):
        self.descriptionPanel = ImageScrollablePanel(parent)
        self.descriptionPanel.SetBackgroundColour(wx.WHITE)
        
        self.description = wx.StaticText(self.descriptionPanel)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.description, 1, wx.EXPAND|wx.ALL, 3)
        
        self.descriptionPanel.SetSizer(sizer)
        self.descriptionPanel.Hide()
        
        self.descriptionPanel.Bind(wx.EVT_SIZE, lambda event: self.SetDescriptionSpacer())
        self.descriptionPanel.Bind(wx.EVT_SHOW, lambda event: self.SetDescriptionSpacer())
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.descriptionPanel, 1, wx.EXPAND|wx.LEFT, self.radius + 3)
        self.descriptionSpacer = hSizer.AddSpacer((self.radius + 3, 0))
        self.descriptionSpacer.Show(False)
        #self.descriptionSpacer.sizer = hSizer
        return hSizer

    def Reset(self):
        SearchHeader.Reset(self)
        self.SetStyle(None)
    
    def SetDescriptionSpacer(self):
        if self.descriptionPanel.IsShown():
            dirty = False
            self.descriptionPanel.SetVirtualSizeHints(-1, -1, maxW = self.descriptionPanel.GetClientSize()[0]) #change to allow for scrollbarwidth
            self.descriptionPanel.SetupScrolling()
            
            bestHeight = self.description.GetVirtualSize()[1] + 6
            minHeight = min(self.DESCRIPTION_MAX_HEIGTH, bestHeight)
            if self.descriptionPanel.GetMinSize()[1] != minHeight:
                self.descriptionPanel.SetMinSize((-1, minHeight))
                dirty = True
            
            if bestHeight < self.DESCRIPTION_MAX_HEIGTH:

                descriptionSpacer = self.radius + 3
                if self.descriptionSpacer.GetSize()[0] != descriptionSpacer:
                    self.descriptionSpacer.SetSpacer((descriptionSpacer, 0))
                    dirty = True
                    
                if not self.descriptionSpacer.IsShown():
                    self.descriptionSpacer.Show(True)
                    dirty = True
                    
            elif self.descriptionSpacer.IsShown():
                self.descriptionSpacer.Show(False)
                dirty = True
            
            if dirty:
                self.Layout()
        
    def SetEvents(self, back):
        self.back.Bind(wx.EVT_BUTTON, back)
    
    def SetStyle(self, description, font = None, foreground = None, bgImage = None):
        if description:
            self.description.SetLabel(description)
            if font:
                self.description.SetFont(font)
            if foreground:
                self.description.SetForegroundColour(foreground)
            
            self.descriptionPanel.SetBitmap(bgImage)
            self.descriptionPanel.Show()
        else:
            self.descriptionPanel.Hide()
            
class PlayerHeader(TitleHeader):
    def __init__(self, parent, parent_list, background, columns, minimize, maximize):
        self.minimize = minimize
        self.maximize = maximize
        TitleHeader.__init__(self, parent, parent_list, columns)
        self.SetBackgroundColour(background)
        self.SetTitle('Player')
        
        self.ShowMinimized(False)
    
    def GetRightTitlePanel(self, parent):
        self.minimize = wx.StaticBitmap(self, -1, wx.BitmapFromImage(wx.Image(self.minimize, wx.BITMAP_TYPE_ANY)))
        self.maximize = wx.StaticBitmap(self, -1, wx.BitmapFromImage(wx.Image(self.maximize, wx.BITMAP_TYPE_ANY)))
        
        self.minimize.Bind(wx.EVT_LEFT_UP, self.OnClick)
        self.maximize.Bind(wx.EVT_LEFT_UP, self.OnClick)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.minimize)
        hSizer.Add(self.maximize)
        return hSizer
    
    def OnClick(self, event):
        if self.minimize.IsShown():
            self.parent_list.OnMinimize()
        else:
            self.parent_list.OnMaximize()
        
    def ShowMinimized(self, minimized):
        self.Freeze()
        self.minimize.Show(minimized)
        self.maximize.Show(not minimized)
        
        self.title.Show(minimized)
        self.Layout()
        self.Thaw()
