# Written by Niels Zeilemaker, Egbert Bouman
import sys
import math
import wx
from wx.lib.stattext import GenStaticText
from wx.lib.colourutils import AdjustColour
from wx.lib.wordwrap import wordwrap
from wx.lib.mixins.listctrl import CheckListCtrlMixin, ListCtrlAutoWidthMixin

from Tribler.Main.Utility.GuiDBHandler import startWorker
from Tribler.Main.vwxGUI import (TRIBLER_RED, LIST_HIGHTLIGHT, GRADIENT_LRED, GRADIENT_DRED, SEPARATOR_GREY,
                                 FILTER_GREY, DEFAULT_BACKGROUND, COMPLETED_COLOUR, SEEDING_COLOUR, DOWNLOADING_COLOUR,
                                 STOPPED_COLOUR)
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice
from Tribler.Core.simpledefs import DLMODE_VOD


class BetterText(wx.StaticText):

    def __init__(self, *args, **kwargs):
        wx.StaticText.__init__(self, *args, **kwargs)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackGround)

    def OnEraseBackGround(self, event):
        pass

    def SetLabel(self, text):
        if text != self.GetLabel():
            wx.StaticText.SetLabel(self, text)


class MaxBetterText(wx.BoxSizer):

    def __init__(self, parent, label, maxLines=6, maxCharacters=600, name=None, button=None):
        wx.BoxSizer.__init__(self, wx.VERTICAL)

        self.fullLabel = ''
        self.expand = button
        self.parent = parent

        self.maxLines = maxLines
        self.maxCharacters = maxCharacters
        self.name = name or 'item'
        self.name = self.name.lower()

        self.label = BetterText(parent, -1, '')
        self.Add(self.label, 0, wx.EXPAND)

        self.SetLabel(label)

        if sys.platform == 'win32':  # lets do manual word wrapping
            self.label.Bind(wx.EVT_SIZE, self.OnSize)

    def Show(self, show):
        self.ShowItems(show)

    def SetLabel(self, label):
        if self.fullLabel != label:
            self.fullLabel = label
            self.shortLabel = self._limitLabel(label)

            self.label.SetLabel(self.shortLabel)

            if len(self.shortLabel) < len(self.fullLabel):
                self.hasMore = True

                if not self.expand:
                    self.expand = LinkText(self.parent, "See more >>", colours=[None, TRIBLER_RED], parentsizer=self)
                    self.expand.Bind(wx.EVT_LEFT_UP, self.OnFull)
                    self.Add(self.expand, 0, wx.ALIGN_LEFT)
                else:
                    self.expand.Bind(wx.EVT_LEFT_UP, self.OnFull)
                    self.expand.SetLabel("See more >>")
            else:
                self.hasMore = False

    def GetLabel(self):
        return self.fullLabel

    def OnFull(self, event):
        if not self.IsExpanded():
            self.expand.SetLabel("<< See less")
            self.label.SetLabel(self.fullLabel)
        else:
            self.expand.SetLabel("See more >>")
            self.label.SetLabel(self.shortLabel)

        self.parent.OnChange()

    def IsExpanded(self):
        return self.expand is None or self.expand.GetLabel().startswith('<< See less')

    def OnSize(self, event):
        width = self.label.GetSize()[0]
        bestwidth = self.label.GetBestSize()[0]

        if width > 1 and bestwidth != width:
            dc = wx.ClientDC(self.label)
            dc.SetFont(self.label.GetFont())
            label = wordwrap(self.fullLabel, width, dc, breakLongWords=True, margin=0)
            if not self.IsExpanded():
                self.shortLabel = label = self._limitLabel(label)
            self.label.SetLabel(label)

    def SetMinSize(self, minsize):
        self.label.SetMinSize(minsize)
        self.Layout()

    def find_nth(self, haystack, needle, n):
        start = haystack.find(needle)
        while start >= 0 and n > 1:
            start = haystack.find(needle, start + len(needle))
            n -= 1
        return start

    def _limitLabel(self, label):
        # find 6th line or break at 600 characters
        breakAt = self.find_nth(label, '\n', self.maxLines)
        if breakAt != -1:
            breakAt = min(breakAt, self.maxCharacters)
        else:
            breakAt = self.maxCharacters

        return label[:breakAt]


# Stripped down version of wx.lib.agw.HyperTextCtrl, thank you andrea.gavana@gmail.com
class LinkText(GenStaticText):

    def __init__(self, parent, label, fonts=[None, None], colours=[None, None], style=0, parentsizer=None):
        if parentsizer:
            self.parentsizer = parentsizer
        else:
            self.parentsizer = parent

        GenStaticText.__init__(self, parent, -1, label, style=style)
        self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))

        self.SetFonts(fonts)
        self.SetColours(colours)
        self.Reset()

        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvent)
        self.Bind(wx.EVT_MOTION, self.OnMouseEvent)
        self.enter = False

    def SetFonts(self, fonts):
        self.fonts = []
        for font in fonts:
            if font is None:
                font = self.GetFont()
            self.fonts.append(font)

    def SetColours(self, colours):
        self.colours = []
        for colour in colours:
            if colour is None:
                colour = self.GetForegroundColour()
            self.colours.append(colour)

    def GetColours(self):
        return self.colours

    def Reset(self):
        self.SetFontColour(self.fonts[0], self.colours[0])
        self.enter = False

    def SetFontColour(self, font, colour):
        needRefresh = False

        if self.GetFont() != font:
            self.SetFont(font)

            needRefresh = True

        if self.GetForegroundColour() != colour:
            self.SetForegroundColour(colour)

            needRefresh = True

        if needRefresh:
            self.Refresh()
            self.parentsizer.Layout()

    def OnMouseEvent(self, event):
        if event.Moving():
            self.SetFontColour(self.fonts[1], self.colours[1])
            self.enter = True

        elif event.LeftUp() or event.LeftDown():
            pass
        else:
            self.SetFontColour(self.fonts[0], self.colours[0])
            self.enter = False

        event.Skip()

    def SetBackgroundColour(self, colour):
        GenStaticText.SetBackgroundColour(self, colour)
        self.Refresh()


class LinkStaticText(wx.BoxSizer):

    def __init__(self, parent, text, icon="bullet_go.png", icon_type=None, icon_align=wx.ALIGN_RIGHT, font_increment=0, font_colour='#0473BB'):
        wx.BoxSizer.__init__(self, wx.HORIZONTAL)
        self.parent = parent

        self.icon_type = icon_type
        self.icon_align = icon_align

        if icon:
            self.icon = wx.StaticBitmap(parent, bitmap=GuiImageManager.getInstance().getImage(icon))
            self.icon.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        elif icon_type:
            self.icon = wx.StaticBitmap(parent, bitmap=GuiImageManager.getInstance().getBitmap(
                parent, self.icon_type, parent.GetBackgroundColour(), state=0))
        else:
            self.icon = None

        if self.icon and icon_align == wx.ALIGN_LEFT:
            self.Add(self.icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)

        normalfont = parent.GetFont()
        normalfont.SetPointSize(normalfont.GetPointSize() + font_increment)

        selectedfont = parent.GetFont()
        selectedfont.SetPointSize(normalfont.GetPointSize() + font_increment)
        selectedfont.SetUnderlined(True)

        self.text = LinkText(parent, text, fonts=[normalfont, selectedfont], colours=[
                             font_colour, (255, 0, 0, 255)], parentsizer=self)
        self.Add(self.text, 1, wx.ALIGN_CENTER_VERTICAL)

        if self.icon and icon_align == wx.ALIGN_RIGHT:
            self.Add(self.icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 3)

        if self.icon and text == '':
            self.icon.Hide()

        self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        if parent.GetBackgroundStyle() != wx.BG_STYLE_SYSTEM:
            self.SetBackgroundColour(parent.GetBackgroundColour())

    def SetToolTipString(self, tip):
        self.text.SetToolTipString(tip)
        if self.icon:
            self.icon.SetToolTipString(tip)

    def SetLabel(self, text):
        if text != self.text.GetLabel():
            if self.icon:
                self.icon.Show(text != '')

            self.text.SetLabel(text)
            if self.icon and self.icon_align == wx.ALIGN_RIGHT:
                self.text.SetMaxSize((self.text.GetBestSize()[0], -1))

            self.Layout()

    def GetLabel(self):
        return self.text.GetLabel()

    def SetFont(self, font):
        self.text.SetFont(font)

    def GetFont(self):
        return self.text.GetFont()

    def Show(self, show):
        if self.icon:
            self.icon.Show(show)
        if self.text:
            self.text.Show(show)

    def IsShown(self):
        if self.text:
            return self.text.IsShown()
        return False

    def ShowIcon(self, show=True):
        if self.icon and self.icon.IsShown() != show:
            self.icon.Show(show)

    def IsIconShown(self):
        if self.icon:
            return self.icon.IsShown()
        return False

    def SetIconToolTipString(self, tip):
        if self.icon:
            self.icon.SetToolTipString(tip)

    def SetMinSize(self, minsize):
        self.text.SetMinSize(minsize)
        self.Layout()

    def HighLight(self, timeout=2.0):
        self.SetBackgroundColour(LIST_HIGHTLIGHT, blink=True)
        wx.CallLater(timeout * 1000, self.Revert)

    def Revert(self):
        self.SetBackgroundColour(self.originalColor, blink=True)

    def Blink(self):
        self.HighLight(0.15)
        wx.CallLater(300, self.HighLight, 0.15)

    def SetCursor(self, cursor):
        if self.icon:
            self.icon.SetCursor(cursor)

    def ClientToScreen(self, pt):
        if self.icon and self.icon_align != wx.ALIGN_RIGHT:
            return self.icon.ClientToScreen(pt)
        return self.text.ClientToScreen(pt)

    def Bind(self, event, handler, source=None, id=-1, id2=-1):
        def modified_handler(actual_event, handler=handler):
            actual_event.SetEventObject(self)
            handler(actual_event)

        self.text.Bind(event, modified_handler, source, id, id2)
        if self.icon:
            self.icon.Bind(event, modified_handler, source, id, id2)

    def Unbind(self, event):
        self.text.Unbind(event)
        if self.icon:
            self.icon.Unbind(event)

    def SetBackgroundColour(self, colour, blink=False):
        if not blink:
            self.originalColor = colour
        self.text.SetBackgroundColour(colour)

        if self.icon and self.icon_type:
            self.icon.SetBitmap(GuiImageManager.getInstance().getBitmap(self.parent, self.icon_type, colour, state=0))
            self.icon.Refresh()

    def SetForegroundColour(self, colour):
        colours = self.text.GetColours()
        colours[0] = colour
        self.text.SetColours(colours)
        font = self.GetFont()
        if self.text.enter:
            self.text.SetFontColour(font, colours[1])
        else:
            self.text.SetFontColour(font, colours[0])


class HorizontalGauge(wx.Control):

    def __init__(self, parent, background, bitmap, repeat=1, bordersize=0, size=wx.DefaultSize):
        wx.Control.__init__(self, parent, size=size, style=wx.NO_BORDER)

        self.background = background
        self.bitmap = bitmap
        self.repeat = repeat
        self.bordersize = bordersize
        self.percentage = 0
        self.hasBGColour = False

        if size == wx.DefaultSize:
            size = background.GetSize()
            self.SetMinSize((size.width * repeat, size.height))

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    def SetMinSize(self, size):
        w, h = size
        if w == -1:
            w = self.GetSize().x
        if h == -1:
            h = self.GetSize().y
        wx.Control.SetMinSize(self, (w, h))

    def SetPercentage(self, percentage):
        self.percentage = percentage
        self.Refresh()

    def GetPercentage(self):
        return self.percentage

    def SetBackgroundColour(self, colour):
        self.hasBGColour = True
        return wx.Control.SetBackgroundColour(self, colour)

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        if self.hasBGColour:
            dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
            dc.Clear()

        bitmapWidth, bitmapHeight = self.bitmap.GetSize()

        width, height = self.GetClientSize()
        width -= self.bordersize * 2
        width = min(width, self.repeat * bitmapWidth)

        xpos = self.bordersize
        ypos = (height - bitmapHeight) / 2

        for i in range(self.repeat):
            dc.DrawBitmap(self.background, xpos + (i * bitmapWidth), ypos, True)

        dc.SetClippingRegion(xpos, ypos, width * self.percentage, bitmapHeight)
        for i in range(self.repeat):
            dc.DrawBitmap(self.bitmap, xpos + (i * bitmapWidth), ypos, True)

    def OnEraseBackground(self, event):
        pass


class EditText(wx.TextCtrl):

    def __init__(self, parent, text="", multiline=False, validator=wx.DefaultValidator):
        style = 0
        if multiline:
            style = style | wx.TE_MULTILINE

        wx.TextCtrl.__init__(self, parent, -1, text, style=style, validator=validator)
        self.original_text = text

        self.multiline = multiline
        self.maxlength = 0

    def SetValue(self, value):
        wx.TextCtrl.SetValue(self, value)
        self.original_text = value

    def SetMaxLength(self, maxlength):
        if self.multiline:
            self.maxlength = maxlength
            self.Bind(wx.EVT_TEXT, self.OnText)
        else:
            wx.TextCtrl.SetMaxLength(self, maxlength)

    def OnText(self, event):
        value = self.GetValue()
        if len(value) > self.maxlength:
            self.SetValue(value[:self.maxlength])

    def RevertChange(self):
        self.SetValue(self.original_text)

    def IsChanged(self):
        return self.original_text != self.GetValue()

    def Saved(self):
        self.original_text = self.GetValue()

    def GetChanged(self):
        if self.IsChanged():
            return self.GetValue()


class NotebookPanel(wx.Panel):

    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        self.SetForegroundColour(self.GetParent().GetForegroundColour())

        self.sizer = wx.BoxSizer()
        self.SetSizer(self.sizer)

    def SetList(self, list, spacer=0):
        self.list = list
        self.list.IsShownOnScreen = self.IsShownOnScreen
        self.sizer.Add(list, 1, wx.EXPAND | wx.ALL, spacer)

    def IsShownOnScreen(self):
        notebook = self.GetParent()
        page = notebook.GetCurrentPage()
        return page == self

    def __getattr__(self, name):
        try:
            wx.Panel.__getattr__(self, name)
        except:
            return getattr(self.list, name)

    def Show(self, show=True, isSelected=False):
        wx.Panel.Show(self, show)
        self.list.Show(show, isShown=isSelected)
        if show:
            self.Layout()

    def Focus(self):
        self.list.Focus()

    def Reset(self):
        self.list.Reset()

    def SetupScrolling(self, *args, **kwargs):
        if hasattr(self.list, 'SetupScrolling'):
            self.list.SetupScrolling(*args, **kwargs)


class AutoWidthListCtrl(wx.ListCtrl, ListCtrlAutoWidthMixin):

    def __init__(self, parent, style):
        wx.ListCtrl.__init__(self, parent, style=style)
        ListCtrlAutoWidthMixin.__init__(self)


class BetterListCtrl(wx.ListCtrl, ListCtrlAutoWidthMixin):

    def __init__(self, parent, style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.NO_BORDER, tooltip=True):
        wx.ListCtrl.__init__(self, parent, -1, style=style)
        ListCtrlAutoWidthMixin.__init__(self)
        if tooltip:
            self.Bind(wx.EVT_MOTION, self.OnMouseMotion)

    def GetListCtrl(self):
        return self

    def OnMouseMotion(self, event):
        tooltip = ''
        row, _ = self.HitTest(event.GetPosition())
        if row >= 0:
            try:
                for col in xrange(self.GetColumnCount()):
                    tooltip += self.GetItem(row, col).GetText() + "    "

                if len(tooltip) > 0:
                    tooltip = tooltip[:-4]
            except:
                pass
        self.SetToolTipString(tooltip)


class SelectableListCtrl(BetterListCtrl):

    def __init__(self, parent, style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.NO_BORDER, tooltip=True):
        BetterListCtrl.__init__(self, parent, style, tooltip)
        self.allselected = False
        self.Bind(wx.EVT_KEY_DOWN, self._CopyToClipboard)

    def _CopyToClipboard(self, event):
        if event.ControlDown():
            if event.GetKeyCode() == 67:  # ctrl + c
                data = ""

                selected = self.GetFirstSelected()
                while selected != -1:
                    for col in xrange(self.GetColumnCount()):
                        data += self.GetItem(selected, col).GetText() + "\t"
                    data += "\n"
                    selected = self.GetNextSelected(selected)

                do = wx.TextDataObject()
                do.SetText(data)
                wx.TheClipboard.Open()
                wx.TheClipboard.SetData(do)
                wx.TheClipboard.Close()

            elif event.GetKeyCode() == 65:  # ctrl + a
                self.doSelectAll()
        event.Skip()

    def doSelectAll(self):
        for index in xrange(self.GetItemCount()):
            if self.allselected:
                self.Select(index, 0)
            else:
                self.Select(index, 1)
        self.allselected = not self.allselected


class CheckSelectableListCtrl(SelectableListCtrl, CheckListCtrlMixin):

    def __init__(self, parent, style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.NO_BORDER, tooltip=True):
        SelectableListCtrl.__init__(self, parent, style, tooltip)
        CheckListCtrlMixin.__init__(self)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)

    def OnItemActivated(self, event):
        if not wx.GetKeyState(wx.WXK_RETURN):
            self.ToggleItem(event.m_itemIndex)

    def IsSelected(self, index):
        return self.IsChecked(index)

    def GetSelectedItems(self):
        selected = []
        for index in xrange(self.GetItemCount()):
            if self.IsChecked(index):
                selected.append(index)
        return selected

    def doSelectAll(self):
        for index in xrange(self.GetItemCount()):
            if self.allselected:
                self.CheckItem(index, False)
            else:
                self.CheckItem(index, True)
        self.allselected = not self.allselected


class TextCtrlAutoComplete(wx.TextCtrl):

    def __init__(self, parent, entrycallback=None, selectcallback=None, **therest):
        '''
            Constructor works just like wx.TextCtrl
        '''
        if 'style' in therest:
            therest['style'] = wx.TE_PROCESS_ENTER | therest['style']
        else:
            therest['style'] = wx.TE_PROCESS_ENTER

        wx.TextCtrl.__init__(self, parent, **therest)

        self.text = ""
        self.choices = []
        self.screenheight = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y)

        self.dropdown = wx.PopupWindow(self)
        self.dropdown.SetBackgroundColour(DEFAULT_BACKGROUND)
        sizer = wx.BoxSizer()

        self.dropdownlistbox = AutoWidthListCtrl(
            self.dropdown, style=wx.LC_REPORT | wx.BORDER_NONE | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER)
        self.dropdownlistbox.Bind(wx.EVT_LEFT_DOWN, self.ListClick)
        self.dropdownlistbox.Bind(wx.EVT_LEFT_DCLICK, self.ListClick)
        sizer.Add(self.dropdownlistbox, 1, wx.EXPAND | wx.ALL, 3)
        self.dropdown.SetSizer(sizer)

        self.entrycallback = entrycallback
        self.selectcallback = selectcallback

        self.Bind(wx.EVT_KILL_FOCUS, self.ControlChanged, self)
        self.Bind(wx.EVT_TEXT, self.EnteredText, self)
        self.Bind(wx.EVT_KEY_DOWN, self.KeyDown, self)

        self.dropdown.Bind(wx.EVT_LISTBOX, self.ListItemSelected, self.dropdownlistbox)

    def ListClick(self, evt):
        toSel, _ = self.dropdownlistbox.HitTest(evt.GetPosition())
        if toSel == -1:
            return

        self.dropdownlistbox.Select(toSel)
        self.SetValueFromSelected()

    def SetChoices(self, choices=[""]):
        ''' Sets the choices available in the popup wx.ListBox. '''
        self.choices = choices

        # delete, if need, all the previous data
        if self.dropdownlistbox.GetColumnCount() != 0:
            self.dropdownlistbox.DeleteAllColumns()
            self.dropdownlistbox.DeleteAllItems()

        self.dropdownlistbox.InsertColumn(0, "Select")

        for num, it in enumerate(choices):
            self.dropdownlistbox.InsertStringItem(num, it)

        self.dropdownlistbox.SetColumnWidth(0, wx.LIST_AUTOSIZE)  # autosize only works after adding rows

        itemcount = min(len(choices), 7) + 2
        charheight = self.dropdownlistbox.GetCharHeight()

        self.popupsize = wx.Size(self.GetClientSize()[0], (charheight * itemcount) + 6)
        self.dropdown.SetClientSize(self.popupsize)
        self.dropdown.Layout()

    def ControlChanged(self, event):
        self.ShowDropDown(False)
        event.Skip()

    def EnteredText(self, event):
        text = event.GetString()
        if text != self.text:
            self.text = text

            if self.entrycallback:
                def wx_callback(delayedResult, text):
                    choices = delayedResult.get()
                    if text == self.text:
                        self.SetChoices(choices)
                        if len(self.choices) == 0:
                            self.ShowDropDown(False)
                        else:
                            self.ShowDropDown(True)

                def db_callback(text):
                    if text == self.text:
                        return self.entrycallback(text)
                startWorker(wx_callback, db_callback, cargs=(text,), wargs=(text,))

    def KeyDown(self, event):
        skip = True

        sel = self.dropdownlistbox.GetFirstSelected()
        visible = self.dropdown.IsShown()
        if event.GetKeyCode() == wx.WXK_DOWN:
            if sel < (self.dropdownlistbox.GetItemCount() - 1):
                self.dropdownlistbox.Select(sel + 1)
                self.ListItemVisible()

            self.ShowDropDown()
            skip = False

        if event.GetKeyCode() == wx.WXK_UP:
            if sel > 0:
                self.dropdownlistbox.Select(sel - 1)
                self.ListItemVisible()
            self.ShowDropDown()
            skip = False

        if visible:
            if event.GetKeyCode() == wx.WXK_RETURN or event.GetKeyCode() == wx.WXK_SPACE:
                if sel > -1:  # we select the current item if enter or space is pressed
                    skip = event.GetKeyCode() == wx.WXK_RETURN
                    self.SetValueFromSelected(addSpace=(event.GetKeyCode() == wx.WXK_SPACE))
                    self.ShowDropDown(False)

            if event.GetKeyCode() == wx.WXK_ESCAPE:
                self.ShowDropDown(False)
                skip = False

        if skip:
            event.Skip()

    def SetValueFromSelected(self, addSpace=False):
        '''
            Sets the wx.TextCtrl value from the selected wx.ListBox item.
            Will do nothing if no item is selected in the wx.ListBox.
        '''
        sel = self.dropdownlistbox.GetFirstSelected()
        if sel > -1:
            newval = self.dropdownlistbox.GetItemText(sel)
            if addSpace:
                newval += " "

            if newval != self.GetValue():
                self.text = newval

                self.SetValue(newval)
                self.SetInsertionPointEnd()

                if self.selectcallback:
                    self.selectcallback()

    def ShowDropDown(self, show=True):
        ''' Either display the drop down list (show = True) or hide it (show = False). '''
        if show:
            show = len(self.choices) > 0

        if show:
            focusWin = wx.Window.FindFocus()
            show = focusWin == self

        if show and not self.dropdown.IsShown():
            size = self.dropdown.GetSize()
            width, height = self.GetSizeTuple()
            x, y = self.ClientToScreenXY(0, height)
            if size.GetWidth() != width:
                size.SetWidth(width)
                self.dropdown.SetSize(size)

            if (y + size.GetHeight()) < self.screenheight:
                self.dropdown.SetPosition(wx.Point(x, y))
            else:
                self.dropdown.SetPosition(wx.Point(x, y - height - size.GetHeight()))
        self.dropdown.Show(show)

    def ListItemVisible(self):
        ''' Moves the selected item to the top of the list ensuring it is always visible. '''
        self.dropdownlistbox.EnsureVisible(self.dropdownlistbox.GetFirstSelected())

    def ListItemSelected(self, event):
        self.SetValueFromSelected()


class SwarmHealth(wx.Panel):

    def __init__(self, parent, bordersize=0, size=wx.DefaultSize, align=wx.ALIGN_LEFT):
        wx.Panel.__init__(self, parent, size=size, style=wx.NO_BORDER)
        self.bordersize = bordersize
        self.align = align

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    def SetRatio(self, seeders, leechers):
        ratio = 0
        pop = 0

        self.blue = 0
        if leechers <= 0 and seeders <= 0:
            self.barwidth = 0

            self.green = 0
            self.red = 0
        else:
            if leechers == 0:
                ratio = sys.maxsize
            elif seeders == 0:
                ratio = 0
            else:
                ratio = seeders / (leechers * 1.0)

            pop = seeders + leechers
            if ratio == 0 and pop == 0:
                self.barwidth = 1
                self.green = 0
                self.red = 0
            else:
                if pop > 0:
                    self.barwidth = min(max(math.log(pop * 4, 10) * 2, 1.1) / 10.0, 1)  # let it max at 25k population
                else:
                    self.barwidth = 1

                self.green = max(0, min(255, 125 + (ratio * 130)))
                self.red = max(0, min(255, 125 + ((1 - ratio) * 130)))
        self.Refresh()

        if seeders < 0:
            seeders_str = 'Unknown number of seeders'
        elif seeders == 1:
            seeders_str = '1 seeder'
        else:
            seeders_str = '%d seeders' % seeders

        if leechers < 0:
            leechers_str = 'unknown number of leechers'
        elif leechers == 1:
            leechers_str = '1 leecher'
        else:
            leechers_str = '%d leechers' % leechers

        tooltip = '%s ; %s' % (seeders_str, leechers_str)
        self.SetToolTipString(tooltip)

    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)

        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()

        width, height = self.GetClientSize()
        width -= self.bordersize * 2
        width -= 1
        width -= width % 10
        width += 1

        if self.align == wx.ALIGN_CENTER:
            xpos = (self.GetClientSize()[0] - width) / 2
        elif self.align == wx.ALIGN_RIGHT:
            xpos = self.GetClientSize()[0] - width
        else:
            xpos = 0

        dc.SetPen(wx.Pen(self.GetParent().GetForegroundColour()))
        dc.SetBrush(wx.WHITE_BRUSH)
        dc.DrawRectangle(xpos, 0, width, height)

        dc.SetPen(wx.TRANSPARENT_PEN)

        dc.SetBrush(wx.Brush((self.red, self.green, self.blue), wx.SOLID))

        if self.barwidth > 0:
            dc.DrawRectangle(xpos + 1, 1, self.barwidth * (width - 2), height - 2)

        if self.green > 0 or self.red > 0:
            dc.SetPen(wx.WHITE_PEN)
            for i in range(1, 10):
                x = xpos + (width / 10) * i
                dc.DrawLine(x, 1, x, height - 1)

        dc.SetPen(wx.BLACK_PEN)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(xpos, 0, width, height)

    def OnEraseBackground(self, event):
        pass


class ProgressBar(wx.Panel):

    def __init__(self, parent, colours=["#ffffff", "#92cddf", "#006dc0"], size=wx.DefaultSize):
        wx.Panel.__init__(self, parent, size=size, style=wx.NO_BORDER)
        self.pens = [wx.Pen(c) for c in colours]
        self.brushes = [wx.Brush(c) for c in colours]

        for i in xrange(len(self.pens)):
            if self.pens[i].GetColour() == wx.WHITE:
                self.pens[i] = None
        self.reset()

        self.SetMaxSize((-1, 6))
        self.SetMinSize((1, 6))
        self.SetBackgroundColour(wx.WHITE)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

        self.completed = False
        self.prev_blocks = None

    def OnEraseBackground(self, event):
        pass  # Or None

    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()

        x, y, maxw, maxh = self.GetClientRect()

        if len(self.blocks) > 0 and not self.completed:
            numrect = float(len(self.blocks))
            w = max(1, maxw / numrect)

            lines = [(x + i, y, x + i, maxh) for i in xrange(maxw) if self.blocks[int(i / w)]]
            pens = [self.pens[self.blocks[int(i / w)]] for i in xrange(maxw) if self.blocks[int(i / w)]]
            dc.DrawLineList(lines, pens)

        if self.completed:
            dc.SetBrush(self.brushes[2])
        else:
            dc.SetBrush(wx.TRANSPARENT_BRUSH)

        dc.SetPen(wx.BLACK_PEN)
        dc.DrawRoundedRectangle(x, y, maxw, maxh, 2)

    def set_pieces(self, blocks):
        if self.prev_blocks == blocks:
            return
        else:
            self.prev_blocks = blocks

        maxBlocks = max(self.GetClientRect().width, 100)
        haveBlocks = len(blocks)

        if haveBlocks > maxBlocks:  # we need to group the blocks
            sblocks = [0] * maxBlocks
            nrBlocksPerPixel = haveBlocks / maxBlocks
            for i in xrange(maxBlocks):
                any = False
                all = True

                for j in xrange(nrBlocksPerPixel * i, nrBlocksPerPixel * (i + 1)):
                    if blocks[j]:
                        any = True
                    else:
                        all = False
                        if any:
                            break
                if all:
                    sblocks[i] = 2
                elif any:
                    sblocks[i] = 1
        else:
            sblocks = []
            for i in xrange(haveBlocks):
                remainingPixels = maxBlocks - len(sblocks)
                remainingBlocks = haveBlocks - i
                nrPixelsToColour = int(remainingPixels / remainingBlocks)

                if blocks[i]:
                    state = 2
                else:
                    state = 0

                sblocks.extend([state] * nrPixelsToColour)
        self.set_blocks(sblocks)

    def set_blocks(self, blocks):
        self.completed = all([x == 2 for x in blocks])
        self.blocks = blocks

    def setNormalPercentage(self, perc):
        self.prev_blocks = None
        maxBlocks = max(self.GetClientRect().width, 100)

        sblocks = [2] * int(perc * maxBlocks)
        sblocks += [0] * (maxBlocks - len(sblocks))
        self.set_blocks(sblocks)

    def reset(self, colour=0):
        self.prev_blocks = None
        sblocks = [colour] * 100
        self.set_blocks(sblocks)


def _set_font(control, size_increment=0, fontweight=wx.FONTWEIGHT_NORMAL, fontcolour=None):
    font = control.GetFont()
    font.SetPointSize(font.GetPointSize() + size_increment)
    font.SetWeight(fontweight)
    control.SetFont(font)
    if fontcolour:
        control.SetForegroundColour(fontcolour)


class ActionButton(wx.Panel):

    def __init__(self, parent, id=-1, bitmap=wx.NullBitmap, hover=True, **kwargs):
        wx.Panel.__init__(self, parent, id, size=bitmap.GetSize(), **kwargs)
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self.hover = hover
        self.enabled = True
        self.handler = None
        self.SetBitmapLabel(bitmap, recreate=True)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseAction)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_CHILD_FOCUS, self.OnFocus)

    def GetBitmapLabel(self):
        return self.bitmaps[0]

    def SetBitmapLabel(self, bitmap, recreate=False):
        if bitmap:
            if recreate:
                image = bitmap.ConvertToImage()
                self.bitmaps = [bitmap]
                self.bitmaps.append(
                    wx.BitmapFromImage(image.AdjustChannels(1.0, 1.0, 1.0, 0.6)) if self.hover else bitmap)
                self.bitmaps.append(wx.BitmapFromImage(image.ConvertToGreyscale().AdjustChannels(1.0, 1.0, 1.0, 0.3)))
            else:
                self.bitmaps[0] = bitmap
            self.Refresh()

    def GetBitmapHover(self):
        return self.bitmaps[1]

    def SetBitmapHover(self, bitmap):
        if bitmap:
            self.bitmaps[1] = bitmap

    def GetBitmapDisabled(self):
        return self.bitmaps[2]

    def SetBitmapDisabled(self, bitmap):
        if bitmap:
            self.bitmaps[2] = bitmap

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        # Draw the background
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        if hasattr(self.GetParent(), 'bitmap'):
            if not self.GetParent().bitmap:
                wx.CallLater(100, self.Refresh)
            else:
                rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
                sub = self.GetParent().bitmap.GetSubBitmap(rect)
                dc.DrawBitmap(sub, 0, 0)
        # Draw the button using a gc (dc doesn't do transparency very well)
        bitmap = self.GetBitmap()
        gc = wx.GraphicsContext.Create(dc)
        gc.DrawBitmap(bitmap, 0, 0, *bitmap.GetSize())

    def OnMouseAction(self, event):
        if event.Entering() or event.Leaving():
            self.Refresh()
        event.Skip()

    def OnFocus(self, event):
        self.Refresh()

    def GetBitmap(self):
        if not self.IsEnabled():
            return self.bitmaps[2]
        if self.GetScreenRect().Contains(wx.GetMousePosition()):
            return self.bitmaps[1]
        return self.bitmaps[0]

    def Bind(self, event, handler):
        if event == wx.EVT_LEFT_UP:
            self.handler = handler
        wx.Panel.Bind(self, event, handler)

    def Enable(self, enable):
        if enable and self.handler:
            self.Bind(wx.EVT_LEFT_UP, self.handler)
        elif not enable:
            self.Unbind(wx.EVT_LEFT_UP)
        self.enabled = enable
        self.Refresh()

    def IsEnabled(self):
        return self.enabled


class ProgressButton(ActionButton):

    def __init__(self, parent, id=-1, label='Search', **kwargs):
        ActionButton.__init__(self, parent, id=id, bitmap=wx.EmptyBitmap(1, 1), **kwargs)
        self.icon = None
        self.icon_hl = None
        self.icon_gs = None
        self.label = label
        self.maxval = 25
        self.curval = 25
        self.ResetSize()

    def GetRange(self):
        return self.maxval

    def SetRange(self, maximum):
        self.maxval = maximum
        self.Refresh()

    def GetValue(self):
        return self.curval

    def SetValue(self, current):
        self.curval = current
        self.Refresh()

    def SetIcon(self, icon):
        if isinstance(icon, wx.Bitmap):
            self.icon = icon
            self.icon_hl = icon.ConvertToImage().AdjustChannels(1.0, 1.0, 1.0, 0.6).ConvertToBitmap()
            self.icon_gs = icon.ConvertToImage().ConvertToGreyscale().ConvertToBitmap()
            self.ResetSize()

    def ResetSize(self):
        w, h = self.GetTextExtent(self.label)
        w += 30
        h += 10
        if self.icon:
            w = w + self.icon.GetSize()[0] + 5
            h = max(h, self.icon.GetSize()[1])
        self.SetMinSize((w, h))

    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        # Draw the background using the bitmap from the parent (if it exists)
        if not getattr(self.GetParent(), 'bitmap', None):
            # Draw the background using the backgroundcolour from the parent
            dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
            dc.Clear()
        else:
            # Draw the background using the bitmap from the parent (TopSearchPanel)
            rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
            try:
                sub = self.GetParent().bitmap.GetSubBitmap(rect)
                dc.DrawBitmap(sub, 0, 0)
            except:
                pass
        x, y, width, height = self.GetClientRect()
        # If there is currently something in progress, first paint a black&white background
        if self.curval != self.maxval:
            col1 = wx.Colour(199, 199, 199)
            col2 = wx.Colour(162, 162, 162)
            br = gc.CreateLinearGradientBrush(x, y, x, y + height, col1, col2)
            gc.SetBrush(br)
            gc.SetPen(wx.TRANSPARENT_PEN)
            path = gc.CreatePath()
            path.AddRoundedRectangle(x, y, width - 1, height - 1, 5)
            path.CloseSubpath()
            gc.DrawPath(path)
        # Depending on the state of the button, paint the progress made thus far
        highlight = self.GetScreenRect().Contains(wx.GetMousePosition())
        if not self.IsEnabled():
            col1 = wx.Colour(199, 199, 199)
            col2 = wx.Colour(162, 162, 162)
        elif highlight:
            col1 = wx.Colour(255, 169, 148)
            col2 = wx.Colour(255, 150, 127)
        else:
            col1 = GRADIENT_LRED
            col2 = GRADIENT_DRED
        br = gc.CreateLinearGradientBrush(x, y, x, y + height, col1, col2)
        gc.SetBrush(br)
        gc.SetPen(wx.TRANSPARENT_PEN)
        path = gc.CreatePath()
        if self.curval > 1:
            progress = max(self.curval * 1.0 / self.maxval, 0.15)
            path.AddRoundedRectangle(x, y, progress * width - 1, height - 1, 5)
            path.CloseSubpath()
            gc.DrawPath(path)
        # Draw the button label and icon (if any)
        font = self.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        dc.SetTextForeground(wx.WHITE)
        textWidth, textHeight = dc.GetFullTextExtent(self.label)[:2]
        if self.icon:
            x_icon = (width - textWidth - self.icon.GetSize()[0] - 5) / 2
            y_icon = (height - self.icon.GetSize()[1]) / 2
            if highlight:
                dc.DrawBitmap(self.icon_hl, x_icon, y_icon)
            elif not self.IsEnabled():
                dc.DrawBitmap(self.icon_gs, x_icon, y_icon)
            else:
                dc.DrawBitmap(self.icon, x_icon, y_icon)
            x = x_icon + 5 + self.icon.GetSize()[0]
            y = (height - textHeight) / 2
            dc.DrawText(self.label, x, y)
        else:
            x = (width - textWidth) / 2
            y = (height - textHeight) / 2
            dc.DrawText(self.label, x, y)


class FancyPanel(wx.Panel):

    def __init__(self, *args, **kwargs):
        self.radius = kwargs.pop('radius', 0)
        self.border = kwargs.pop('border', 0)
        wx.Panel.__init__(self, *args, **kwargs)
        self.focus = None
        self.colour1 = self.colour2 = None
        self.border_colour = self.border_highlight = None
        self.bitmap = None
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    def SetBorderColour(self, colour, highlight=None):
        self.border_colour = colour
        if highlight:
            self.border_highlight = highlight
            self.focus = False
            self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
            self.Bind(wx.EVT_CHILD_FOCUS, self.OnSetFocus)
            self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
            self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseAction)
        self.Refresh()

    def SetBackgroundColour(self, colour1, colour2=None):
        self.colour1 = colour1
        self.colour2 = colour2 if colour2 else colour1
        wx.Panel.SetBackgroundColour(self, self.colour1)
        self.Refresh()

    def OnSetFocus(self, event):
        self.focus = True
        self.Refresh()

    def OnKillFocus(self, event):
        self.focus = False
        self.Refresh()

    def OnMouseAction(self, event):
        if event.Entering() or event.Leaving():
            self.Refresh()
        event.Skip()

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        x, y, width, height = self.GetClientRect()

        # Use buffered drawing and save the buffer to a bitmap
        buffer = wx.EmptyBitmap(width, height)
        dc = wx.BufferedPaintDC(self, buffer)

        # For rounded panels, paint the background for the corners first
        if self.radius > 0:
            if getattr(self.GetParent(), 'bitmap', None):
                rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
                sub = self.GetParent().bitmap.GetSubBitmap(rect)
                dc.DrawBitmap(sub, 0, 0)
            else:
                dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
                dc.Clear()

        # Next, draw gradient/bitmap/regular background
        gc = wx.GraphicsContext.Create(dc)
        gc.SetPen(wx.TRANSPARENT_PEN)
        if self.colour1 != self.colour2:
            gc.SetBrush(gc.CreateLinearGradientBrush(x, y, x, y + height, self.colour1, self.colour2))
            gc.DrawRoundedRectangle(x, y, width, height, self.radius)
        else:
            gc.SetBrush(wx.Brush(self.colour1 if self.colour1 else self.GetBackgroundColour()))
            gc.DrawRoundedRectangle(x, y, width, height, self.radius)

        # Set border colour
        gc.SetPen(wx.Pen(self.border_colour, 1, wx.SOLID) if self.border_colour else wx.TRANSPARENT_PEN)
        if self.focus is not None:
            if self.focus:
                gc.SetPen(wx.Pen(self.border_highlight, 1, wx.SOLID))
            elif self.GetScreenRect().Contains(wx.GetMousePosition()):
                gc.SetPen(wx.Pen(AdjustColour(self.border_colour, -10), 1, wx.SOLID))

        # Draw border
        if self.radius > 0:
            if self.border > 0:
                gc.DrawRoundedRectangle(x, y, width - 1, height - 1, self.radius)
        else:
            if bool(self.border & wx.RIGHT):
                gc.DrawLines([(x + width - 1, y), (x + width - 1, y + height - 1)])
            if bool(self.border & wx.LEFT):
                gc.DrawLines([(x, y), (x, y + height - 1)])
            if bool(self.border & wx.TOP):
                gc.DrawLines([(x, y), (x + width - 1, y)])
            if bool(self.border & wx.BOTTOM):
                gc.DrawLines([(x, y + height - 1), (x + width - 1, y + height - 1)])

        self.bitmap = buffer


class MinMaxSlider(wx.Panel):

    def __init__(self, *args, **kwargs):
        self.slider_size = kwargs.pop('slider_size', (100, 25))
        wx.Panel.__init__(self, *args, **kwargs)
        self.SetBackgroundColour(self.GetParent().GetBackgroundColour())
        self.SetForegroundColour(self.GetParent().GetForegroundColour())
        self.base = 1.7
        self.LoadIcons()
        self.SetMinMax(0, 0)
        self.text_spacers = [self.GetTextExtent('T' * 11)[0]] * 2
        self.SetSize((sum(self.text_spacers) + self.slider_size[0], -1))
        self.Reset()
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)

    def SetMinMax(self, min, max):
        if max < min:
            return
        self.min = min
        self.max = max
        self.Refresh()

    def GetMinMax(self):
        return (self.min, self.max)

    def SetCurrentValues(self, min_val, max_val):
        if self.max - self.min == 0 or min_val == 0:
            w, h = self.arrow_up.GetSize()
            self.arrow_up_rect = [self.range[0], self.GetClientRect()[3] / 2 + 1, w, h]
        else:
            length = self.range[1] - self.range[0]
            min_val = (min_val - self.min) / float(self.max - self.min)
            min_val = min_val * math.pow(length, self.base)
            self.arrow_up_rect[0] = math.exp((math.log(min_val) / self.base)) + self.range[0]

        if self.max - self.min == 0 or max_val == 0:
            w, h = self.arrow_down.GetSize()
            self.arrow_down_rect = [self.range[1], self.GetClientRect()[3] / 2 - h - 1, w, h]
        else:
            length = self.range[1] - self.range[0]
            max_val = (max_val - self.min) / float(self.max - self.min)
            max_val = max_val * math.pow(length, self.base)
            self.arrow_down_rect[0] = math.exp((math.log(max_val) / self.base)) + self.range[0]

        self.Refresh()

    def GetCurrentValues(self):
        length = self.range[1] - self.range[0]
        min_val = math.pow(self.arrow_up_rect[0] - self.range[0], self.base) / math.pow(length, self.base)
        max_val = math.pow(self.arrow_down_rect[0] - self.range[0], self.base) / math.pow(length, self.base)
        min_val = self.min + min_val * (self.max - self.min)
        max_val = self.min + max_val * (self.max - self.min)
        return (min_val, max_val)

    def OnLeftDown(self, event):
        x, y, w, h = self.arrow_down_rect
        if wx.Rect(x, y - 4, w, h + 4).Contains(event.GetPositionTuple()):
            self.arrow_down_drag = True
        x, y, w, h = self.arrow_up_rect
        if wx.Rect(x, y, w, h + 4).Contains(event.GetPositionTuple()):
            self.arrow_up_drag = True
        self.CaptureMouse()
        self.Bind(wx.EVT_MOTION, self.OnMotion)

    def OnLeftUp(self, event):
        self.arrow_down_drag = False
        self.arrow_up_drag = False
        self.ReleaseMouse()
        self.Unbind(wx.EVT_MOTION)
        # Call parent
        min_val, max_val = self.GetCurrentValues()
        self.GetParent().GetParent().OnSlider(min_val, max_val)

    def OnMotion(self, event):
        if event.LeftIsDown():
            self.SetIcon(event)

    def SetIcon(self, event):
        mx = event.GetPositionTuple()[0] - 3
        if self.arrow_up_drag and mx < self.arrow_down_rect[0]:
            self.arrow_up_rect[0] = max(mx, self.range[0])
        elif self.arrow_down_drag and mx > self.arrow_up_rect[0]:
            self.arrow_down_rect[0] = min(mx, self.range[1])
        self.Refresh()

    def LoadIcons(self):
        self.arrow_down = GuiImageManager.getInstance().getBitmap(self, u"slider", self.GetBackgroundColour(), state=0)
        img = self.arrow_down.ConvertToImage()
        self.arrow_up = img.Rotate90().Rotate90().ConvertToBitmap()

    def Reset(self):
        w, h = self.arrow_down.GetSize()
        self.range = [self.text_spacers[0], self.GetSize()[0] - w - self.text_spacers[1]]
        self.arrow_down_rect = [self.range[1], self.GetClientRect()[3] / 2 - h - 1, w, h]
        self.arrow_down_drag = False
        self.arrow_up_rect = [self.range[0], self.GetClientRect()[3] / 2 + 1, w, h]
        self.arrow_up_drag = False

        self.SetMinMax(0, 0)

    def SetFormatter(self, formatter):
        self.formatter = formatter

    def Format(self, i):
        return self.formatter(i)

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        bg_colour = self.GetBackgroundColour()
        fg_colour = self.GetForegroundColour()
        dc.SetBackground(wx.Brush(bg_colour))
        dc.SetTextForeground(fg_colour)
        dc.Clear()

        _, _, width, height = self.GetClientRect()
        min_val, max_val = self.GetCurrentValues()
        min_val = self.Format(min_val)
        max_val = self.Format(max_val)
        dc.SetFont(self.GetFont())
        text_width, text_height = dc.GetTextExtent(min_val)
        dc.DrawText(min_val, (self.text_spacers[0] - text_width) / 2, (height - text_height + 1) / 2)
        text_width, text_height = dc.GetTextExtent(max_val)
        dc.DrawText(max_val, width - text_width - (
            self.text_spacers[0] - text_width) / 2, (height - text_height + 1) / 2)

        dc.SetPen(wx.Pen(fg_colour, 2, wx.SOLID))
        dc.DrawLine(self.range[0], height / 2, self.range[1] + self.arrow_down.GetSize()[0], height / 2)

        gc = wx.GraphicsContext.Create(dc)
        gc.DrawBitmap(self.arrow_down, *self.arrow_down_rect)
        gc.DrawBitmap(self.arrow_up, *self.arrow_up_rect)


class SimpleNotebook(wx.Panel):

    def __init__(self, *args, **kwargs):
        self.show_single_tab = kwargs.pop('show_single_tab', True)
        wx.Panel.__init__(self, *args, **kwargs)
        self.SetBackgroundColour(FILTER_GREY)
        self.labels = []
        self.panels = []
        self.pshown = 0
        self.lspace = 10
        self.messagePanel = None
        self.message_on_pages = []
        self.hSizer_labels = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer_panels = wx.BoxSizer(wx.HORIZONTAL)
        self.tab_colours = {}
        self.tab_panel = wx.Panel(self, -1)
        self.tab_panel.SetSizer(self.hSizer_labels)
        self.tab_panel.SetBackgroundColour(self.GetBackgroundColour())
        self.tab_panel.SetMinSize((-1, 25))
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.tab_panel, 0, wx.EXPAND)
        vSizer.Add(self.hSizer_panels, 1, wx.EXPAND)
        self.SetSizer(vSizer)
        self.tab_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    def OnLeftUp(self, event):
        obj = event.GetEventObject()
        if obj in self.labels:
            self.SetSelection(self.labels.index(obj))
            self.tab_panel.Refresh()

    def GetPage(self, num_page):
        if num_page >= 0 and num_page < self.GetPageCount():
            return self.panels[num_page]
        return None

    def AddPage(self, page, text, tab_colour=None):
        self.InsertPage(self.GetPageCount(), page, text, tab_colour)

    def InsertPage(self, index, page, text, tab_colour=None):
        if not (index >= 0 and index <= self.GetPageCount()):
            return

        if tab_colour:
            self.tab_colours[index] = tab_colour

        label = LinkStaticText(self.tab_panel, text, None, font_colour=self.tab_panel.GetForegroundColour())
        label.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.hSizer_labels.Insert(index, label, 0, wx.RIGHT | wx.LEFT | wx.CENTER, self.lspace)
        self.hSizer_labels.Layout()
        page.Show(index == 0)
        self.hSizer_panels.Insert(index, page, 100, wx.EXPAND)
        self.labels.insert(index, label)
        self.panels.insert(index, page)

        if not self.show_single_tab:
            show_tab_panel = self.GetPageCount() > 1
            self.tab_panel.SetMinSize((-1, 25 if show_tab_panel else 1))
            self.hSizer_labels.ShowItems(show_tab_panel)
        self.Layout()

        if index <= self.pshown:
            if self.GetPageCount() > 1:
                self.pshown += 1
            wx.CallAfter(self.ResetTabs)

    def ResetTabs(self):
        for index, label in enumerate(self.labels):
            selected_tab = self.GetSelection()
            is_current = index == selected_tab
            fg_colour = TRIBLER_RED if is_current else self.tab_panel.GetForegroundColour()
            bg_colour = self.tab_colours.get(selected_tab, self.panels[
                                             selected_tab].GetBackgroundColour()) if is_current else self.tab_panel.GetBackgroundColour()
            label.SetForegroundColour(fg_colour)
            label.SetBackgroundColour(bg_colour)
        self.tab_panel.Refresh()

    def RemovePage(self, index):
        label = self.labels.pop(index)
        label.Show(False)
        page = self.panels.pop(index)
        page.Show(False)
        self.hSizer_labels.Remove(index)
        self.hSizer_panels.Remove(index)

        if self.GetSelection() == index:
            self.SetSelection(index - 1 if index > 0 else 0)

        if not self.show_single_tab:
            show_tab_panel = self.GetPageCount() > 1
            self.tab_panel.SetMinSize((-1, 25 if show_tab_panel else 1))
            self.hSizer_labels.ShowItems(show_tab_panel)
        self.Layout()

    def ShowPage(self, index, show):
        is_selected = self.GetSelection() == index

        label = self.labels[index]
        label.Show(show)

        if not show and is_selected:
            self.SetSelection(index - 1 if index > 0 else 0)

        self.hSizer_labels.Layout()
        self.hSizer_panels.Layout()
        self.Layout()
        self.Refresh()

    def GetPageText(self, num_page):
        if num_page >= 0 and num_page < self.GetPageCount():
            return self.labels[num_page].GetLabel()
        return ''

    def SetPageText(self, num_page, text):
        if num_page >= 0 and num_page < self.GetPageCount():
            self.labels[num_page].SetLabel(text)
            self.Layout()

    def GetPageCount(self):
        return len(self.labels)

    def GetCurrentPage(self):
        return self.GetPage(self.GetSelection())

    def GetIndexFromText(self, text):
        result = None
        for i in range(self.GetPageCount()):
            if self.GetPageText(i) == text:
                result = i
                break
        return result

    def SetSelection(self, num_page):
        if not (num_page >= 0 and num_page < self.GetPageCount()) or self.pshown == num_page:
            return

        old_page = self.GetCurrentPage()
        if old_page:
            if self.GetSelection() in self.message_on_pages:
                self.messagePanel.Show(False)
            else:
                old_page.Show(False)
            old_label = self.labels[self.pshown]
            old_label.SetForegroundColour(self.tab_panel.GetForegroundColour())
            old_label.SetBackgroundColour(self.tab_panel.GetBackgroundColour())

        new_page = self.panels[num_page]
        if num_page in self.message_on_pages:
            self.messagePanel.Show(True)
        else:
            new_page.Show(True)
        new_label = self.labels[num_page]
        new_label.SetForegroundColour(TRIBLER_RED)
        new_label.SetBackgroundColour(self.tab_colours.get(num_page, new_page.GetBackgroundColour()))
        self.Layout()
        new_page.Layout()

        event = wx.NotebookEvent(wx.EVT_NOTEBOOK_PAGE_CHANGED.typeId, 0, num_page, self.GetSelection())
        event.SetEventObject(self)
        self.pshown = num_page
        wx.PostEvent(self.GetEventHandler(), event)

    def GetSelection(self):
        return self.pshown

    def ChangeSelection(self, num_page):
        self.SetSelection(num_page)

    def CalcSizeFromPage(self, *args):
        return GUIUtility.getInstance().frame.splitter_bottom_window.GetSize()

    def SetMessagePanel(self, panel):
        if self.messagePanel:
            self.messagePanel.Show(False)
            self.hSizer_panels.Detach(self.messagePanel)
        self.messagePanel = panel
        self.hSizer_panels.Add(self.messagePanel, 100, wx.EXPAND)
        self.messagePanel.Show(self.GetSelection() in self.message_on_pages)
        self.hSizer_labels.Layout()
        self.hSizer_panels.Layout()
        self.Layout()
        self.Refresh()

    def ShowMessageOnPage(self, index, show_message):
        is_selected = self.GetSelection() == index

        panel = self.panels[index]
        panel.Show(not show_message and is_selected)

        if show_message and is_selected:
            self.messagePanel.Show(True)
        elif not show_message and is_selected:
            self.messagePanel.Show(False)

        if show_message and index not in self.message_on_pages:
            self.message_on_pages.append(index)
        elif not show_message and index in self.message_on_pages:
            self.message_on_pages.remove(index)

        self.hSizer_labels.Layout()
        self.hSizer_panels.Layout()
        self.Layout()
        self.Refresh()

    def GetThemeBackgroundColour(self):
        return self.GetBackgroundColour()

    def OnEraseBackground(self, evt):
        dc = evt.GetDC()
        if not dc:
            dc = wx.ClientDC(self)
            rect = self.GetUpdateRegion().GetBox()
            dc.SetClippingRect(rect)

        width, height = self.tab_panel.GetClientSize()
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()

        # Draw bottom separator
        dc.SetPen(wx.Pen(SEPARATOR_GREY))
        dc.DrawLine(0, height - 1, width, height - 1)

        # If we're not showing the full tab_panel, stop here
        if not self.show_single_tab and self.GetPageCount() < 2:
            return

        # Calculate separator positions
        separator_positions = []
        visible_labels = [label for label in self.labels if label.IsShown()]
        for i in range(0, len(visible_labels) - 1):
            l1, l2 = visible_labels[i:i + 2]
            x1, x2 = l1.GetPosition().x + l1.GetSize().x, l2.GetPosition().x
            x_avg = (x1 + x2) / 2
            separator_positions.append(x_avg)
        if visible_labels:
            l = self.labels[-1]
            separator_positions.append(l.GetPosition().x + l.GetSize().x + self.lspace)

        # Draw tab highlighting
        selected_tab = self.GetSelection()
        selected_sep = selected_tab - \
            sum([1 for index, label in enumerate(self.labels) if not label.IsShown() and index < selected_tab])
        x1 = separator_positions[selected_sep]
        x2 = separator_positions[selected_sep - 1] if selected_sep > 0 else 0
        tab_colour = self.tab_colours.get(selected_tab, self.panels[selected_tab].GetBackgroundColour())
        dc.SetBrush(wx.Brush(tab_colour))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangle(x2, 0, x1 - x2, self.GetSize().y)

        # Draw top separator
        dc.SetPen(wx.Pen(SEPARATOR_GREY))
        dc.DrawLine(0, 0, width, 0)

        # Draw separators between labels
        for i, x in enumerate(separator_positions):
            if i == selected_sep or i == selected_sep - 1:
                dc.DrawLine(x, 0, x, height)
            else:
                dc.DrawLine(x, self.lspace / 2, x, height - self.lspace / 2)


class TagText(wx.Panel):

    def __init__(self, parent, id=-1, label='', fill_colour=wx.Colour(240, 255, 204), edge_colour=wx.Colour(200, 200, 200), text_colour=wx.BLACK, **kwargs):
        wx.Panel.__init__(self, parent, id, **kwargs)
        self.fill_colour = fill_colour
        self.edge_colour = edge_colour
        self.text_colour = text_colour
        self.prnt_colour = parent.GetBackgroundColour()
        self.label = label
        w, h = self.GetTextExtent(self.label)
        w += 10
        self.SetMinSize((w, h))
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    def SetValue(self, label):
        self.label = label
        w, h = self.GetTextExtent(self.label)
        w += 10
        self.SetMinSize((w, h))
        self.Refresh()

    def SetBackgroundColour(self, colour):
        self.prnt_colour = colour
        self.Refresh()

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        # Draw the background
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.prnt_colour))
        dc.Clear()
        if getattr(self.GetParent(), 'bitmap', None):
            rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
            sub = self.GetParent().bitmap.GetSubBitmap(rect)
            dc.DrawBitmap(sub, 0, 0)

        # Draw the rounded rectangle which will contain the text.
        gc = wx.GraphicsContext.Create(dc)
        x, y, width, height = self.GetClientRect()
        gc.SetBrush(wx.Brush(self.fill_colour))
        gc.SetPen(wx.Pen(self.edge_colour, 1, wx.SOLID))
        path = gc.CreatePath()
        path.AddRoundedRectangle(x, y, width - 1, height - 1, 5)
        path.CloseSubpath()
        gc.DrawPath(path)

        # Draw the text
        font = self.GetFont()
        dc.SetFont(font)
        dc.SetTextForeground(self.text_colour)
        dc.DrawText(self.label, 5, 0)


class TorrentStatus(wx.Panel):

    def __init__(self, parent, id=-1, status='Initializing', fill_colour=wx.Colour(132, 194, 255), back_colour=wx.Colour(235, 235, 235), **kwargs):
        wx.Panel.__init__(self, parent, id, **kwargs)
        self.status = status
        self.value = None
        self.fill_colour = fill_colour
        self.back_colour = back_colour
        self.prnt_colour = parent.GetBackgroundColour()
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    def SetMinSize(self, size):
        w, h = size
        if w == -1:
            w = self.GetSize()[0]
        if h == -1:
            h = self.GetTextExtent(self.status)[1]
        wx.Panel.SetMinSize(self, (w, h))

    def SetValue(self, value):
        if isinstance(value, float) or isinstance(value, int):
            self.value = float(value)

    def SetStatus(self, status):
        if isinstance(status, str):
            self.status = status

        if status.endswith('Seeding'):
            self.fill_colour = SEEDING_COLOUR
        if status == 'Completed':
            self.fill_colour = COMPLETED_COLOUR
        if status in ['Fetching torrent', 'Waiting', 'Checking']:
            self.fill_colour = self.back_colour
        if status in ['Building circuits', 'Downloading', 'Streaming']:
            self.fill_colour = DOWNLOADING_COLOUR
        if status == 'Stopped':
            self.fill_colour = STOPPED_COLOUR

        self.SetMinSize((-1, -1))

    def SetBackgroundColour(self, colour):
        self.prnt_colour = colour
        self.Refresh()

    def Update(self, torrent):
        progress = torrent.progress
        torrent_state = torrent.state
        finished = progress == 1.0
        is_vod = torrent.ds.get_download().get_mode() == DLMODE_VOD if torrent.ds else False
        hidden = torrent.ds.get_download().get_def().is_anonymous()

        if torrent.ds.status == 2 or 'checking' in torrent_state:
            status = 'Checking'
        elif 'circuits' in torrent_state:
            if hidden:
                status = 'Building End to End'
            else:
                status = 'Building circuits'
        elif 'metadata' in torrent_state:
            status = 'Fetching torrent'
        elif 'seeding' in torrent_state:
            status = 'Seeding'
            if hidden:
                status = 'Hidden Seeding'
            if torrent.ds and UserDownloadChoice.get_singleton().get_download_state(torrent.ds.get_download().get_def().get_infohash()) == 'restartseed':
                status = "[F] " + status
        elif finished:
            status = 'Completed'
        elif 'allocating' in torrent_state:
            status = 'Waiting'
        elif 'downloading' in torrent_state:
            status = 'Streaming' if is_vod else 'Downloading'
            if hidden:
                status = "Hidden " + status
        elif 'error' in torrent_state:
            status = 'Stopped on error'
        elif 'stopped' in torrent_state:
            status = 'Stopped'
        else:
            status = 'Unknown'

        self.SetValue(progress)
        self.SetStatus(status)
        self.Refresh()
        if self.value is not None:
            return int(self.value * self.GetSize().width)
        return 0

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        # Draw the background
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.prnt_colour))
        dc.Clear()
        if getattr(self.GetParent(), 'bitmap', None):
            rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
            sub = self.GetParent().bitmap.GetSubBitmap(rect)
            dc.DrawBitmap(sub, 0, 0)

        # Draw an empty progress bar and text
        gc = wx.GraphicsContext.Create(dc)
        x, y, width, height = self.GetClientRect()
        gc.SetBrush(wx.Brush(self.back_colour))
        gc.SetPen(wx.TRANSPARENT_PEN)
        path = gc.CreatePath()
        path.AddRoundedRectangle(x, y, width, height, 2)
        path.CloseSubpath()
        gc.DrawPath(path)
        self.TextToDC(dc, self.TextColour(self.back_colour))

        if self.value is not None:
            # Draw a full progress bar and text
            rect = wx.EmptyBitmap(width, height)
            rect_dc = wx.MemoryDC(rect)
            rect_dc.SetBackground(wx.Brush(self.prnt_colour))
            rect_dc.Clear()

            rect_gc = wx.GraphicsContext.Create(rect_dc)
            rect_gc.SetBrush(wx.Brush(self.fill_colour))
            rect_gc.SetPen(wx.TRANSPARENT_PEN)
            path = rect_gc.CreatePath()
            path.AddRoundedRectangle(x, y, width, height, 2)
            path.CloseSubpath()
            rect_gc.DrawPath(path)
            self.TextToDC(rect_dc, self.TextColour(self.fill_colour))

            # Combine the two dc's
            dc.Blit(0, 0, int(self.value * width), height, rect_dc, 0, 0)
            rect_dc.SelectObject(wx.NullBitmap)

    def TextToDC(self, dc, colour):
        font = self.GetFont()
        dc.SetFont(font)
        dc.SetTextForeground(colour)
        if self.value is None or len(self.status) > 11:
            todraw = self.status
        else:
            todraw = "%s %.1f%%" % (self.status, self.value * 100)
        dc.DrawLabel(todraw, self.GetClientRect(), alignment=wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL)

    def TextColour(self, bg):
        rgb = bg.Get()
        brightness = (rgb[0] + rgb[1] + rgb[2]) / 3
        return wx.Colour(80, 80, 80) if brightness > 150 else wx.WHITE


class TransparentText(wx.StaticText):

    def __init__(self, parent, id=wx.ID_ANY, label='', pos=wx.DefaultPosition, size=wx.DefaultSize, style=wx.TRANSPARENT_WINDOW):
        wx.StaticText.__init__(self, parent, id, label, pos, size, style)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def SetLabel(self, value):
        size = self.GetTextExtent(value)
        self.SetSize(size)
        wx.StaticText.SetLabel(self, value)

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        dc.SetFont(self.GetFont())
        dc.SetTextForeground(self.GetForegroundColour())
        dc.DrawLabel(self.GetLabel(), self.GetClientRect())

    def OnSize(self, event):
        self.Refresh()
        event.Skip()


class TransparentStaticBitmap(wx.StaticBitmap):

    def __init__(self, *args, **kwargs):
        wx.StaticBitmap.__init__(self, *args, **kwargs)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def OnPaint(self, event):
        # Use double duffered drawing to prevent flickering
        dc = wx.BufferedPaintDC(self)
        if not getattr(self.GetParent(), 'bitmap', None):
            # Draw the background using the backgroundcolour
            dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
            dc.Clear()
        else:
            # Draw the background using the bitmap from the parent
            rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
            if rect.x > 0 and rect.y > 0:
                sub = self.GetParent().bitmap.GetSubBitmap(rect)
                dc.DrawBitmap(sub, 0, 0)
        # Draw the bitmap using a gc (dc doesn't do transparency very well)
        bitmap = self.GetBitmap()
        gc = wx.GraphicsContext.Create(dc)
        gc.DrawBitmap(bitmap, 0, 0, *bitmap.GetSize())

    def OnSize(self, event):
        self.Refresh()
        event.Skip()


class TextCtrl(wx.TextCtrl):

    def __init__(self, *args, **kwargs):
        wx.TextCtrl.__init__(self, *args, **kwargs)
        self.descr_label = ''
        self.descr_shown = False
        self.descr_colour = wx.Colour(80, 80, 80)
        self.Bind(wx.EVT_CHILD_FOCUS, self.OnGetFocus)
        self.Bind(wx.EVT_SET_FOCUS, self.OnGetFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)

    def SetDescriptiveText(self, descr_label):
        self.descr_label = descr_label
        self._SetDescriptiveText()

    def _SetDescriptiveText(self):
        if not self.GetValue():
            wx.TextCtrl.SetValue(self, self.descr_label)
            self.SetForegroundColour(self.descr_colour)
            self.descr_shown = True

    def GetValue(self):
        if self.descr_shown:
            return ''
        return wx.TextCtrl.GetValue(self)

    def SetValue(self, value):
        if value:
            self.descr_shown = False
            wx.TextCtrl.SetValue(self, value)

    def OnGetFocus(self, event):
        if self.descr_shown:
            wx.TextCtrl.SetValue(self, '')
        self.SetForegroundColour(self.GetParent().GetForegroundColour())
        self.descr_shown = False

    def OnKillFocus(self, event):
        self._SetDescriptiveText()


class StaticBitmaps(wx.Panel):

    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        self.bitmaps_index = 0
        self.SetPositions()
        self.Reset()
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    def SetPositions(self):
        width, height = self.GetSize()
        self.buttons = [wx.Rect(width - 27, height - 15, 14, 15),
                        wx.Rect(width - 14, height - 15, 14, 15)]
        self.pointer = wx.Rect(width - 26, 1, 25, 14)

    def OnEraseBackground(self, event):
        pass

    def OnMouse(self, event):
        if event.Entering() or event.Leaving():
            self.show_buttons = event.Entering()
            self.Refresh()

        elif event.LeftUp():
            if self.buttons[0].Contains(event.GetPosition()):
                return self.OnLeftButton()
            elif self.buttons[1].Contains(event.GetPosition()):
                return self.OnRightButton()

        event.Skip()

    def OnLeftButton(self):
        if self.bitmaps_index >= 0:
            self.bitmaps_index = self.bitmaps_index - 1 if self.bitmaps_index > 0 else len(self.bitmaps) - 1
            self.bitmap = self.bitmaps[self.bitmaps_index]
            self.Refresh()

    def OnRightButton(self):
        if self.bitmaps_index >= 0:
            self.bitmaps_index = self.bitmaps_index + 1 if self.bitmaps_index < len(self.bitmaps) - 1 else 0
            self.bitmap = self.bitmaps[self.bitmaps_index]
            self.Refresh()

    def SetBitmaps(self, bitmaps):
        if isinstance(bitmaps, list) and bitmaps:
            if self.bitmaps_index >= len(bitmaps):
                self.bitmaps_index = 0
            self.bitmaps = bitmaps
            self.bitmap = bitmaps[self.bitmaps_index]
            self.SetSize(self.bitmap.GetSize())
            self.SetPositions()
        else:
            self.Reset()
        self.Refresh()

    def Reset(self):
        self.bitmap_index = -1
        self.bitmaps = []
        self.bitmap = None
        self.show_buttons = False

    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        dc.Clear()

        if not self.bitmap:
            return

        dc.DrawBitmap(self.bitmap, 0, 0)

        if self.show_buttons:
            tmpbmp = wx.EmptyBitmapRGBA(*self.buttons[0].GetSize(), red=255, green=255, blue=255, alpha=155)
            dc.DrawBitmap(tmpbmp, self.buttons[0].x, self.buttons[0].y)
            dc.DrawBitmap(tmpbmp, self.buttons[1].x, self.buttons[1].y)

            dc.SetPen(wx.BLACK_PEN)
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRoundedRectangleRect(self.buttons[0], 0)
            dc.DrawRoundedRectangleRect(self.buttons[1], 0)

            arrow = GuiImageManager.getInstance().getBitmap(self, u"arrow", wx.WHITE, state=0)
            arrow_left = arrow.ConvertToImage().Rotate90(True).ConvertToBitmap()
            arrow_right = arrow.ConvertToImage().Rotate90(False).ConvertToBitmap()
            dc.DrawBitmap(arrow_left, self.buttons[0].x + 5, self.buttons[0].y + 4)
            dc.DrawBitmap(arrow_right, self.buttons[1].x + 5, self.buttons[1].y + 4)

            tmpbmp = wx.EmptyBitmapRGBA(*self.pointer.GetSize(), red=255, green=255, blue=255, alpha=155)
            dc.DrawBitmap(tmpbmp, self.pointer.x, self.pointer.y)
            dc.SetFont(self.GetFont())
            dc.DrawLabel("%d/%d" % (self.bitmaps_index + 1, len(self.bitmaps)),
                         self.pointer, alignment=wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL)


class Graph(wx.Panel):

    def __init__(self, parent, grid_size=4, max_points=120, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.x_margins = (30, 10)
        self.y_margins = (10, 20)
        self.max_range = 0
        self.grid_size = grid_size
        self.config = []
        self.data = []
        self.font = self.GetFont()
        self.font.SetPointSize(self.font.GetPointSize() - 1)
        self.SetAxisLabels("", "")
        self.SetMaxPoints(max_points)
        self.SetBackgroundColour(wx.WHITE)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def SetAxisLabels(self, x_label, y_label):
        self.x_label = x_label
        self.y_label = y_label

    def SetMaxPoints(self, max_points):
        self.max_points = max_points

    def AddGraph(self, colour, data=[], label=""):
        self.data.append(data)
        self.data[-1] = self.data[-1][-self.max_points:]
        self.config.append((colour, label))
        self.max_range = max(self.max_range, max(self.data[-1]) if self.data[-1] else 0)
        self.Refresh()

    def SetData(self, graph_id, data):
        self.data[graph_id] = data
        self.data[graph_id] = self.data[graph_id][-self.max_points:]
        self.max_range = max([max(column) for column in self.data if column])
        self.Refresh()

    def AppendData(self, graph_id, value):
        self.data[graph_id].append(value)

        dropped_value = None
        if len(self.data[graph_id]) > self.max_points:
            dropped_value = self.data[graph_id][0]
            self.data[graph_id] = self.data[graph_id][-self.max_points:]

        if dropped_value is not None and dropped_value == self.max_range:
            self.max_range = max([max(column) for column in self.data if column])
        else:
            self.max_range = max(self.max_range, value)
        self.Refresh()

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        _, _, width, height = self.GetClientRect()
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        self.DrawAxis(dc, width, height)
        self.DrawGrid(dc, width, height)
        self.DrawText(dc, width, height)

        gc = wx.GraphicsContext.Create(dc)
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        self.DrawGraphs(gc, width, height)
        self.DrawLegend(gc, dc, width, height)

    def DrawAxis(self, dc, width, height):
        dc.SetPen(wx.Pen((175, 175, 175), 1, wx.SOLID))
        dc.DrawLine(self.x_margins[0], height - self.y_margins[1], self.x_margins[0], self.y_margins[0])
        dc.DrawLine(self.x_margins[0], height - self.y_margins[
                    1], width - self.x_margins[1], height - self.y_margins[1])

    def DrawGrid(self, dc, width, height):
        dashed_pen = wx.Pen((175, 175, 175), 1, wx.USER_DASH)
        dashed_pen.SetDashes([4, 4])
        dc.SetPen(dashed_pen)
        grid_height = (height - self.y_margins[0] - self.y_margins[1]) / self.grid_size
        for i in range(1, self.grid_size + 1):
            dc.DrawLine(self.x_margins[0], height - self.y_margins[
                        1] - i * grid_height, width - self.x_margins[1], height - self.y_margins[1] - i * grid_height)

    def DrawText(self, dc, width, height):
        dc.SetFont(self.font)
        dc.SetTextForeground(wx.Colour(130, 130, 130))

        # Draw labels along the x/y axis
        x_width, _ = self.GetTextExtent(self.x_label)
        _, y_height = self.GetTextExtent(self.y_label)
        dc.DrawText(self.x_label, (width - self.x_margins[0] - self.x_margins[
                    1] - x_width) / 2 + self.x_margins[0], height - self.y_margins[1])
        dc.DrawRotatedText(self.y_label, self.x_margins[0] - y_height, (
            height - self.y_margins[0] - self.y_margins[1]) / 2 + self.y_margins[1], 90)

        # Draw min/max values along the y axis
        miny = "0"
        maxy = str(int(self.max_range + 1))
        miny_width, miny_height = self.GetTextExtent(miny)
        maxy_width, maxy_height = self.GetTextExtent(maxy)
        dc.DrawText(miny, max(0, self.x_margins[0] - miny_width), height - self.y_margins[1] - miny_height / 2)
        dc.DrawText(maxy, max(0, self.x_margins[0] - maxy_width), self.y_margins[0] - maxy_height / 2)

    def DrawGraphs(self, gc, width, height):
        for graph_id, column in enumerate(self.data):
            if column:
                colour, _ = self.config[graph_id]
                gc.SetPen(wx.Pen(colour, 1, wx.SOLID))
                num_points = len(column)
                x_coords = [self.x_margins[0] + (i / float(self.max_points)) * (
                    width - self.x_margins[0] - self.x_margins[1]) for i in range(0, num_points)]
                if self.max_range != 0:
                    y_coords = [height - self.y_margins[1] - (
                        (height - self.y_margins[0] - self.y_margins[1]) * column[i] / self.max_range) for i in range(0, num_points)]
                else:
                    y_coords = [height - self.y_margins[1] for i in range(0, num_points)]
                y_coords = [min(height - self.y_margins[1] - 1, y_coord) for y_coord in y_coords]
                gc.DrawLines(zip(x_coords, y_coords))

    def DrawLegend(self, gc, dc, width, height):
        gc.SetFont(self.font)
        gc.SetPen(wx.Pen(wx.Colour(240, 240, 240, 200)))
        gc.SetBrush(wx.Brush(wx.Colour(245, 245, 245, 150)))

        rect_width = max([self.GetTextExtent(label)[0] for _, label in self.config]) + 30
        rect_height = sum([self.GetTextExtent(label)[1] for _, label in self.config]) + 10
        gc.DrawRectangle(self.x_margins[0] + 5, self.x_margins[1] + 5, rect_width, rect_height)

        next_y = self.y_margins[0] + 10
        for colour, label in self.config:
            label_width, label_height = self.GetTextExtent(label)
            gc.SetPen(wx.Pen(colour, 1, wx.SOLID))
            gc.DrawLines(
                [(self.x_margins[0] + 10, next_y + label_height / 2), (self.x_margins[0] + 25, next_y + label_height / 2)])
            # Drawing text with a gc looks a bit weird on Ubuntu, using dc instead.
            dc.SetTextForeground(wx.Colour(100, 100, 100))
            dc.DrawText(label, self.x_margins[0] + 30, next_y)
            next_y += label_height

    def OnSize(self, event):
        self.Refresh()
        event.Skip()


class VideoProgress(wx.Panel):

    def __init__(self, parent, id=-1, label='Loading\n 0%', value=0.0, fill_colour=wx.Colour(220, 220, 220), edge_colour=wx.Colour(210, 210, 210), text_colour=wx.Colour(210, 210, 210), **kwargs):
        wx.Panel.__init__(self, parent, id, **kwargs)
        self.fill_colour = fill_colour
        self.edge_colour = edge_colour
        self.text_colour = text_colour
        self.prnt_colour = parent.GetBackgroundColour()
        self.label = label
        self.value = 0.0
        self.error = ''
        self.SetValue(value)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    def SetValue(self, value):
        self.value = value
        self.Refresh()

    def SetError(self, error):
        self.error = error

    def SetLabel(self, label):
        self.label = label
        self.Refresh()

    def SetBackgroundColour(self, colour):
        self.prnt_colour = colour
        self.Refresh()

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.prnt_colour))
        dc.Clear()

        gc = wx.GraphicsContext.Create(dc)
        width, height = self.GetClientSize()
        radius = min(width - 5, height - 5) / 2
        pi = math.pi

        path = gc.CreatePath()
        path.AddCircle(0, 0, radius)
        path.AddCircle(0, 0, radius / 1.5)
        gc.PushState()
        gc.Translate(width / 2, height / 2)
        gc.SetBrush(wx.Brush(wx.Colour(180, 180, 180)))
        gc.SetPen(wx.Pen(self.edge_colour, 1, wx.SOLID))
        gc.DrawPath(path)

        if not self.error:
            path = gc.CreatePath()
            path.AddArc(0, 0, radius, -pi / 2, -pi / 2 + self.value * 2 * pi, True)
            x = self.value * 2 * pi - (pi / 2)
            path.AddLineToPoint(math.cos(x) * radius / 1.5, math.sin(x) * radius / 1.5)
            path.AddArc(0, 0, radius / 1.5, -pi / 2 + self.value * 2 * pi, -pi / 2, False)
            path.CloseSubpath()
            gc.PopState()
            gc.PushState()
            gc.Translate(width / 2, height / 2)
            gc.SetBrush(gc.CreateRadialGradientBrush(0, 0, 0, 0, radius, wx.Colour(255, 255, 255), self.fill_colour))
            gc.SetPen(wx.Pen(self.edge_colour, 1, wx.SOLID))
            gc.DrawPath(path)

        font = self.GetFont()
        font.SetPixelSize((0, radius / 3.5))
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        dc.SetTextForeground(self.text_colour)
        dc.DrawLabel(self.error or self.label, self.GetClientRect(),
                     alignment=wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL)


class VideoSlider(wx.Panel):

    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        self.slider_range = [10, 0]
        self.slider_radius = 9
        self.slider_position = [10, 0]
        # Colours for enabled slider
        self.colour1 = wx.Colour(241, 93, 63)
        self.colour2 = wx.Colour(246, 144, 119)
        # Colours for disabled slider
        self.colour3 = wx.Colour(170, 170, 170)
        self.colour4 = wx.Colour(220, 220, 220)
        self.dragging = False
        self.enabled = True
        self.hovering = False
        self.value = 0.0
        self.pieces = []
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value
        if not self.dragging:
            slider_width = self.slider_range[1] - self.slider_range[0]
            self.slider_position[0] = (slider_width * self.value) + self.slider_range[
                0] if slider_width else self.slider_range[0]
            self.slider_position[0] = min(self.slider_range[1], self.slider_position[0])
            self.slider_position[0] = max(self.slider_range[0], self.slider_position[0])
            self.Refresh()

    def SetPieces(self, pieces):
        self.pieces = pieces
        self.Refresh()

    def PositionOnSlider(self, position=None):
        x, y = position or self.ScreenToClient(wx.GetMousePosition())
        return (x - self.slider_position[0]) ** 2 + (y - self.slider_position[1]) ** 2 < self.slider_radius ** 2

    def OnLeftDown(self, event):
        self.SetSlider(event)
        if self.PositionOnSlider(event.GetPositionTuple()):
            self.dragging = True
            self.CaptureMouse()

    def OnLeftUp(self, event):
        self.dragging = False
        self.SetValue(float(self.slider_position[0] - self.slider_range[0]) / (
            self.slider_range[1] - self.slider_range[0]))
        if self.HasCapture():
            self.ReleaseMouse()
        # Call parent
        self.GetParent().GetParent().Seek()

    def OnMotion(self, event):
        if event.LeftIsDown():
            self.SetSlider(event)
        if self.hovering != self.PositionOnSlider(event.GetPositionTuple()):
            self.Refresh()

    def SetSlider(self, event):
        mx = event.GetPositionTuple()[0]
        if mx > self.slider_range[0] and mx < self.slider_range[1]:
            self.slider_position[0] = mx
            self.Refresh()

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, evt):
        # Draw the background
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        if hasattr(self.GetParent(), 'bitmap'):
            if not self.GetParent().bitmap:
                wx.CallLater(100, self.Refresh)
            else:
                rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
                sub = self.GetParent().bitmap.GetSubBitmap(rect)
                dc.DrawBitmap(sub, 0, 0)

        width, height = self.GetClientSize()
        gc = wx.GraphicsContext.Create(dc)
        self.slider_range = [10, width - 10]
        self.slider_position[1] = height / 2
        rect_height = height / 4

        # Draw background rectangle
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(self.colour4))
        gc.DrawRectangle(self.slider_range[0],
                         height / 2 - rect_height / 2,
                         self.slider_range[1] - self.slider_range[0],
                         rect_height)

        # Draw buffer rectangle
        if self.pieces:
            gc.SetBrush(wx.Brush(self.colour3))
            slider_width = self.slider_range[1] - self.slider_range[0]
            num_pieces = len(self.pieces)
            piece_width = slider_width / float(num_pieces)
            from_piece = to_piece = int(self.value * slider_width / piece_width)
            while to_piece < num_pieces and self.pieces[to_piece]:
                to_piece += 1
            gc.DrawRectangle(self.slider_range[0] + from_piece * piece_width,
                             height / 2 - rect_height / 2,
                             (to_piece - from_piece) * piece_width,
                             rect_height)

        # Draw position rectangle
        gc.SetBrush(wx.Brush(self.colour1))
        gc.DrawRectangle(self.slider_range[0],
                         height / 2 - rect_height / 2,
                         self.slider_position[0] - self.slider_range[0],
                         rect_height)

        # Draw slider
        if self.IsEnabled():
            gc.SetBrush(gc.CreateLinearGradientBrush(self.slider_position[
                        0] - self.slider_radius, 0, self.slider_position[0] + self.slider_radius, 0, self.colour1, self.colour2))
            path = gc.CreatePath()
            path.AddCircle(self.slider_position[0], self.slider_position[1], self.slider_radius)
            gc.DrawPath(path)
            self.hovering = self.PositionOnSlider()
            gc.SetBrush(wx.TRANSPARENT_BRUSH if self.hovering or self.dragging else wx.Brush(wx.Colour(244, 244, 244)))
            path = gc.CreatePath()
            path.AddCircle(self.slider_position[0], self.slider_position[1], self.slider_radius / 2)
            gc.DrawPath(path)
        else:
            gc.SetBrush(gc.CreateLinearGradientBrush(0, 0, self.slider_radius * 2, 0, self.colour3, self.colour4))
            path = gc.CreatePath()
            path.AddCircle(self.slider_position[0], self.slider_position[1], self.slider_radius)
            gc.DrawPath(path)

    def Enable(self, enable):
        if enable:
            self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
            self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
            self.Bind(wx.EVT_MOTION, self.OnMotion)
        elif not enable:
            self.Unbind(wx.EVT_LEFT_UP)
            self.Unbind(wx.EVT_LEFT_DOWN)
            self.Unbind(wx.EVT_MOTION)
        self.enabled = enable
        self.Refresh()

    def IsEnabled(self):
        return self.enabled


class VideoVolume(wx.Panel):

    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        self.value = 0
        self.handler = None
        self.dragging = False

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)

    def PositionOnTriangle(self, position=None):
        x, y = position or self.ScreenToClient(wx.GetMousePosition())
        w, h = self.GetClientSize()
        return y > h - (x * h / w)

    def OnLeftDown(self, event):
        self.SetPosition(event)
        if self.PositionOnTriangle(event.GetPositionTuple()):
            self.dragging = True
            self.CaptureMouse()

    def OnLeftUp(self, event):
        self.dragging = False
        if self.HasCapture():
            self.ReleaseMouse()

    def OnMotion(self, event):
        if event.LeftIsDown():
            self.SetPosition(event)

    def SetPosition(self, event):
        mx, _ = event.GetPosition()
        value = float(mx) / self.GetClientSize().x
        if self.value != value and self.handler:
            self.handler(value)
        self.value = value
        self.Refresh()

    def SetVolumeHandler(self, handler):
        self.handler = handler

    def SetValue(self, value):
        self.value = min(max(0.0, value), 1.0)
        self.Refresh()

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        # Draw the background
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        if hasattr(self.GetParent(), 'bitmap'):
            if not self.GetParent().bitmap:
                wx.CallLater(100, self.Refresh)
            else:
                rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
                sub = self.GetParent().bitmap.GetSubBitmap(rect)
                dc.DrawBitmap(sub, 0, 0)

        w, h = self.GetClientSize()

        gc = wx.GraphicsContext.Create(dc)

        if self.value > 0.0:
            path = gc.CreatePath()
            path.MoveToPoint(0, h - 1)
            path.AddLineToPoint(self.value * w, h - 1)
            path.AddLineToPoint(self.value * w, (1 - self.value) * h)
            path.AddLineToPoint(0, h - 1)
            path.CloseSubpath()
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.SetBrush(gc.CreateLinearGradientBrush(0, 0, w, 0, wx.Colour(244, 172, 156), wx.Colour(241, 92, 62)))
            gc.DrawPath(path)

        path = gc.CreatePath()
        path.MoveToPoint(0, h - 1)
        path.AddLineToPoint(w - 1, h - 1)
        path.AddLineToPoint(w - 1, 0)
        path.AddLineToPoint(0, h - 1)
        path.CloseSubpath()
        gc.SetPen(wx.Pen(wx.Colour(241, 92, 62)))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawPath(path)


class AnonymityDialog(wx.Panel):

    def __init__(self, parent):
        super(AnonymityDialog, self).__init__(parent)

        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.exitnodes_chkbox = wx.CheckBox(self, -1, "Enable anonimity over exit nodes")
        font = self.exitnodes_chkbox.GetFont()
        font.SetWeight(wx.BOLD)
        self.exitnodes_chkbox.SetFont(font)
        self.exitnodes_chkbox.Bind(wx.EVT_CHECKBOX, self.OnExitnodesValueChanged)

        self.endtoend_chkbox = wx.CheckBox(self, -1, "Enable anonimity over hidden services")
        font = self.endtoend_chkbox.GetFont()
        font.SetWeight(wx.BOLD)
        self.endtoend_chkbox.SetFont(font)
        self.endtoend_chkbox.Bind(wx.EVT_CHECKBOX, self.OnEndToEndValueChanged)

        # Add slider
        self._lbls = []
        self.labels = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(self, -1, 'High speed\nMinimum anonymity', style=wx.ALIGN_CENTRE_HORIZONTAL)
        self._lbls.append(lbl)
        self.labels.Add(lbl)
        self.labels.AddStretchSpacer()
        lbl = wx.StaticText(self, -1, 'Low speed\nStrong anonymity', style=wx.ALIGN_CENTRE_HORIZONTAL)
        self._lbls.append(lbl)
        self.labels.Add(lbl)

        self.slider_images = [GuiImageManager.getInstance().getImage(u"scale_%d.png" % i) for i in range(6)]
        self.slider_bitmap = wx.StaticBitmap(self, -1, self.slider_images[0])

        self.slider = wx.Slider(self, -1, 1, 1, 3, wx.DefaultPosition, style=wx.SL_AUTOTICKS | wx.SL_HORIZONTAL)
        self.slider.Bind(wx.EVT_SLIDER, self.OnSlide)

        hop_count = wx.BoxSizer(wx.HORIZONTAL)
        hop_count.AddSpacer((10, -1))
        for count in xrange(1, 4):
            lbl = wx.StaticText(self, -1, '%d' % count, style=wx.ALIGN_CENTRE_HORIZONTAL)
            self._lbls.append(lbl)
            hop_count.Add(lbl)
            if count != 3:
                hop_count.AddStretchSpacer()
            else:
                hop_count.AddSpacer((10, -1))

        labels_and_slider = wx.BoxSizer(wx.VERTICAL)
        labels_and_slider.Add(self.labels, 0, wx.EXPAND)
        labels_and_slider.Add(self.slider, 0, wx.EXPAND)
        labels_and_slider.Add(hop_count, 0, wx.EXPAND)

        slider_sizer = wx.BoxSizer(wx.HORIZONTAL)
        slider_sizer.Add(labels_and_slider, 1, wx.RIGHT, 10)
        slider_sizer.Add(self.slider_bitmap)

        vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.BOTTOM, 10)
        vSizer.Add(self.exitnodes_chkbox, 0, wx.EXPAND | wx.BOTTOM, 10)
        vSizer.Add(self.endtoend_chkbox, 0, wx.EXPAND | wx.BOTTOM, 10)
        self.st = wx.StaticText(self, -1, 'Please select how anonymous you want to download:')
        _set_font(self.st, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(self.st, 0, wx.EXPAND | wx.BOTTOM, 10)
        vSizer.Add(slider_sizer, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        self.SetSizer(vSizer)

        self.exitnodes_chkbox.SetValue(False)
        self.endtoend_chkbox.SetValue(False)
        self.OnEndToEndValueChanged(None)
        self.OnExitnodesValueChanged(None)

    def OnSlide(self, event):
        self.slider_bitmap.SetBitmap(self.slider_images[self.slider.GetValue()])

    def OnEndToEndValueChanged(self, event):
        to_show = self.endtoend_chkbox.GetValue()
        self.slider.Show(False)
        self.slider_bitmap.Show(False)
        self.st.Show(False)
        self.exitnodes_chkbox.SetValue(False)
        for lbl in self._lbls:
            lbl.Show(False)

    def OnExitnodesValueChanged(self, event):
        to_show = self.exitnodes_chkbox.GetValue()
        self.slider.Show(to_show)
        self.slider_bitmap.Show(to_show)
        self.st.Show(to_show)
        self.endtoend_chkbox.SetValue(False)
        for lbl in self._lbls:
            lbl.Show(to_show)

        self.Layout()
        self.GetParent().Layout()

    def GetExitnodesHops(self):
        return self.slider.GetValue() if self.exitnodes_chkbox.GetValue() else 0

    def SetExitnodesHops(self, value):
        if value == 0:
            self.exitnodes_chkbox.SetValue(False)
        else:
            self.exitnodes_chkbox.SetValue(True)
            self.slider.SetValue(value)

    def GetEndToEndValue(self):
        return self.endtoend_chkbox.GetValue()

    def SetEndToEndValue(self, value):
        self.endtoend_chkbox.SetValue(value)
