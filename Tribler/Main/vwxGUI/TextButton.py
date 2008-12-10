# Written by Jelle Roozenburg, Maarten ten Brinke 
# see LICENSE.txt for license information

import wx, os, sys
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from Tribler.Main.vwxGUI.bgPanel import ImagePanel
from Tribler.Main.vwxGUI.IconsManager import IconsManager
#from Tribler.Main.Dialogs.MugshotManager import MugshotManager ## no longer used
from Tribler.Main.vwxGUI.TextEdit import TextEdit
from font import *
from traceback import print_exc
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
#from wx.lib.stattext import GenStaticText

DEBUG = False

class TextButtonBasic(wx.Panel):
    """
    Button that changes the image shown if you move your mouse over it.
    It redraws the background of the parent Panel, if this is an imagepanel with
    a variable self.bitmap.
    """

    def __init__(self, menuItem, *args, **kw):
        self.selected = False
        self.menuItem = menuItem
        self.triblerStyles = TriblerStyles.getInstance()
        if len(args) == 0:
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            wx.Panel.__init__(self, *args, **kw) 
            self._PostInit()     
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True

    def _PostInit(self):
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        if not self.menuItem:
            self.Bind(wx.EVT_LEFT_UP, self.ClickedButton)      
        
        self.dcRollOver = 0
        
        if self.GetParent().GetName() == 'filterStandard':
            self.SetMinSize((-1,15))
            self.SetSize((-1,15))
#        self.SetMinSize((60,17))
        else:
            self.SetMinSize(self.GetSize())
        
        self.GetParent().Layout()
        self.Refresh(True)
        self.Update()
        
       
    def setSelected(self, sel):
        if sel != self.selected:
            self.selected = sel
            if self.menuItem:
                self.dcRollOver = 0
            self.Refresh()
        
    def isSelected(self):
        return self.selected
        
    def mouseAction(self, event):
        event.Skip()
        if event.Entering() and not self.selected: 
            self.dcRollOver = 1
            self.Refresh()
        elif event.Leaving() and not self.selected:
            self.dcRollOver = 0
            self.Refresh()

    def ClickedButton(self, event):
        name = self.GetName()
        event.Skip()
        self.guiUtility.buttonClicked(event)
#        self.guiUtility.detailsTabClicked(name)

    def OnPaint(self, evt):        
        dc = wx.BufferedPaintDC(self)
        if self.dcRollOver == 0 :
            dc.SetBackground(wx.Brush(self.triblerStyles.textButtonLeft(style = 'bgColour')))
        if self.dcRollOver == 1 or self.selected == True:
            dc.SetBackground(wx.Brush(self.triblerStyles.textButtonLeft(style = 'bgColour2')))
        
        dc.SetTextForeground(self.triblerStyles.textButtonLeft(style = 'textColour'))
        dc.SetFont(self.triblerStyles.textButtonLeft(style = 'font'))
        
        dc.Clear()
        
        dc.DrawText(self.GetName(), 2, 2)

class TextButton(TextButtonBasic):
    def __init__(self, *args, **kw):
        menuItem = False
        TextButtonBasic.__init__(self, menuItem, *args, **kw)
        
class TextButtonFilter(TextButtonBasic):
    def __init__(self, *args, **kw):
        menuItem = False
        TextButtonBasic.__init__(self, menuItem, *args, **kw)

        
class TextButtonLeft(TextButtonBasic):
    def __init__(self, parent, addItem = False, icon=False, *args, **kw):
        
        self.mm = IconsManager.getInstance()
        self.icon = None
        self.leftBtnMenuIcon = None

                
        menuItem = True        
        self.addItem = addItem
        self.extraMenu = False
        
        
        TextButtonBasic.__init__(self, menuItem, parent, *args, **kw)
        if icon:
#        if self.GetName() == 'Highspeed':
            self.AddLeftButtonIcon(True)
            
#        self.AddLeftButtonMenuIcon(False)
        

    def AddLeftButtonIcon(self, False):
        print 'tb> addleftButtonIcon'
        print self.GetName()
        if self.GetName() == 'Start page':
            self.icon = self.mm.MENUICONHOME
        elif self.GetName() == 'Stats':
            self.icon = self.mm.MENUICONSTATS
        elif self.GetName() == 'Profile':
            self.icon = self.mm.MENUICONPROFILE
        elif self.GetName() == 'All Downloads':
            self.icon = self.mm.MENUICONALLDOWNLOADS
        elif self.GetName() == 'Highspeed':
            self.icon = self.mm.MENUICONPLAYLIST
        elif self.GetName() == 'All Friends':
            self.icon = self.mm.MENUICONALLFRIENDS
        elif self.GetName() == 'All Favorites':
            self.icon = self.mm.MENUICONPLAYLIST
        elif self.GetName() == 'All Subscriptions':
            self.icon = self.mm.MENUICONALLSUBSCRIPTIONS
        elif self.GetName() == 'Tribler 5':
            self.icon = self.mm.MENUICONGROUPS
        elif self.GetName() == 'Tribler 4':
            self.icon = self.mm.MENUICONGROUPS
        elif self.GetName() == '< Tribler 4':
            self.icon = self.mm.MENUICONGROUPS

        
        
    def AddLeftButtonMenuIcon(self, enabled):
        if enabled:
            self.leftBtnMenuIcon = self.mm.LEFTBUTTONMENU
        else:
            self.leftBtnMenuIcon = None
#        if enabled:
#            self.expanded = True         
#            self.enabled = self.mm.H1EXPANDEDTRUE
#        else:
#            self.expanded = False         
#            self.enabled = self.mm.H1EXPANDEDFALSE


        
    def AddButtonLeftMenu(self, active):
        self.active = active
        if self.active:
            self.buttonIcon = self.mm.ADDMENUITEM
        else:
            self.buttonIcon = None  
            
        self.Refresh()
        
        
    def OnPaint(self, evt):
        # overriding the OnPaint funcion in TextButton
        dc = wx.BufferedPaintDC(self)
        
        if self.dcRollOver == 0 :
#            dc.SetBrush(wx.Brush(wx.BLACK)) 
            
            dc.SetBackground(wx.Brush(self.triblerStyles.textButtonLeft(style = 'bgColour')))
            dc.Clear()
            
        if self.dcRollOver == 1 or self.selected == True:
            dc.SetBackground(wx.Brush(self.triblerStyles.textButtonLeft(style = 'bgColour')))
#            dc.SetBackground(wx.Brush(self.triblerStyles.textButtonLeft(style = 'bgColour2')))
            dc.Clear()
#            
            dc.SetBrush(wx.Brush(self.triblerStyles.textButtonLeft(style = 'bgColour2')))            
            dc.DrawRectangle(0, 0, 200, 20)

#            dc.SetBackground(wx.Brush(self.triblerStyles.textButtonLeft(style = 'bgColour2')))
        
        if self.addItem:
            dc.SetFont(self.triblerStyles.textButtonLeft(style = 'fontAdd'))
            dc.SetTextForeground(self.triblerStyles.textButtonLeft(style = 'textColourAdd'))            
        else:
            dc.SetFont(self.triblerStyles.textButtonLeft(style = 'font'))
            dc.SetTextForeground(self.triblerStyles.textButtonLeft(style = 'textColour'))

        dc.DrawText(self.GetName(), 48, 3)
#        if self.leftBtnMenuIcon != None:
#            dc.DrawBitmap(self.leftBtnMenuIcon, 140, 2, True)
        if self.icon != None:
            dc.DrawBitmap(self.icon, 20, 0, True)
        
        
class TextButtonLeftH1(TextButtonBasic):
    def __init__(self, *args, **kw):
        self.mm = MugshotManager.getInstance()
        self.enabled = True
        self.Enabled(self.enabled)
        self.active = False
        menuItem = True
        self.buttonIcon = None        
        
        TextButtonBasic.__init__(self, menuItem, *args, **kw)
        
#        self.AddButtonIcon(False)
        
#    def AddButtonIcon(self, active):
#        self.active = active
#        if self.active:
#            self.buttonIcon = self.mm.ADDMENUITEM
#        else:
#            self.buttonIcon = None  
#            
#        self.Refresh()
            
    def Enabled(self, enabled):         
        if enabled:
            self.expanded = True         
            self.enabled = self.mm.H1EXPANDEDTRUE
        else:
            self.expanded = False         
            self.enabled = self.mm.H1EXPANDEDFALSE
            
        
            
    def OnPaint(self, evt):
        # overriding the OnPaint funcion in TextButton
        dc = wx.BufferedPaintDC(self)
        if self.dcRollOver == 0 :
            dc.SetBackground(wx.Brush(self.triblerStyles.textButtonLeftH1(style = 'bgColour')))
        if self.dcRollOver == 1 or self.selected == True:
            dc.SetBackground(wx.Brush(self.triblerStyles.textButtonLeftH1(style = 'bgColour')))
        
        if self.expanded:   
            dc.SetTextForeground(self.triblerStyles.textButtonLeftH1(style = 'textColour'))
        else:  
            dc.SetTextForeground(self.triblerStyles.textButtonLeftH1(style = 'textColour2'))
            
        dc.SetFont(self.triblerStyles.textButtonLeftH1(style = 'font'))
        dc.Clear()
        
        dc.DrawText(self.GetName(), 18, 2)
        dc.DrawBitmap(self.enabled, 5, 5, True)
        
        if self.buttonIcon != None: 
            print 'tb'
#            dc.DrawBitmap(self.buttonIcon, 140, 2, True)
        


        
