# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import unittest
import os
import sys
import wx

from threading import Thread
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
        
        wx.CallAfter(self.frame.OnCloseWindow, force = True)
        self.t.join()
        
        sleep(10)