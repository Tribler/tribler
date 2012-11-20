# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import unittest
import os
import sys
import wx
import gc

from threading import Thread, enumerate as enumerate_threads
from time import sleep

from Tribler.Main.tribler import run
from Tribler.Core.Session import Session
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

class TestGuiAsServer(unittest.TestCase):
    """ 
    Parent class for testing the gui-side of Tribler
    """
    
    def setUp(self):
        """ unittest test setup code """
        #modify argv to let tribler think its running from a different directory
        sys.argv = [os.path.abspath(os.path.join('..','..', '.exe'))]
        
        self.t = Thread(target = run, name = "UnitTestingThread")
        self.t.start()
        
        while not Session.has_instance():
            sleep(1)
            
        self.session = Session.get_instance()
        self.lm = self.session.lm
        
        while not self.lm.initComplete:
            sleep(1)
            
        self.guiUtility = GUIUtility.getInstance()
        self.frame = self.guiUtility.frame

    def tearDown(self):
        """ unittest test tear down code """
        wx.CallAfter(self.frame.OnCloseWindow)
        
        del self.guiUtility
        del self.frame
        del self.lm
        del self.session
        
        self.t.join()
        
        sleep(10)
        
        ts = enumerate_threads()
        print >>sys.stderr,"teardown: Number of threads still running",len(ts)
        for t in ts:
            print >>sys.stderr,"teardown: Thread still running",t.getName(),"daemon",t.isDaemon(), "instance:", t