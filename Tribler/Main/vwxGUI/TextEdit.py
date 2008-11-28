import wx, os, sys
#import wx, math, time, os, sys, threading
import wx, os
from font import *
from traceback import print_exc
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
#from wx.lib.stattext import GenStaticText

DEBUG = False

class TextEdit(wx.Panel):
    """
    Text item that is used for moderations.
    """

    def __init__(self, *args, **kw):
        self.selected = False
        self.colours = [wx.Colour(102,102,102), wx.WHITE]
        if len(args) == 0:
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            wx.Panel.__init__(self, *args, **kw)             
            self.OnCreate()
            self._PostInit()     
        
    def OnCreate(self, event= None):
        print 'tb > OnCreate TEXTEDIT'
        self.Unbind(wx.EVT_WINDOW_CREATE)
        self.triblerStyles = TriblerStyles.getInstance()
        self.addComponents()
        self.editState = True
        self.editSetToggle(False)
        


        wx.CallAfter(self._PostInit)
        if event != None:
            event.Skip()
        return True
    
    def addComponents(self):
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.textctrl = wx.TextCtrl(self, -1, style = wx.TE_MULTILINE|wx.NO_BORDER|wx.TE_RICH )
        
        self.triblerStyles.setLightText(self.textctrl)       
#        self.textctrl.SetForegroundColour(wx.Colour(180,180,180))
#        self.textctrl.SetBackgroundColour(wx.Colour(102,102,102))
#        self.triblerStyles.setLightText(self.sizeField, text= '---')        
#        wx.TE_NO_VSCROLL

#        self.textctrl = wx.StaticText(self, -1, label)
        self.textctrl.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.textctrl.Bind(wx.EVT_LEFT_UP, self.ClickedButton)

        
        self.sizer.Add(self.textctrl, 1, wx.ALIGN_LEFT|wx.EXPAND, 5)
#        self.SetMinSize((60,200))
        self.SetBackgroundColour(self.colours[int(self.selected)])    
        
        self.SetSizer(self.sizer)
        
        self.SetAutoLayout(1)
        self.Layout()
        self.Refresh(True)
        self.Update()


    def _PostInit(self):
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
#        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_LEFT_UP, self.ClickedButton)
        
        
        #self.Show()        
       
    def setText(self, text=''):
        self.textctrl.SetValue(text)
        
       
       
    def editSetToggle(self, newState):

        if newState != self.editState:        
            if newState == True:
                # enable Edit
                colour = self.triblerStyles.colours(2)
                self.textctrl.SetEditable(True)

            elif newState == False:
                # disable Edit
                colour = self.triblerStyles.colours(1)                
                self.textctrl.SetEditable(False)
                
            self.SetBackgroundColour(colour)
            self.textctrl.SetBackgroundColour(colour)
            
            self.editState = newState

        
    def isSelected(self):
        return self.selected
        
    def mouseAction(self, event):
        event.Skip()
        if event.Entering() and not self.selected:
            #print 'TextButton: enter' 
            self.SetBackgroundColour(self.colours[1])
            self.Refresh()
        elif event.Leaving() and not self.selected:
            #print 'TextButton: leaving'
            self.SetBackgroundColour(self.colours[0])
            self.Refresh()

    def ClickedButton(self, event):
        name = self.GetName()
        event.Skip()
        #self.guiUtility.buttonClicked(event)
        self.guiUtility.detailsTabClicked(name)
