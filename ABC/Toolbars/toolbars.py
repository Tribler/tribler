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

from Tribler.Dialogs.activities import *

DEBUG = True

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
    def __init__(self, parent, utility):
        self.utility = utility
        style = wx.ST_SIZEGRIP | wx.CLIP_CHILDREN
        
        wx.StatusBar.__init__(self, parent, -1, style = style)
        self.SetFieldsCount(5)
        self.SetStatusWidths([-1, 120, 120, 100, 100])

    def setActivity(self,type,msg=u''):
    
        if type == ACT_NONE:
            prefix = u''
            msg = u''
        elif type == ACT_UPNP:
            prefix = self.utility.lang.get('act_upnp')
        elif type == ACT_REACHABLE:
            prefix = self.utility.lang.get('act_reachable')
        elif type == ACT_GET_EXT_IP_FROM_PEERS:
            prefix = self.utility.lang.get('act_get_ext_ip_from_peers')
        elif type == ACT_MEET:
            prefix = self.utility.lang.get('act_meet')
        elif type == ACT_GOT_METADATA:
           prefix = self.utility.lang.get('act_got_metadata')
        elif type == ACT_RECOMMEND:
           prefix = self.utility.lang.get('act_recommend')

        if msg == u'':
            text = prefix
        else:
            text = unicode( prefix+u' '+msg)
            
        if DEBUG:
            print "act: Setting activity",text            
        self.SetStatusText( text, 0)

##############################################################
#
# Class : ABCStatusButtons
#
# The statusbar buttons at the bottom left of the screen
#
############################################################## 
class ABCStatusButtons(wx.BoxSizer):
    def __init__(self, parent, utility):
        self.utility = utility
        wx.BoxSizer.__init__(self, wx.HORIZONTAL)

        self.reach = False
        self.gbm = self.utility.makeBitmap('greenball.bmp')
        self.reachbutton = self.utility.makeBitmapButtonFit(parent, 'yellowball.bmp', 'unknownreach_tooltip',self.onClick)
        self.Add(self.reachbutton, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
        self.ybm = self.reachbutton.GetBitmapLabel()        
        #self.reachbutton.SetBitmapDisabled(self.ybm)
        #self.reachbutton.SetBitmapFocus(self.ybm)
        #self.reachbutton.SetBitmapSelected(self.ybm)

    def setReachable(self,reach):
        if self.reachbutton is not None:
            if reach:
                self.reachbutton.SetBitmapLabel(self.gbm)
                self.reachbutton.GetToolTip().SetTip(self.utility.lang.get('reachable_tooltip'))
            else:
                self.reachbutton.SetBitmapLabel(self.ybm)
                self.reachbutton.GetToolTip().SetTip(self.utility.lang.get('unknownreac_tooltip'))
            self.reach = reach

    def onClick(self,event=None):
        if self.reach:
            title = self.utility.lang.get('tribler_information')
            type = wx.ICON_INFORMATION
            msg = self.utility.lang.get('reachable_tooltip')
        else:
            title = self.utility.lang.get('tribler_warning')
            type = wx.ICON_WARNING
            msg = self.utility.lang.get('tribler_unreachable_explanation')
            
        dlg = wx.MessageDialog(None, msg, title, wx.OK|type)
        result = dlg.ShowModal()
        dlg.Destroy()

   
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
    
    
