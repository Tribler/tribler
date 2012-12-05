# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import unittest
import os
import sys
import wx
import gc
import Image

from threading import Thread, enumerate as enumerate_threads
from time import sleep, time

from Tribler.Main.tribler import run
from Tribler.Core.Session import Session
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.dispersy.singleton import Singleton
from Tribler.dispersy.member import Member

try:
    from collections import OrderedDict
except ImportError:
    from .python27_ordereddict import OrderedDict

class TestGuiAsServer(unittest.TestCase):
    """ 
    Parent class for testing the gui-side of Tribler
    """
    
    def setUp(self):
        """ unittest test setup code """
        self.app = wx.GetApp()
        if not self.app:
            self.app = wx.PySimpleApp(redirect = False)
            
        self.guiUtility = None
        self.frame = None
        self.lm = None
        self.session = None
        
        self.asserts = []
        
    def startTest(self, callback):
        def wait_for_peers():
            if not (self.frame.ready and self.frame.SRstatusbar.GetConnections() > 0):
                wx.CallLater(1000, wait_for_peers)
            else:
                wx.CallLater(5000, callback)
        
        def wait_for_init():
            if not self.lm.initComplete:
                wx.CallLater(1000, wait_for_init)
            else:
                self.guiUtility = GUIUtility.getInstance()
                self.frame = self.guiUtility.frame
                wait_for_peers()
        
        def wait_for_instance():
            if not Session.has_instance():
                wx.CallLater(1000, wait_for_instance)
            else:
                self.session = Session.get_instance()
                self.lm = self.session.lm
            
                wait_for_init()
        
        wx.CallLater(1000, wait_for_instance)
        
        #modify argv to let tribler think its running from a different directory
        sys.argv = [os.path.abspath('./.exe')]
        run()
        
    def quit(self):
        self.frame.OnCloseWindow()

    def tearDown(self):
        for boolean, reason in self.asserts:
            assert boolean, reason
        
        """ unittest test tear down code """
        del self.guiUtility
        del self.frame
        del self.lm
        del self.session
        
        for object in gc.get_objects():
            if isinstance(object, Singleton):
                print >> sys.stderr, "teardown: Deleting %s singleton"%str(type(object))
                object.del_instance()
                
            if isinstance(object, OrderedDict):
                print >> sys.stderr, "teardown: Clearing %s"%str(type(object))
                object.clear()
                
            if isinstance(object, dict):
                keys = object.keys()
                if keys:
                    if isinstance(object[keys[0]], Member):
                        object.clear()
                        print >> sys.stderr, "teardown: Clearing %s contains Member objects"%str(type(object))
    
        from Tribler.Core.CacheDB.sqlitecachedb import unregister
        unregister()
        
        sleep(10)
        gc.collect()
        
        ts = enumerate_threads()
        print >>sys.stderr,"teardown: Number of threads still running",len(ts)
        for t in ts:
            print >>sys.stderr,"teardown: Thread still running",t.getName(),"daemon",t.isDaemon(), "instance:", t
    
    def screenshot(self, title = None, destdir = "output"):
        app = wx.GetApp()
        window = app.GetTopWindow()
        rect = window.GetRect()
        
        screen = wx.ScreenDC()
        bmp = wx.EmptyBitmap(rect.GetWidth(), rect.GetHeight())
        
        mem = wx.MemoryDC(bmp)
        mem.Blit(0, 0, rect.GetWidth(), rect.GetHeight(), screen, rect.GetX(), rect.GetY())
        if title:
            titlerect = wx.Rect(0, 0, rect.GetWidth(), 30)
            mem.DrawRectangleRect(titlerect)
            mem.DrawLabel(title, titlerect, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL)
        del mem
        
        myWxImage = wx.ImageFromBitmap(bmp)
        im = Image.new('RGB', (myWxImage.GetWidth(), myWxImage.GetHeight()))
        im.fromstring(myWxImage.GetData())
        
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        index = 1
        filename = os.path.join(destdir, 'Screenshot-%d.png'%index)
        while os.path.exists(filename):
            index += 1
            filename = os.path.join(destdir, 'Screenshot-%d.png'%index)
        im.save(filename)
        
        del bmp