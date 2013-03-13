# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import unittest
import os
import sys
import wx
import gc
import Image
import re

from threading import Thread, enumerate as enumerate_threads
from time import sleep, time

from Tribler.Main.tribler import run
from Tribler.Core.Session import Session
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.dispersy.singleton import Singleton
from Tribler.dispersy.member import Member
import shutil

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
        #If these directories still exist then the previous unittest caused a filelock.
        #Hence this should not happen...
        os.mkdir(".Tribler")
        os.mkdir("TriblerDownloads")
        
        self.app = wx.GetApp()
        if not self.app:
            self.app = wx.PySimpleApp(redirect = False)
            
        self.guiUtility = None
        self.frame = None
        self.lm = None
        self.session = None
        self.quitting = False
        
        self.asserts = []
        
        self.annotate(self._testMethodName, start = True)
        
    def assert_(self, boolean, reason, doassert = True):
        if not boolean:
            self.screenshot("ASSERT: %s"%reason)
            self.quit()
            
            self.asserts.append((boolean, reason))
            
            if doassert:
                assert boolean, reason
        
    def startTest(self, callback):
        self.quitting = False
        
        def wait_for_init():
            print >> sys.stderr, "tgs: lm initcomplete, staring to wait for frame to be ready"

            self.guiUtility = GUIUtility.getInstance()
            self.frame = self.guiUtility.frame
            
            self.CallConditional(30, lambda : self.frame.ready, callback)
        
        def wait_for_instance():
            print >> sys.stderr, "tgs: found instance, staring to wait for lm to be initcomplete"
            self.session = Session.get_instance()
            self.lm = self.session.lm
            
            self.CallConditional(30, lambda : self.lm.initComplete, wait_for_init)
        
        self.CallConditional(30, Session.has_instance, wait_for_instance)
        
        #modify argv to let tribler think its running from a different directory
        sys.argv = [os.path.abspath('./.exe')]
        run()
        
    def Call(self, seconds, callback):
        if not self.quitting:
            wx.CallLater(seconds * 1000, callback)
        
    def CallConditional(self, timeout, condition, callback, assertMsg = None):
        t = time()
        
        def DoCheck():
            if not self.quitting:
                if time() - t < timeout:
                    if condition():
                        print >> sys.stderr, "tgs: condition satisfied after %d seconds, calling callback"%(time() - t)
                        callback()
                    else:
                        self.Call(0.5, DoCheck)
                else:
                    print >> sys.stderr, "tgs: quitting, condition was not satisfied in %d seconds"%timeout
                    self.assert_(False, assertMsg if assertMsg else "Condition was not satisfied in %d seconds"%timeout, doassert = False)
        wx.CallAfter(DoCheck)
    
    def quit(self):
        self.quitting = True
        
        if self.frame:
            self.frame.OnCloseWindow()
            
        else:
            wx.CallLater(1000, self.app.ExitMainLoop)
            wx.CallLater(2500, self.app.Exit)

    def tearDown(self):
        self.annotate(self._testMethodName, start = False)
        
        """ unittest test tear down code """
        del self.guiUtility
        del self.frame
        del self.lm
        del self.session
    
        from Tribler.Core.CacheDB.sqlitecachedb import unregister
        unregister()
        
        sleep(10)
        gc.collect()
        
        ts = enumerate_threads()
        print >>sys.stderr,"teardown: Number of threads still running",len(ts)
        for t in ts:
            print >>sys.stderr,"teardown: Thread still running",t.getName(),"daemon",t.isDaemon(), "instance:", t
        
        dhtlog = os.path.join('.Tribler', 'pymdht.log')
        if os.path.exists(dhtlog):
            print >> sys.stderr,"teardown: content of pymdht.log"
            f = open(dhtlog, 'r')
            for line in f:
                line = line.strip()
                if line:
                    print >> sys.stderr, line
            f.close()
            print >> sys.stderr,"teardown: finished printing content of pymdht.log"
        
        shutil.rmtree(".Tribler")
        shutil.rmtree("TriblerDownloads")
        
        for boolean, reason in self.asserts:
            assert boolean, reason
            
        assert not os.path.exists(".Tribler"), ".Tribler should not exist"
        assert not os.path.exists("TriblerDownloads"), "TriblerDownloads should not exist"
            
    def annotate(self, annotation, start = True, destdir = "output"):
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        
        filename = os.path.join(destdir, "annotations.txt")
        if os.path.exists(filename):
            f = open(filename, 'a')
        else:
            f = open(filename, 'w')
            print >> f, "time remark start"
        
        annotation = re.sub('[^a-zA-Z0-9_]', '_', annotation)
        
        print >> f, time(), annotation, '1' if start else '0'
        f.close()
    
    def screenshot(self, title = None, destdir = "output"):
        app = wx.GetApp()
        window = app.GetTopWindow()
        rect = window.GetRect()
        
        screen = wx.WindowDC(window)
        bmp = wx.EmptyBitmap(rect.GetWidth(), rect.GetHeight() + 30)
        
        mem = wx.MemoryDC(bmp)
        mem.Blit(0, 30, rect.GetWidth(), rect.GetHeight(), screen, rect.GetX(), rect.GetY())
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
        filename = os.path.join(destdir, 'Screenshot-%.2d.png'%index)
        while os.path.exists(filename):
            index += 1
            filename = os.path.join(destdir, 'Screenshot-%.2d.png'%index)
        im.save(filename)
        
        del bmp
