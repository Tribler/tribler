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

from ABC.Toolbars.spinners import NumSimSpinner
from ABC.GUI.toolbar import ABCBar

from Utility.constants import * #IGNORE:W0611


##############################################################
#
# Class : ABCBottomBar2
#
# The right half of the bottom buttonbar that includes
# the spinner controls for # of simultaneous downloads
#
############################################################## 
class ABCBottomBar2(wx.Panel):
    def __init__(self, parent):
        self.parent = parent
        self.utility = self.parent.utility
        
        wx.Panel.__init__(self, parent, -1)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # New option buttons
        ##################################
        
        self.utility.bottomline = ABCBottomBar(self)

        sizer.Add(self.utility.bottomline, 0, wx.ALIGN_CENTER_VERTICAL)

        # Queue
        self.numsimspinner = NumSimSpinner(self)
        sizer.Add(self.numsimspinner, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 10)
       
        self.SetSizerAndFit(sizer)

    def changeSpinners(self):
        self.numsimspinner.changeSpinner()
                
    def updateCounters(self):
        self.numsimspinner.updateCounter()


##############################################################
#
# Class : ABCBottomBar
#
# The buttonbar at the bottom of the screen
#
############################################################## 
class ABCBottomBar(ABCBar):
    def __init__(self, windowparent):       
        # New option buttons
        ##################################
        configlabel = 'icons_toolbarbottom'
        
        style = wx.TB_HORIZONTAL | wx.NO_BORDER | wx.TB_FLAT | wx.TB_NODIVIDER | wx.CLIP_CHILDREN
        ABCBar.__init__(self, windowparent, configlabel, style = style, hspacing = 5)
            

##############################################################
#
# Class : ABCStatusBar
#
# The statusbar at the bottom of the screen
#
############################################################## 
class ABCStatusBar(wx.StatusBar):
    def __init__(self, parent):
        style = wx.ST_SIZEGRIP | wx.CLIP_CHILDREN
        
        wx.StatusBar.__init__(self, parent, -1, style = style)
        self.SetFieldsCount(9)
        self.SetStatusWidths([-1, 45, 35, 35, 35, 35, 50, 120, 120])
   
   
##############################################################
#
# Class : ABCToolBar
#
# Tool Bar at the top of the window
#
##############################################################         
class ABCToolBar(ABCBar):
    def __init__(self, parent):
        configlabel = 'icons_toolbartop'

        style = wx.TB_HORIZONTAL | wx.NO_BORDER | wx.TB_FLAT | wx.TB_TEXT | wx.CLIP_CHILDREN
        ABCBar.__init__(self, parent, configlabel, style = style)


##############################################################
#
# Class : ABCMenuBar
#
# Handles the menus at the top of the window
#
############################################################## 
class ABCMenuBar(wx.MenuBar):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility
                      
        style = wx.CLIP_CHILDREN
        wx.MenuBar.__init__(self, style = style)
        
        self.updateMenu()
        
    def updateMenu(self):
        for item in range(self.GetMenuCount()):
            menu = self.Remove(0)
            menu.Destroy()
        
        items = [ACTION_FILEMENU, 
                 ACTION_TORRENTACTIONMENU, 
                 ACTION_TOOLSMENU, 
                 ACTION_VERSIONMENU]
        for item in items:
            self.utility.actions[item].addToMenu(self, bindto = self.parent)
    
    