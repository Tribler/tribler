import wx
import sys

from wx.lib import masked

#from Utility.compat import convertINI


################################################################
#
# Class: ColumnsDialog
#
# Allows a user to alter the settings and appearance of 
# columns in a ManagedList.
#
################################################################
class ColumnsDialog(wx.Dialog):
    def __init__(self, list):
        
        self.utility = list.utility
        
        title = self.utility.lang.get('columns')
        
        pre = wx.PreDialog()
        pre.Create(list, -1, title)
        self.this = pre.this

        outerbox = wx.BoxSizer(wx.VERTICAL)
        
        self.columnsPanel = ColumnsPanel(self, list)
        
        applybtn  = wx.Button(self, -1, self.utility.lang.get('apply'))
        self.Bind(wx.EVT_BUTTON, self.onApply, applybtn)
        
        okbtn  = wx.Button(self, -1, self.utility.lang.get('ok'))
        self.Bind(wx.EVT_BUTTON, self.onOK, okbtn)
        
        cancelbtn = wx.Button(self, wx.ID_CANCEL, self.utility.lang.get('cancel'))
        
#        setDefaultsbtn = wx.Button(self, -1, self.utility.lang.get('reverttodefault'))
        
        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        buttonbox.Add(applybtn, 0, wx.ALL, 5)
        buttonbox.Add(okbtn, 0, wx.ALL, 5)
        buttonbox.Add(cancelbtn, 0, wx.ALL, 5)
        
        outerbox.Add(self.columnsPanel, 0, wx.EXPAND|wx.ALL, 5)
        outerbox.Add(buttonbox, 0, wx.ALIGN_CENTER)
       
        self.SetAutoLayout(True)
        self.SetSizer(outerbox)
        self.Fit()
        
    def onOK(self, event = None):
        if self.onApply(event):
            self.EndModal(wx.ID_OK)
        
    def onApply(self, event = None):
        self.columnsPanel.apply()
        return True


################################################################
#
# Class: ColumnsPanel
#
# Contains the interface elements for a ColumnsDialog
#
################################################################
class ColumnsPanel(wx.Panel):
    def __init__(self, parent, list):
        wx.Panel.__init__(self, parent, -1)
        
        # Constants
        self.RANK = 0
        self.COLID = 1
        self.TEXT = 2
        self.WIDTH = 3

        self.utility = parent.utility
        
        self.list = list
        self.columns = list.columns
        
        self.changed = False
        
        self.changingvalue = False

        self.leftid = []
        self.rightid = []
        self.leftindex = -1
        self.rightindex = -1
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        listsizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # unselected list ctrl
       
        self.checklistbox = wx.CheckListBox(self, -1, size = wx.Size(150, 200), style = wx.LB_SINGLE)

        listsizer.Add(self.checklistbox, 0, wx.ALL, 5)

        # Up & Down button
        ###################        
        self.upbutton = self.utility.makeBitmapButton(self, 'moveup.bmp', 'move_up', self.OnMove)
        self.downbutton = self.utility.makeBitmapButton(self, 'movedown.bmp', 'move_down', self.OnMove)

        updownsizer = wx.BoxSizer(wx.VERTICAL)
        
        updownsizer.Add(self.upbutton, 0, wx.BOTTOM, 5)
        updownsizer.Add(self.downbutton, 0, wx.TOP, 5)
        
        listsizer.Add(updownsizer, 0, wx.ALL, 5)
        
        sizer.Add(listsizer, 0)
        
        labelbox = wx.BoxSizer(wx.HORIZONTAL)
        labelbox.Add(wx.StaticText(self, -1, self.utility.lang.get('displayname')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        columnlabel = ""
        self.labelsetting = wx.TextCtrl(self, -1, columnlabel)
        labelbox.Add(self.labelsetting, 0, wx.ALIGN_CENTER_VERTICAL)
        
        sizer.Add(labelbox, 0, wx.ALL, 5)
        
        widthbox = wx.BoxSizer(wx.HORIZONTAL)
        widthbox.Add(wx.StaticText(self, -1, self.utility.lang.get('columnwidth')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        initialvalue = 0
        self.widthsetting = self.utility.makeNumCtrl(self, initialvalue, integerWidth = 4, max = 2000)
        widthbox.Add(self.widthsetting, 0, wx.ALIGN_CENTER_VERTICAL)
        
        sizer.Add(widthbox, 0, wx.ALL, 5)
               
        self.getDefaultValues()

        self.labelsetting.Enable(False)
        self.widthsetting.Enable(False)
        
        self.SetSizerAndFit(sizer)

        # Add Event
        #########################
        self.Bind(wx.EVT_LISTBOX, self.OnSelect, self.checklistbox)
        self.Bind(wx.EVT_TEXT, self.OnChangeLabel, self.labelsetting)
        self.Bind(masked.EVT_NUM, self.OnChangeWidth, self.widthsetting)

    def getDefaultValues(self):
        unselected = []
        
        selected = []

        for colid in range(self.columns.minid, self.columns.maxid):
            rank = self.utility.config.Read(self.list.prefix + str(colid) + "_rank", "int")
            text = self.utility.lang.get(self.list.prefix + str(colid) + "_text")
            width = self.utility.config.Read(self.list.prefix + str(colid) + "_width", "int")
            if colid in self.list.exclude:
                pass
            elif rank == -1:
                unselected.append([rank, colid, text, width])
            else:
                selected.append([rank, colid, text, width])
        
        unselected.sort()
        selected.sort()
        
        self.columnlist = selected + unselected
        
        self.checklistbox.Set([item[2] for item in self.columnlist])
        
        for i in range(len(self.columnlist)):
            if self.columnlist[i][0] != -1:
                self.checklistbox.Check(i)
    
    # Select one of the items in the list
    def OnSelect(self, event):
        # The index of the selection within the checklistbox
        index = self.checklistbox.GetSelection()
        if index == wx.NOT_FOUND:
            self.labelsetting.Enable(False)
            self.widthsetting.Enable(False)
            return
        self.labelsetting.Enable(True)
        self.widthsetting.Enable(True)
            
        textstring = self.checklistbox.GetString(index)

        self.changingvalue = True
        self.labelsetting.SetValue(textstring)
        self.widthsetting.SetValue(self.columnlist[index][self.WIDTH])
        self.changingvalue = False
        
    def OnChangeLabel(self, event):
        if self.changingvalue:
            return
        
        index = self.checklistbox.GetSelection()
        if index == wx.NOT_FOUND:
            return
        
        oldlabel = self.columnlist[index][self.TEXT]
        newlabel = self.labelsetting.GetValue()
        if oldlabel == newlabel:
            return
            
        self.columnlist[index][self.TEXT] = newlabel
        self.checklistbox.SetString(index, newlabel)
        
    def OnChangeWidth(self, event):
        if self.changingvalue:
            return
        
        index = self.checklistbox.GetSelection()
        if index == wx.NOT_FOUND:
            return
        
        self.columnlist[index][self.WIDTH] = self.widthsetting.GetValue()
    
    # Move a list item up or down           
    def OnMove(self, event):
        # Move up
        if event.GetId() == self.upbutton.GetId():
            direction = -1
        # Move down
        else:
            direction = 1
        
        index = self.checklistbox.GetSelection()
        if index == wx.NOT_FOUND:
            # Nothing is selected:
            return

        if (direction == 1) and (index == self.checklistbox.GetCount() - 1):
            #Last Item can't move down anymore
            return
        elif (direction == -1) and (index == 0):
            # First Item can't move up anymore
            return
        else:
            self.columnlist[index], self.columnlist[index + direction] = self.columnlist[index + direction], self.columnlist[index]

            col1text = self.checklistbox.GetString(index)
            col2text = self.checklistbox.GetString(index + direction)

            col1checked = self.checklistbox.IsChecked(index)
            col2checked = self.checklistbox.IsChecked(index + direction)

            #Update display
            self.checklistbox.SetString(index + direction, col1text)
            self.checklistbox.SetString(index, col2text)
            
            self.checklistbox.Check(index + direction, col1checked)
            self.checklistbox.Check(index, col2checked)
            
            self.checklistbox.SetSelection(index + direction)

    def apply(self):
        selected = 0
        for i in range(0, self.checklistbox.GetCount()):
            colid = self.columnlist[i][1]
            if self.checklistbox.IsChecked(i):
                self.columnlist[i][self.RANK] = selected
                selected += 1
            else:
                self.columnlist[i][self.RANK] = -1

        # Check to see if anything has changed
        overallchange = False                
        for item in self.columnlist:
            colid = item[self.COLID]

            rank = item[self.RANK]
            changed = self.utility.config.Write(self.list.prefix + str(colid) + "_rank", rank)
            if changed:
                overallchange = True
            
            changed = self.utility.lang.writeUser(self.list.prefix + str(colid) + "_text", item[self.TEXT])
            if changed:
                overallchange = True

            width = item[self.WIDTH]
            changed = self.utility.config.Write(self.list.prefix + str(colid) + "_width", width)
            if changed:
                overallchange = True

        # APPLY on-the-fly
        if overallchange:
            self.utility.config.Flush()
            self.utility.lang.flush()
            self.list.updateColumns()


################################################################
#
# Class: ColumnManager
#
# Keep track of the settings for order and appearance of
# columns in a ManagedList
#
################################################################
class ColumnManager:
    def __init__(self, list):
        self.utility = list.utility
        
        self.minid = list.minid
        self.maxid = list.maxid
        self.prefix = list.prefix
        
        self.exclude = list.exclude

        self.active = []
        
        self.getColumnData()

    # Method used to compare two elements of self.active
    def compareRank(self, a, b):
        if a[1] < b[1]:
            return -1
        if a[1] > b[1]:
            return 1
        else:
            return 0
        
    def getNumCol(self):
        return len(self.active)
        
    def getRankfromID(self, colid):
        return self.utility.config.Read(self.prefix + str(colid) + "_rank", "int")

    def getIDfromRank(self, rankid):
        return self.active[rankid][0]
    
    def getTextfromRank(self, rankid):
        colid = self.active[rankid][0]
        return self.utility.lang.get(self.prefix + str(colid) + "_text")
    
    def getValuefromRank(self, rankid):
        colid = self.active[rankid][0]
        return self.utility.config.Read(self.prefix + str(colid) + "_width", "int")

    def getColumnData(self):
        self.active = []

        # Get the list of active columns
        for colid in range(self.minid, self.maxid):
            rank = self.utility.config.Read(self.prefix + str(colid) + "_rank", "int")
            
            if (rank < 0 or colid in self.exclude):
                self.utility.config.Write(self.prefix + str(colid) + "_rank", -1)
            elif (rank > -1):
                self.active.append([colid, rank])
                
        # Sort the columns by rank
        self.active.sort(self.compareRank)
        
        # Make sure that the columns are in an order that makes sense
        # (i.e.: if we have a config with IDs of 4, 99, 2000 then
        #        we'll convert that to 0, 1, 2)
        for i in range(len(self.active)):
            colid = self.active[i][0]
            rank = i
            self.active[i][1] = rank
            self.utility.config.Write(self.prefix + str(colid) + "_rank", rank)
        self.utility.config.Flush()


################################################################
#
# Class: ManagedList
#
# An extension of wx.ListCtrl that keeps track of column
# settings in a unified manner.
#
################################################################       
class ManagedList(wx.ListCtrl):
    def __init__(self, parent, style, prefix, minid, maxid, exclude = [], rightalign = [], centeralign = []):        
        wx.ListCtrl.__init__(self, parent, -1, style = style)
        
        self.parent = parent
        
        self.prefix = prefix
        self.minid = minid
        self.maxid = maxid
        self.exclude = exclude
        
        self.rightalign = rightalign
        self.centeralign = centeralign
        
        self.utility = parent.utility
        
        self.columns = ColumnManager(self)
        
        self.Bind(wx.EVT_LIST_COL_END_DRAG, self.OnResizeColumn)
        self.Bind(wx.EVT_LIST_COL_RIGHT_CLICK, self.OnColRightClick)
        
        self.loadColumns()
        
        self.loadFont()
        
        # Add to the list of ManagedList objects
        self.utility.lists[self] = True
        
    def loadFont(self):
        # Get font information
        fontinfo = self.utility.config.Read('listfont', "bencode-fontinfo")
        font = self.utility.getFontFromInfo(fontinfo)

        # Only change if we've gotten an acceptable font
        if font.Ok():
            # Jump to the top of the list
            # self.EnsureVisible(0)    #_# remove this line to be compatible on linux
            # Change the font
            self.SetFont(font)
            # Refresh to make the change visable
            self.Refresh()

    def loadColumns(self):
        # Delete Old Columns (if they exist)
        #################################################
        numcol = self.GetColumnCount()
        for i in range(numcol):
            self.DeleteColumn(0)

        # Read status display
        ####################################
        
        for rank in range(self.columns.getNumCol()):
            colid = self.columns.getIDfromRank(rank)
            if colid in self.rightalign:
                style = wx.LIST_FORMAT_RIGHT
            elif colid in self.centeralign:
                style = wx.LIST_FORMAT_CENTER
            else:
                style = wx.LIST_FORMAT_LEFT
            text = self.columns.getTextfromRank(rank)
            width = self.columns.getValuefromRank(rank)
            # Don't allow a column to have a size of 0
            if width == 0:
                width = -1
            self.InsertColumn(rank, text, style, width)
        
        # Save the width of the column that was just resized
    def OnResizeColumn(self, event):
        if self.utility.config.Read('savecolumnwidth', "boolean"):
            rank = event.GetColumn()
            width = self.GetColumnWidth(rank)
            colid = self.columns.getIDfromRank(rank)
            self.utility.config.Write(self.prefix + str(colid) + "_width", width)
            self.utility.config.Flush()
            
    # Create a list of columns that are active/inactive
    def OnColRightClick(self, event):
        if not hasattr(self, "columnpopup"):
            self.makeColumnPopup()
            
        # Check off columns for all that are currently active
        for colid in range(self.minid, self.maxid):
            if colid in self.exclude:
                continue
            
            if self.utility.config.Read(self.prefix + str(colid) + "_rank", "int") > -1:
                self.columnpopup.Check(777 + colid, True)
            else:
                self.columnpopup.Check(777 + colid, False)
        
        self.lastcolumnselected = event.GetColumn()
               
        self.PopupMenu(self.columnpopup, event.GetPosition())
        
    def makeColumnPopup(self):
        self.columnpopup = wx.Menu()
        
        for colid in range(self.minid, self.maxid):
            if colid in self.exclude:
                continue
            
            text = self.utility.lang.get(self.prefix + str(colid) + '_text')
            self.columnpopup.Append(777 + colid, text, text, wx.ITEM_CHECK)
            
        self.columnpopup.AppendSeparator()
        
        self.utility.makePopup(self.columnpopup, self.onColumnDialog, 'more')

        startid = 777 + self.minid
        endid = 777 + (self.maxid - 1)

        self.Bind(wx.EVT_MENU, self.onSelectColumn, id=startid, id2=endid)
        
    def onColumnDialog(self, event = None):
        dialog = ColumnsDialog(self)
        dialog.ShowModal()
        dialog.Destroy()

    def onSelectColumn(self, event):
        eventid = event.GetId()
        colid = eventid - 777
        oldrank = self.utility.config.Read(self.prefix + str(colid) + "_rank", "int")

        if oldrank > -1:
            # Column was deselected, don't show it now
            # (update ranks for the rest of the columns that appeared after it)
            for i in range (self.minid, self.maxid):
                temprank = self.utility.config.Read(self.prefix + str(i) + "_rank", "int")
                if (i == colid):
                    self.utility.config.Write(self.prefix + str(i) + "_rank", -1)
                elif (temprank > oldrank):
                    self.utility.config.Write(self.prefix + str(i) + "_rank", temprank - 1)
                else:
                    self.utility.config.Write(self.prefix + str(i) + "_rank", temprank)
        else:
            # Column was selected, need to show it
            # Put it after the closest column
            if hasattr(self, 'lastcolumnselected'):
                newrank = self.lastcolumnselected + 1
            # (just tack it on the end of the display)
            else:
                newrank = self.GetColumnCount()
            
            for i in range (self.minid, self.maxid):
                temprank = self.utility.config.Read(self.prefix + str(i) + "_rank", "int")
                if (i == colid):
                    self.utility.config.Write(self.prefix + str(i) + "_rank", newrank)
                elif (temprank >= newrank):
                    self.utility.config.Write(self.prefix + str(i) + "_rank", temprank + 1)
                else:
                    self.utility.config.Write(self.prefix + str(i) + "_rank", temprank)
        self.utility.config.Flush()
        
        # Write changes to the config file and refresh the display
        self.updateColumns()
    
    def updateColumns(self):
        self.columns.getColumnData()
        self.loadColumns()

        self.parent.updateColumns(force = True)
    
    def getSelected(self, firstitemonly = False, reverse = False):
        selected = []
        index = self.GetNextItem(-1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
        while index != -1:
            selected.append(index)
            if (firstitemonly):
                return selected
            index = self.GetNextItem(index, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
        selected.sort()
        if reverse:
            selected.reverse()
        return selected
        
    def selectAll(self):
        for index in range(self.GetItemCount()):
            self.Select(index)
    
    def invertSelection(self):
        for index in range(self.GetItemCount()):
            self.SetItemState(index, 4 - self.GetItemState(index, wx.LIST_STATE_SELECTED), wx.LIST_STATE_SELECTED)
