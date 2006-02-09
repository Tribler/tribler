#!/usr/bin/python

#########################################################################
#
# Spinners to control and display information
# 
#########################################################################
import sys
import os
import wx
import threading
from traceback import print_stack

from ABC.GUI.spinner import ABCSpinner

from Utility.constants import * #IGNORE:W0611
       
    
class NumSimSpinner(ABCSpinner):
    def __init__(self, parent):
        label = 'tb_maxsim'
        
        ABCSpinner.__init__(self, parent, label)
        
        self.changeSpinner()

    def changeSpinner(self, event = None):

        if threading.currentThread().getName() != "MainThread":
            print "spinners: NOT MAIN THREAD"
            print_stack()

        if event is None:
            self.spinner.SetValue(self.utility.config.Read('numsimdownload', "int"))
            self.updateCounter()
            return
            
        currentval = self.utility.config.Read('numsimdownload')
        newval = self.enforceMinMax()
               
        if currentval != newval:
            self.utility.config.Write('numsimdownload', newval)
            self.utility.config.Flush()
            
            if event is not None:
                self.utility.queue.updateAndInvoke()

    def updateCounter(self, event = None):

        if threading.currentThread().getName() != "MainThread":
            print "spinners: NOT MAIN THREAD"
            print_stack()

        proccount = self.utility.queue.getProcCount()
        self.current.SetLabel(str(proccount))
       

#class DownSpinner(ABCSpinner):
#    def __init__(self, parent):
#        # TODO: needs real label
#        label = 'tb_urm'
#        unitlabel = self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')
#        
#        ABCSpinner.__init__(self, parent, label, unitlabel)
#        
#        self.changeSpinner()
#        
#    def changeSpinner(self):
#        if event is None:
#            self.spinner.SetRange(0, 9999)
#            self.spinner.SetValue(self.utility.queue.ratemanager.MaxRate("down"))
#            self.current.SetLabel(str(self.utility.queue.totals_kb['down']))
#            return


#class UpSpinner(ABCSpinner):
#    def __init__(self, parent):       
#        # TODO: needs real label
#        label = 'tb_urm'
#        unitlabel = self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')
#        
#        ABCSpinner.__init__(self, parent, label, unitlabel)
#        
#        self.changeSpinner()
#        
#    def changeSpinner(self, event = None):
#        if event is None:
#            self.spinner.SetRange(0, 9999)
#            self.spinner.SetValue(self.utility.queue.ratemanager.MaxRate("up"))
#            self.current.SetLabel(str(self.utility.queue.totals_kb['up']))
#            return
#            
#        # Check which upload value we're using
#        # (seeding or downloading)