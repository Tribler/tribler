import wx
import sys
import os

from Tribler.Main.vwxGUI.tribler_topButton import LinkStaticText, ImageScrollablePanel
from Tribler.__init__ import LIBRARYNAME

from __init__ import LIST_RADIUS

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
        if background not in self.icons:
            self.icons[background] = self.__createBitmap(parent, background, 'arrow')
        return self.icons[background]
    
    def __createBitmap(self, parent, background, type, flag=0):
        #There are some strange bugs in RendererNative, the alignment is incorrect of the drawn images
        #Thus we create a larger bmp, allowing for borders
        bmp = wx.EmptyBitmap(24,24) 
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(background))
        dc.Clear()
        
        if type == 'arrow':
            wx.RendererNative.Get().DrawDropArrow(parent, dc, (4, 4, 16, 16), flag) #max size is 16x16, using 4px as a border
        dc.SelectObject(wx.NullBitmap)
        
        #determine actual size of drawn icon, and return this subbitmap
        bb = wx.RegionFromBitmapColour(bmp, background).GetBox()
        down = bmp.GetSubBitmap(bb)
        
        img = down.ConvertToImage()
        up = img.Rotate90().Rotate90().ConvertToBitmap()
        
        empty = wx.EmptyBitmap(up.GetWidth(), up.GetHeight())
        dc = wx.MemoryDC(empty)
        dc.SetBackground(wx.Brush(background))
        dc.Clear()
        dc.SelectObject(wx.NullBitmap)
        return [down, up, empty]

class ListHeader(wx.Panel):
    def __init__(self, parent, columns, radius = LIST_RADIUS):
        wx.Panel.__init__(self, parent)
        self.parent = parent
        self.columnHeaders = []
        
        self.columns = columns
        self.radius = radius

        self.sortedColumn = -1
        self.defaultSort = -1
        self.sortedDirection = False

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
                sizer.Add(label.sortIcon, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT|wx.TOP|wx.BOTTOM, 3)
                
                if columns[i]['width'] == wx.LIST_AUTOSIZE_USEHEADER:
                    columns[i]['width'] = label.GetBestSize()[0] + down.GetWidth()
                    
                elif columns[i]['width'] == wx.LIST_AUTOSIZE:
                    sizer.AddStretchSpacer()

                else:
                    if isinstance(columns[i]['width'], basestring) and columns[i]['width'].endswith('em'):
                        test_string = 'T' * int(columns[i]['width'][:-2])
                        columns[i]['width'] = self.GetTextExtent(test_string)[0] + 6
                    
                    remainingWidth = columns[i]['width'] - (label.GetBestSize()[0] + down.GetWidth())
                    if remainingWidth > 0:
                        sizer.AddSpacer((remainingWidth, 1))
                    else:
                        print >> sys.stderr, "LIST_HEADER: specified width is too small", columns[i]['name'], columns[i]['width']
                        label.SetSize((label.GetBestSize()[0] + remainingWidth, -1))
                    
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
            self.scrollBar.sizer.Layout()

    def SetSpacerRight(self, right):
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
        else:
            newDirection = self.columns[newColumn].get('sortAsc', False)
        
        self.GetParent().OnSort(newColumn, newDirection)
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
    def __init__(self, parent, columns, font_increment = 2, fontweight = wx.FONTWEIGHT_BOLD):
        self.font_increment = font_increment
        self.fontweight = fontweight
        ListHeader.__init__(self, parent, columns)
    
    def AddColumns(self, sizer, parent, columns):
        vSizer = wx.BoxSizer(wx.VERTICAL)

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
        
        if belowPanel:
            subSizer = wx.BoxSizer(wx.VERTICAL)
            subSizer.Add(righttitlePanel, 0, wx.BOTTOM|wx.EXPAND, 3)
            subSizer.Add(belowPanel, 0, wx.EXPAND)
            belowPanel = subSizer
        else:
            belowPanel = righttitlePanel
        
        vSizer.Add(belowPanel, 0, wx.EXPAND|wx.ALL, 3)
        if len(columns) > 0:
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            ListHeader.AddColumns(self, hSizer, self, columns)
            vSizer.Add(hSizer, 0, wx.EXPAND)
        
        sizer.Add(vSizer, 1, wx.EXPAND)
    
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
        
class ButtonHeader(TitleHeader):
    def GetRightTitlePanel(self, parent):
        self.resume = wx.Button(parent, -1, "Resume")
        self.stop = wx.Button(parent, -1, "Stop")
        self.delete = wx.Button(parent, -1, "Delete")

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.resume)
        hSizer.Add(self.stop)
        hSizer.Add(self.delete)
        self.SetStates(False, False, False)
        return hSizer

    def SetEvents(self, resume, stop, delete):
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
        
class MyChannelHeader(SubTitleHeader):
    def __init__(self, parent, columns):
        TitleHeader.__init__(self, parent, columns)
        self.SetTitle('My Channel')
    
    def GetTitlePanel(self, parent):
        self.name = wx.StaticText(parent)
        return self.name
        
    def SetName(self, name):
        if name != self.name.GetLabel():
            self.Freeze()
            self.name.SetLabel('( %s\'s Channel )'%name)
            self.name.Refresh()
            self.Thaw()
        
    def SetNrTorrents(self, nr, nr_favorites):
        subtitle = ''
        if nr == 1:
            subtitle = 'Sharing %d torrent'%nr
        else:
            subtitle = 'Sharing %d torrents'%nr
        
        if nr > 0:    
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
        self.parent.toggleFamilyFilter()
    
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

class SearchHeader(FamilyFilterHeader):
    
    def GetRightTitlePanel(self, parent):
        self.filter = wx.SearchCtrl(parent)
        self.filter.SetDescriptiveText('Search within results')
        self.filter.Bind(wx.EVT_TEXT, self.OnKey)
        self.filter.SetMinSize((175,-1))
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(self.filter, 0, wx.ALIGN_CENTER_VERTICAL)
        return hSizer
    
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
    
    def FilterCorrect(self, regex_correct):
        pass
    
    def SetNrResults(self, nr = None):
        if nr is not None:
            self.SetSubTitle('Discovered %d after filter'%nr)
    
    def OnKey(self, event):
        self.parent.OnFilter(self.filter.GetValue().strip())
    
    def Reset(self):
        FamilyFilterHeader.Reset(self)
        self.subtitle.SetLabel('')
        self.filter.Clear()
        
class SearchHelpHeader(SearchHeader):
    def GetRightTitlePanel(self, parent):
        hSizer = SearchHeader.GetRightTitlePanel(self, parent)
        
        help = wx.StaticBitmap(parent, -1, wx.Bitmap(os.path.join(os.path.dirname(__file__), "images/help.png"),wx.BITMAP_TYPE_ANY))
        help.Bind(wx.EVT_LEFT_UP, self.helpClick)
        hSizer.Add(help, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)

        return hSizer

    def helpClick(self,event=None):
        title = 'Search within results'
        html = """<p>
        <u>Search within results</u> allows you to filter a list with ease.<br>
        Typing a simple string, will allow you to filter items. <br>
        If you type 'ab', then only items matching it will be allowed: 
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
            <li>'size=:200' will show items less than 200 Mbytes</li>
            <li>'size=100:' will show items greater than 100 Mbytes</li>
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
    
    def GetRightTitlePanel(self, parent):
        hSizer = SearchHeader.GetRightTitlePanel(self, parent)
        self.back = wx.Button(parent, wx.ID_BACKWARD, "Go back")
        hSizer.Add(self.back, 0, wx.LEFT, 5)
        return hSizer

    def GetBelowPanel(self, parent):
        self.descriptionPanel = ImageScrollablePanel(parent)
        self.descriptionPanel.SetBackgroundColour(wx.WHITE)
        self.description = wx.StaticText(self.descriptionPanel)
        
        sizer = wx.BoxSizer()
        sizer.Add(self.description)
        self.descriptionPanel.SetSizer(sizer)
        self.descriptionPanel.Hide()
        
        return self.descriptionPanel
        
    def SetEvents(self, back):
        self.back.Bind(wx.EVT_BUTTON, back)
    
    def SetComment(self, description, font = None, foreground = None, bgImage = None):
        if description:
            self.description.SetLabel(description)
            if font:
                self.description.SetFont(font)
            if foreground:
                self.description.SetForegroundColour(foreground)
            self.descriptionPanel.Show()
        else:
            self.descriptionPanel.Hide()
        
        bestSize = self.description.GetSize()[1]
        self.descriptionPanel.SetMinSize((-1, bestSize))
        self.descriptionPanel.SetBitmap(bgImage)
        self.Layout()
            
class PlayerHeader(TitleHeader):
    def __init__(self, parent, background, columns, minimize, maximize):
        self.minimize = minimize
        self.maximize = maximize
        TitleHeader.__init__(self, parent, columns)
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
            self.parent.OnMinimize()
        else:
            self.parent.OnMaximize()
        
    def ShowMinimized(self, minimized):
        self.Freeze()
        self.minimize.Show(minimized)
        self.maximize.Show(not minimized)
        
        self.title.Show(minimized)
        self.Layout()
        self.Thaw()