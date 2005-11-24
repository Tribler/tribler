#!/usr/bin/python

#########################################################################
#
# Spinners to control and display information
# 
#########################################################################
import sys
import os
import wx

from Utility.constants import * #IGNORE:W0611


class ABCSpinner(wx.Panel):
    def __init__(self, parent, label, unitlabel = None):
        self.parent = parent
        self.utility = parent.utility
        
        style = wx.CLIP_CHILDREN
        wx.Panel.__init__(self, parent, -1, style = style)
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.labeltext = self.utility.lang.get(label)
        if unitlabel is not None:
            self.unitlabeltext = self.utility.lang.get(unitlabel)
        else:
            self.unitlabeltext = None
            
        self.spinner = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.spinner.SetRange(0, 1000)
        self.spinner.Bind(wx.EVT_SPINCTRL, self.changeSpinner)
        self.spinner.Bind(wx.EVT_TEXT, self.changeSpinner)
                  
        self.label = wx.StaticText(self, -1, self.labeltext)
        self.current = wx.StaticText(self, -1, "", size = wx.Size(20, -1))
        
        sizer.Add(self.label, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.current, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        sizer.Add(wx.StaticText(self, -1, " / "), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        sizer.Add(self.spinner, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        if self.unitlabeltext is not None:
            self.unitlabel = wx.StaticText(self, -1, self.unitlabeltext)
            sizer.Add(self.unitlabel, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
            
        self.SetSizerAndFit(sizer)

    def changeSpinner(self, event = None):
        pass
        
    def updateCounter(self, event = None):
        pass
        
    def enableSpinner(self, enable = True):
        self.Enable(enable)
        
    def enforceMinMax(self):
        newval = self.spinner.GetValue()
        
        spinnermin = self.spinner.GetMin()
        spinnermax = self.spinner.GetMax()
        if newval < spinnermin:
            newval = spinnermin
            self.spinner.SetValue(spinnermin)
        elif newval > spinnermax:
            newval = spinnermax
            self.spinner.SetValue(spinnermax)
        if newval > 1000:
            newval = 1000
            
        return newval
        
        