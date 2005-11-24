#!/usr/bin/python

#########################################################################
#
# Various toolbars used within ABC's main window
# 
#########################################################################
import sys
import os
import wx

#from traceback import print_exc
#from cStringIO import StringIO

from Utility.constants import * #IGNORE:W0611


################################################################
#
# Class: ToolBarDialog
#
# Allows a user to alter the settings and appearance of 
# columns in a ABCBar.
#
################################################################
class ToolBarDialog(wx.Dialog):
    def __init__(self, toolbar):
        
        self.utility = toolbar.utility
        
        title = self.utility.lang.get('customizetoolbar')
        
        pre = wx.PreDialog()
        pre.Create(toolbar, -1, title)
        self.this = pre.this

        outerbox = wx.BoxSizer( wx.VERTICAL )
        
        self.toolbarPanel = ToolBarPanel(self, toolbar)
        
        applybtn  = wx.Button(self, -1, self.utility.lang.get('apply'))
        self.Bind(wx.EVT_BUTTON, self.onApply, applybtn)
        
        okbtn  = wx.Button(self, -1, self.utility.lang.get('ok'))
        self.Bind(wx.EVT_BUTTON, self.onOK, okbtn)
        
        cancelbtn = wx.Button(self, wx.ID_CANCEL, self.utility.lang.get('cancel'))
        
        setDefaultsbtn = wx.Button(self, -1, self.utility.lang.get('reverttodefault'))
        self.Bind(wx.EVT_BUTTON, self.toolbarPanel.setDefaults, setDefaultsbtn)
        
        buttonbox = wx.BoxSizer( wx.HORIZONTAL )
        buttonbox.Add(applybtn, 0, wx.ALL, 5)
        buttonbox.Add(okbtn, 0, wx.ALL, 5)
        buttonbox.Add(cancelbtn, 0, wx.ALL, 5)
        buttonbox.Add(setDefaultsbtn, 0, wx.ALL, 5)
        
        outerbox.Add( self.toolbarPanel, 0, wx.EXPAND|wx.ALL, 5)
        outerbox.Add( buttonbox, 0, wx.ALIGN_CENTER)
       
        self.SetAutoLayout( True )
        self.SetSizer( outerbox )
        self.Fit()
        
    def onOK(self, event = None):
        if self.onApply(event):
            self.EndModal(wx.ID_OK)
        
    def onApply(self, event = None):
        self.toolbarPanel.apply()
        return True


################################################################
#
# Class: ToolBarPanel
#
# Contains the interface elements for a ToolBarDialog
#
################################################################
class ToolBarPanel(wx.Panel):
    def __init__(self, parent, toolbar):
        wx.Panel.__init__(self, parent, -1)
        
        self.parent = parent
        self.utility = parent.utility
        
        self.toolbar = toolbar
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        listsizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.lists = {}
        self.lists["available"] = ActionButtonsList(self, 'buttons_available', [])
        self.lists["current"] = ActionButtonsList(self, 'buttons_current', [])
        
        listsizer.Add(self.lists["available"], 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        addremovesizer = wx.BoxSizer(wx.VERTICAL)
        
        self.buttons = {}
        self.buttons["add"] = wx.Button(self, -1, self.utility.lang.get('buttons_add') + " ->")
        self.Bind(wx.EVT_BUTTON, self.addButton, self.buttons["add"])
        addremovesizer.Add(self.buttons["add"], 0, wx.ALIGN_CENTER|wx.ALL, 5)
        
        self.buttons["remove"]= wx.Button(self, -1, "<- " + self.utility.lang.get('buttons_remove'))
        self.Bind(wx.EVT_BUTTON, self.removeButton, self.buttons["remove"])
        addremovesizer.Add(self.buttons["remove"], 0, wx.ALIGN_CENTER|wx.ALL, 5)
        
        listsizer.Add(addremovesizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        listsizer.Add(self.lists["current"], 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        updownsizer = wx.BoxSizer(wx.VERTICAL)
        self.buttons["up"] = self.utility.makeBitmapButton(self, 'moveup.bmp', 'move_up', self.OnMove)
        updownsizer.Add(self.buttons["up"], 0, wx.ALIGN_CENTER|wx.ALL, 5)

        self.buttons["down"] = self.utility.makeBitmapButton(self, 'movedown.bmp', 'move_down', self.OnMove)        
        updownsizer.Add(self.buttons["down"], 0, wx.ALIGN_CENTER|wx.ALL, 5)
        
        listsizer.Add(updownsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        sizer.Add(listsizer, 1, wx.EXPAND)
        
        self.loadValues()
        
        self.SetSizerAndFit(sizer)
        
    def getAvailable(self):
        available = []
        
        # Always include the separator
        actionid = ACTION_SEPARATOR
        action = self.utility.actions[actionid]
        if action.bitmap is not None:
            available.append(actionid)
        
        for actionid in self.utility.actions:
            action = self.utility.actions[actionid]
            if action.bitmap is not None and (actionid != ACTION_SEPARATOR):
                if (actionid not in self.lists["current"].items):
                    available.append(actionid)
                
        return available
        
    def getSelected(self, listname = "current"):
        return self.lists[listname].list.GetNextItem(-1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
        
    def addButton(self, event = None):
        # Get the button selected on the left
        index = self.getSelected("available")
        if index == -1:
            # Nothing selected on the left
            return
        
        buttonid = self.lists["available"].buttonlist[index]
        
        # Remove it from the left
        if buttonid != ACTION_SEPARATOR:
            self.lists["available"].removeItem(index)
        
        # Add it to the right
        index = self.lists["current"].addItem(buttonid)
        self.lists["current"].selectItem(index)
        
    def removeButton(self, event = None):
        # Get the button selected on the right
        index = self.getSelected("current")
        if index == -1:
            # Nothing selected on the right
            return
            
        buttonid = self.lists["current"].buttonlist[index]
        
        # Remove it from the right
        self.lists["current"].removeItem(index)
        
        # Add it from the left
        if buttonid != ACTION_SEPARATOR:
            index = self.lists["available"].addItem(buttonid)
            self.lists["available"].selectItem(index)
            
            
    def OnMove(self, event = None):       
        # Get the button selected on the right
        index = self.getSelected("current")
        if index == -1:
            # Nothing selected on the right
            return
        
        # Move up
        if event.GetId() == self.buttons["up"].GetId():
            direction = -1
        # Move down
        else:
            direction = 1
        
        self.lists["current"].move(index, direction)
                
    def apply(self):       
        changed = self.utility.config.Write(self.toolbar.configlabel, self.lists["current"].buttonlist, "bencode-list")
        if changed:
            self.utility.config.Flush()
            self.toolbar.updateItems()
        return changed
        
    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        
        self.lists["current"].items = Read(self.toolbar.configlabel, "bencode-list")
        self.lists["available"].items = self.getAvailable()
        
        self.lists["current"].setupItems()
        self.lists["available"].setupItems()
        
    def setDefaults(self, event = None):
        self.loadValues(self.utility.config.ReadDefault)
               

##############################################################
#
# Class : ActionsList
#
# List of action buttons
#
############################################################## 
class ActionButtonsList(wx.Panel):
    def __init__(self, parent, label, items):
        wx.Panel.__init__(self, parent, -1)
        
        self.parent = parent
        self.utility = parent.utility
        
        self.label = self.utility.lang.get(label)
        self.items = items
        self.buttonlist = []
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(self, -1, self.label), 0, wx.ALL, 5)
        
        self.list = wx.ListCtrl(self, -1, size = (210, 300), style = wx.LC_REPORT|wx.LC_NO_HEADER|wx.LC_SINGLE_SEL)
        self.setupList()
        
        sizer.Add(self.list, 1, wx.ALL, 5)
        
        self.SetSizerAndFit(sizer)
        
        self.firsttime = True
        
    def setupList(self):
        self.list.SetImageList(self.utility.imagelist["list"], wx.IMAGE_LIST_SMALL)
        
        info = wx.ListItem()
        info.m_mask = wx.LIST_MASK_TEXT | wx.LIST_MASK_IMAGE | wx.LIST_MASK_FORMAT
        info.m_image = -1
        info.m_format = 0
        info.m_text = " "
        self.list.InsertColumnInfo(0, info)
               
    def setupItems(self):
        if not self.firsttime:
            # Only need to delete items after the first time
            self.list.DeleteAllItems()
                
        self.buttonlist = []
        for actionid in self.items:
            self.addItem(actionid, resizecol = False)
            
        self.list.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        
        self.firsttime = False
        
    def selectItem(self, index):
        self.list.Select(index)
        self.list.EnsureVisible(index)
        
    def addItem(self, actionid, resizecol = True):
        try:
            action = self.utility.actions[actionid]
        except:
            return
        
        index = self.list.GetItemCount()
        text = action.shortdesc
        imageindex = self.utility.imagelist["idToImage"][actionid]
        self.list.InsertImageStringItem(index, text, imageindex)
        self.buttonlist.append(actionid)
        
        if resizecol:
            self.list.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        
        return index
        
    def removeItem(self, index):
        self.list.DeleteItem(index)
        del self.buttonlist[index]
        
        self.list.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        
    def move(self, index, dir):
        if dir == -1 and index == 0:
            # moving up and already at the top
            return
        elif dir == 1 and index == len(self.buttonlist) - 1:
            # moving down and already at the bottom
            return
        
        index2 = index + dir
        
        # Get items
        item = self.list.GetItem(index)        
        item2 = self.list.GetItem(index2)

        # Swap text and images
        item.m_image, item2.m_image = item2.m_image, item.m_image
        item.m_text, item2.m_text = item2.m_text, item.m_text

        # Set items
        self.list.SetItem(item)
        self.list.SetItem(item2)
        
        # Swap indexes
        self.buttonlist[index], self.buttonlist[index2] = self.buttonlist[index2], self.buttonlist[index]
        
        # Update the selection
        self.selectItem(index2)
        

##############################################################
#
# Class : ABCBar
#
# Generic statusbar class
#
############################################################## 
class ABCBar(wx.ToolBar):
    def __init__(self, parent, configlabel, style = None, hspacing = 0, vspacing = 0):
        self.parent = parent
        self.utility = self.parent.utility
        
        self.hspacing = hspacing
        self.vspacing = vspacing
        self.firsttime = True
        
        if style is None:
            style = wx.TB_HORIZONTAL | wx.NO_BORDER | wx.TB_FLAT | wx.TB_NODIVIDER | wx.CLIP_CHILDREN
        wx.ToolBar.__init__(self, parent, -1, style = style)
        
        self.configlabel = configlabel
        
        self.items = []
        self.toolcount = 0
        
        self.updateItems()
        
        self.Bind(wx.EVT_RIGHT_DOWN, self.onRightClick)
        
    def onRightClick(self, event):
        menu = wx.Menu()
        
        self.utility.makePopup(menu, self.onToolbarDialog, 'customizetoolbar')
        
        self.PopupMenu(menu, event.GetPosition())
        
    def onToolbarDialog(self, event = None):
        dialog = ToolBarDialog(self)
        dialog.ShowModal()
        dialog.Destroy()
        
    def updateItems(self):
        self.items = self.utility.config.Read(self.configlabel, "bencode-list")
        
        # Remove from item toolbars if needed:
        for actionid in self.utility.actions:
            if actionid in self.utility.actions:
                action = self.utility.actions[actionid]
                action.removeFromToolbar(self)

        # Remove old items:
        while self.toolcount > 0:
            self.DeleteToolByPos(0)
            self.toolcount -= 1
               
        # Add new items
        self.firsttime = True
        
        for item in self.items:
            if item == -1:
                self.AddSeparator()
                self.toolcount += 1
            else:
                if item in self.utility.actions:
                    self.utility.actions[item].addToToolbar(self)
                    self.toolcount += 1
                
        self.Realize()
        self.parent.Layout()