# Written by Niels Zeilemaker
from Tribler.Main.vwxGUI.tribler_topButton import LinkStaticText, ImageScrollablePanel,\
    NativeIcon, LinkText, BetterText as StaticText, _set_font
from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

from __init__ import LIST_RADIUS
import sys
import wx
import os
from Tribler.Main.vwxGUI import DEFAULT_BACKGROUND

DEBUG = False

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
        if DEBUG:
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
    def __init__(self, parent, parent_list, columns, radius = LIST_RADIUS, spacers = [0,0]):
        wx.Panel.__init__(self, parent)
        self.parent_list = parent_list
        self.columnHeaders = []
        
        self.columns = columns
        self.radius = radius

        self.sortedColumn = -1
        self.defaultSort = -1
        self.sortedDirection = False
        
        self.scrollBar = None
        self.SetForegroundColour(parent.GetForegroundColour())

        self.AddComponents(columns, spacers)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnResize)

    def AddComponents(self, columns, spacers):
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        if self.radius+spacers[0] > 0:
            hSizer.AddSpacer((self.radius + spacers[0],10))
            
        self.AddColumns(hSizer, self, columns)
        
        if self.radius+spacers[1] > 0:
            hSizer.AddSpacer((self.radius+spacers[1],10))
        
        self.SetSizer(hSizer)
        
    def AddColumns(self, sizer, parent, columns):
        selectedfont = self.GetFont()
        selectedfont.SetUnderlined(True)
        
        self.columnHeaders = []
        
        if len(columns) > 0:
            down, up, empty = ListHeaderIcon.getInstance().getBitmaps(self, self.GetBackgroundColour())
            for i in xrange(len(columns)):
                if columns[i].get('name', '') != '':
                    label = LinkText(parent, columns[i]['name'], fonts = [None, selectedfont], style = columns[i].get('style',0)|wx.ST_NO_AUTORESIZE, parentsizer = sizer)
                    label.SetToolTipString('Click to sort table by %s.'%columns[i]['name'])
                    label.SetBackgroundColour(self.GetBackgroundColour())
                    label.column = i
                    label.Bind(wx.EVT_LEFT_UP, self.OnClick)
                    
                    if i == 0:
                        sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL|wx.TOP|wx.BOTTOM, 3)
                    else:
                        sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.TOP|wx.BOTTOM, 3)

                    if columns[i].get('defaultSorted', False):
                        if columns[i].get('sortAsc', False):
                            label.sortIcon = wx.StaticBitmap(self, -1, up)
                        else:
                            label.sortIcon = wx.StaticBitmap(self, -1, down)
                                
                        self.sortedColumn = i
                        self.defaultSort = i
                    else:
                        label.sortIcon = wx.StaticBitmap(self, -1, empty)
                    sizer.Add(label.sortIcon, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 3)
                
                    if columns[i]['width'] == wx.LIST_AUTOSIZE_USEHEADER:
                        columns[i]['width'] = label.GetBestSize()[0] + down.GetWidth() + 3
                    
                    elif columns[i]['width'] == wx.LIST_AUTOSIZE:
                        sizer.AddStretchSpacer()

                    else:
                        if isinstance(columns[i]['width'], basestring) and columns[i]['width'].endswith('em'):
                            test_string = 'T' * int(columns[i]['width'][:-2])
                            labelWidth = self.GetTextExtent(test_string)[0]
                            columns[i]['width'] = labelWidth + 3 + down.GetWidth()
                        
                        remainingWidth = columns[i]['width'] - label.GetBestSize()[0] - down.GetWidth() - 3
                        if remainingWidth > 0:
                            sizer.AddSpacer((remainingWidth, 1))
                        else:
                            print >> sys.stderr, "LIST_HEADER: specified width is too small", columns[i]['name'], columns[i]['width']
                            label.SetSize((label.GetBestSize()[0] + remainingWidth, -1))
                        
                    self.columnHeaders.append(label)
                else:
                    spacer = sizer.Add((columns[i]['width'], -1), 0, wx.LEFT, 3)
                    self.columnHeaders.append(spacer)

        self.scrollBar = sizer.AddSpacer((0,0))
        self.scrollBar.sizer = sizer
    
    def ResizeColumn(self, column, width):
        changed = False
        item = self.columnHeaders[column]
        if isinstance(item, wx.Window):
            if item.GetSize()[0] != width:
                if getattr(item, 'sortIcon', False):
                    width -= (item.sortIcon.GetSize()[0] + 3)
                item.SetMinSize((width, -1))
                changed = True
        elif item.GetSpacer()[0] != width:
                item.SetSpacer((width, -1))

    def SetSpacerRight(self, right):
        if self.scrollBar:
            right = max(0, right)
            
            if self.scrollBar.GetSize()[0] != right:
                self.scrollBar.SetSpacer((right, 0))
                self.scrollBar.sizer.Layout()
    
    def OnClick(self, event):
        newColumn = event.GetEventObject().column
        
        if newColumn == self.sortedColumn:
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
        
        if newColumn == -1 and self.defaultSort != -1:
            newColumn = self.defaultSort
            newDirection = self.columns[self.defaultSort].get('sortAsc', False)
        
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
                
            if getattr(self.columnHeaders[i], 'SetBackgroundColour', False):
                self.columnHeaders[i].SetBackgroundColour(colour)
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
    def __init__(self, parent, parent_list, columns, font_increment = 2, fontweight = wx.FONTWEIGHT_BOLD, radius=LIST_RADIUS, spacers = [0,0]):
        self.font_increment = font_increment
        self.fontweight = fontweight

        ListHeader.__init__(self, parent, parent_list, columns, radius = radius, spacers = spacers)
    
    def AddComponents(self, columns, spacers):
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddSpacer((-1, 3))
        
        self.title = StaticText(self)
        _set_font(self.title, self.font_increment, self.fontweight)
                
        titlePanel = self.GetTitlePanel(self)
        subtitlePanel = self.GetSubTitlePanel(self)
        righttitlePanel = self.GetRightTitlePanel(self)
        belowPanel = self.GetBelowPanel(self)
        
        if titlePanel:
            subSizer = wx.BoxSizer(wx.HORIZONTAL)
            subSizer.Add(self.title)
            subSizer.Add(titlePanel, 0, wx.LEFT|wx.ALIGN_CENTER_VERTICAL, 3)
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
        
        subSizer = wx.BoxSizer(wx.HORIZONTAL)
        subSizer.Add(subtitlePanel)
        if righttitlePanel:
            subSizer.Add(righttitlePanel, 1, wx.LEFT, 3)
        righttitlePanel = subSizer
             
        vSizer.Add(righttitlePanel, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, self.radius+spacers[0])
        if belowPanel:
            vSizer.Add(belowPanel, 1, wx.EXPAND|wx.TOP, 3)

        vSizer.AddSpacer((-1, 3))

        if len(columns) > 0:
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.AddColumns(hSizer, self, columns)
            vSizer.Add(hSizer, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, self.radius+spacers[0])
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
            
    def SetToolTip(self, tooltip):
        self.title.SetToolTipString(tooltip)

class SearchHeaderHelper():
    
    def GetTitlePanel(self, parent):
        self.afterFilter = wx.StaticText(parent)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.afterFilter)
        return hSizer
    
    def SetSubTitle(self, label):
        if label != '':
            label = '( %s )'%label
        
        if getattr(self, 'subtitle','') != label:
            self.afterFilter.SetLabel(label)
            self.subtitle = label
    
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
        self.parent_list.GotFilter(self.filter.GetValue().strip())
    
    def SetFiltered(self, nr):
        if nr:
            self.afterFilter.SetLabel('( Discovered %d after filter )'%nr)
        else:
            self.afterFilter.SetLabel(getattr(self, 'subtitle',''))
    
    def Reset(self):
        self.SetSubTitle('')
        self.filter.Clear()

class SubTitleHeader(TitleHeader):
    def GetSubTitlePanel(self, parent):
        self.subtitle = StaticText(parent)
        return self.subtitle

    def SetSubTitle(self, subtitle):
        if subtitle != self.subtitle.GetLabel():
            self.Freeze()
            
            self.subtitle.SetLabel(subtitle)
            self.subtitle.Refresh()
            
            self.Thaw()
       
class ManageChannelHeader(SubTitleHeader):
    def __init__(self, parent, parent_list):
        TitleHeader.__init__(self, parent, parent_list, [])
        self.nr_favorites = None
        
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
            
        if nr_favorites:
            self.nr_favorites = nr_favorites
        else:
            nr_favorites = self.nr_favorites
        
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
    
    def Reset(self):
        SubTitleHeader.Reset(self)
        self.nr_favorites = None

class FamilyFilterHeader(TitleHeader):
    def __init__(self, *args, **kwargs):
        self.family_filter = None
        self.nrfiltered = 0
        
        TitleHeader.__init__(self, *args, **kwargs)
    
    def GetSubTitlePanel(self, parent):
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.ff = StaticText(parent)
        self.ffbutton = LinkStaticText(parent, '', None)
        self.ffbutton.Bind(wx.EVT_LEFT_UP, self.toggleFamilyFilter)
        self._SetLabels()
        
        hSizer.Add(self.ff)
        hSizer.Add(self.ffbutton)
        return hSizer
    
    def SetFF(self, family_filter, nrfiltered = 0):
        self.family_filter = family_filter
        self.nrfiltered = nrfiltered
        
        self._SetLabels()
        
    def SetFamilyFiltered(self, nr):
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
    
    def Reset(self):
        FamilyFilterHeader.Reset(self)
        SearchHeaderHelper.Reset(self)
        
class SubTitleSeachHeader(SubTitleHeader, SearchHeader):
    
    def GetSubTitlePanel(self, parent):
        sizer = FamilyFilterHeader.GetSubTitlePanel(self, parent)
        subtitle = SubTitleHeader.GetSubTitlePanel(self, parent)
        sizer.Insert(0, subtitle, 0, wx.RIGHT, 3)
        sizer.Layout()
        
        return sizer
    
    def SetSubTitle(self, subtitle):
        SubTitleHeader.SetSubTitle(self, subtitle)
        self.Layout()
        self.curSubtitle = subtitle
    
    def SetNrResults(self, nr = None):
        if nr is not None:
            SubTitleHeader.SetSubTitle(self, 'Discovered %d after filter'%nr)
        else:
            SubTitleHeader.SetSubTitle(self, self.curSubtitle)      
        
class SearchHelpHeader(SearchHeaderHelper, TitleHeader):
    def GetRightTitlePanel(self, parent):
        hSizer = SearchHeaderHelper.GetRightTitlePanel(self, parent)

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
        <hr>
        Finally if you are in the Library you can filter items by state, i.e.
        <ul>
            <li>'state=completed' will show only items which are completed</li>
            <li>'state=active' will show items which currently are being downloaded or seeded</li>
            <li>'state=seeding' will show items which are seeding</li>
            <li>'state=downloading' will show items which are downloading</li>
            <li>'state=stopped' will show items which are stopped/paused and not completed</li>
            <li>'state=checking' will show items which are currently checking or scheduled to be checked</li> 
        </ul>
        </p>"""
        
        dlg = wx.Dialog(GUIUtility.getInstance().frame, -1, title, style=wx.DEFAULT_DIALOG_STYLE, size=(500,300))
        dlg.CenterOnParent()
        dlg.SetBackgroundColour(DEFAULT_BACKGROUND)

        sizer = wx.FlexGridSizer(2,2)
        
        icon = wx.StaticBitmap(dlg, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_MESSAGE_BOX))
        sizer.Add(icon, 0, wx.TOP, 10)
        
        hwin = wx.html.HtmlWindow(dlg, -1, size = (600, 400))
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
        
    def Reset(self):
        SearchHeaderHelper.Reset(self)
        self.filter.Clear()

class ChannelHeader(SearchHeader):
    DESCRIPTION_MAX_HEIGTH = 100
    
    def GetRightTitlePanel(self, parent):
        hSizer = SearchHeader.GetRightTitlePanel(self, parent)
        self.back = wx.Button(parent, wx.ID_BACKWARD, "Go back")
        hSizer.Add(self.back, 0, wx.LEFT, 5)
        return hSizer

    def GetBelowPanel(self, parent):
        self.descriptionPanel = ImageScrollablePanel(parent)
        self.descriptionPanel.SetBackgroundColour(DEFAULT_BACKGROUND)
        
        self.description = StaticText(self.descriptionPanel)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.description, 1, wx.EXPAND|wx.ALL, 3)
        
        self.descriptionPanel.SetSizer(sizer)
        self.descriptionPanel.Hide()
        
        self.descriptionPanel.Bind(wx.EVT_SIZE, self.SetHeight)
        self.descriptionPanel.Bind(wx.EVT_SHOW, self.SetHeight)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.descriptionPanel, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, self.radius + 3)
        return hSizer

    def Reset(self):
        SearchHeader.Reset(self)
        self.SetStyle(None)
    
    def SetHeight(self, event):
        if self.descriptionPanel.IsShown():
            dirty = False
            self.descriptionPanel.SetVirtualSizeHints(-1, -1, maxW = self.descriptionPanel.GetClientSize()[0]) #change to allow for scrollbarwidth
            self.descriptionPanel.SetupScrolling()
            
            bestHeight = self.description.GetVirtualSize()[1] + 6
            minHeight = min(self.DESCRIPTION_MAX_HEIGTH, bestHeight)
            if self.descriptionPanel.GetMinSize()[1] != minHeight:
                self.descriptionPanel.SetMinSize((-1, minHeight))
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
            
class ChannelOnlyHeader(ChannelHeader):
    
    def GetRightTitlePanel(self, parent):
        hSizer = SearchHeader.GetRightTitlePanel(self, parent)

        self.settings = wx.Button(parent, -1, "Settings")
        self.library = wx.Button(parent, -1, "Downloads")
        
        hSizer.Add(self.settings, 0, wx.LEFT, 5)
        hSizer.Add(self.library, 0, wx.LEFT, 5)
        return hSizer
    
    def SetEvents(self, settings, library):
        self.library.Bind(wx.EVT_BUTTON, library)
        self.settings.Bind(wx.EVT_BUTTON, settings)
            
class LibraryHeader(SearchHelpHeader):
    def GetRightTitlePanel(self, parent):
        sizer = SearchHelpHeader.GetRightTitlePanel(self, parent)
        
        self.add = wx.Button(parent, -1, "+ Add...", style = wx.BU_EXACTFIT)
        self.add.SetToolTipString('Add a .torrent from an external source.')
        sizer.Insert(1, self.add, 0, wx.RIGHT, 3)
        return sizer
        
    def SetEvents(self, add):
        self.add.Bind(wx.EVT_BUTTON, add)
        
class LibraryOnlyHeader(LibraryHeader):
    
    def GetRightTitlePanel(self, parent):
        hSizer = LibraryHeader.GetRightTitlePanel(self, parent)
        
        self.settings = wx.Button(parent, -1, "Settings")
        self.channel = wx.Button(parent, -1, "Channel")
        
        hSizer.Add(self.settings, 0, wx.LEFT, 5)
        hSizer.Add(self.channel, 0, wx.LEFT, 5)
        return hSizer
    
    def SetEvents(self, add, settings, channel):
        LibraryHeader.SetEvents(self, add)
        
        self.channel.Bind(wx.EVT_BUTTON, channel)
        self.settings.Bind(wx.EVT_BUTTON, settings)
            
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
