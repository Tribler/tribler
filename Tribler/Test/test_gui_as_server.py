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
import shutil
from Tribler.Core import defaults

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_.Tribler")
DEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_TriblerDownloads")

# Set custom state_dir and dest_dir paths so we do not mess with local installs by accident.
defaults.sessdefaults["state_dir"] = STATE_DIR
defaults.sessdefaults["dest_dir"] = DEST_DIR

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
        # Elric: If the files are still there it means that either the last run segfaulted or
        # that there was some kind of lock on those and the tearDown wasn't able to delete them.
        # In either case the test would fail, so just remove the dirs.
        for dir_ in (STATE_DIR, DEST_DIR):
            if os.path.exists(dir_):
                shutil.rmtree(dir_)
            os.mkdir(dir_)

        self.app = wx.GetApp()
        if not self.app:
            self.app = wx.PySimpleApp(redirect=False)

        self.guiUtility = None
        self.frame = None
        self.lm = None
        self.session = None
        self.quitting = False

        self.asserts = []

        self.annotate(self._testMethodName, start=True)

    def assert_(self, boolean, reason, doassert=True):
        if not boolean:
            self.screenshot("ASSERT: %s" % reason)
            self.quit()

            self.asserts.append((boolean, reason))

            if doassert:
                assert boolean, reason

    def startTest(self, callback):
        self.quitting = False
        def wait_for_frame():
            print >> sys.stderr, "tgs: lm initcomplete, staring to wait for frame to be ready"
            self.frame = self.guiUtility.frame
            self.CallConditional(30, lambda : self.frame.ready, callback)

        def wait_for_init():
            print >> sys.stderr, "tgs: lm initcomplete, staring to wait for GUIUtility to be ready"

            self.guiUtility = GUIUtility.getInstance()

            self.CallConditional(30, lambda : self.guiUtility.frame, wait_for_frame)

        def wait_for_guiutility():
            print >> sys.stderr, "tgs: waiting for guiutility instance"
            self.CallConditional(30, lambda: GUIUtility.hasInstance(), wait_for_init)

        def wait_for_instance():
            print >> sys.stderr, "tgs: found instance, staring to wait for lm to be initcomplete"
            self.session = Session.get_instance()
            self.lm = self.session.lm

            self.CallConditional(30, lambda : self.lm.initComplete, wait_for_guiutility)

        def wait_for_session():
            print >> sys.stderr, "tgs: waiting for session instance"
            self.CallConditional(30, lambda: Session.has_instance(), wait_for_instance)

        self.CallConditional(30, Session.has_instance, wait_for_session)

        # modify argv to let tribler think its running from a different directory
        sys.argv = [os.path.abspath('./.exe')]
        run()

    def Call(self, seconds, callback):
        if not self.quitting:
            if seconds:
                wx.CallLater(seconds * 1000, callback)
            elif not wx.Thread_IsMain():
                wx.CallAfter(callback)
            else:
                callback()

    def CallConditional(self, timeout, condition, callback, assertMsg=None):
        t = time()

        def DoCheck():
            if not self.quitting:
                if time() - t < timeout:
                    if condition():
                        print >> sys.stderr, "tgs: condition satisfied after %d seconds, calling callback" % (time() - t)
                        callback()
                    else:
                        self.Call(0.5, DoCheck)
                else:
                    print >> sys.stderr, "tgs: quitting, condition was not satisfied in %d seconds" % timeout
                    self.assert_(False, assertMsg if assertMsg else "Condition was not satisfied in %d seconds" % timeout, doassert=False)
        self.Call(0, DoCheck)

    def quit(self):
        if self.frame:
            self.frame.OnCloseWindow()
        else:
            self.Call(0, self.app.ExitMainLoop)
            self.Call(2.5, self.app.Exit)

        self.quitting = True

    def tearDown(self):
        self.annotate(self._testMethodName, start=False)

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
        print >> sys.stderr, "teardown: Number of threads still running", len(ts)
        for t in ts:
            print >> sys.stderr, "teardown: Thread still running", t.getName(), "daemon", t.isDaemon(), "instance:", t

        dhtlog = os.path.join(STATE_DIR, 'pymdht.log')
        if os.path.exists(dhtlog):
            print >> sys.stderr, "teardown: content of pymdht.log"
            f = open(dhtlog, 'r')
            for line in f:
                line = line.strip()
                if line:
                    print >> sys.stderr, line
            f.close()
            print >> sys.stderr, "teardown: finished printing content of pymdht.log"

        shutil.rmtree(STATE_DIR)
        shutil.rmtree(DEST_DIR)

        for boolean, reason in self.asserts:
            assert boolean, reason

        assert not os.path.exists(STATE_DIR), "state_dir (%s) should not exist" % STATE_DIR
        assert not os.path.exists(DEST_DIR), "dest_dir (%s) should not exist" % DEST_DIR

    def annotate(self, annotation, start=True, destdir="output"):
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

    def screenshot(self, title=None, destdir="output"):
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
            mem.DrawLabel(title, titlerect, wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL)
        del mem

        myWxImage = wx.ImageFromBitmap(bmp)
        im = Image.new('RGB', (myWxImage.GetWidth(), myWxImage.GetHeight()))
        im.fromstring(myWxImage.GetData())

        if not os.path.exists(destdir):
            os.makedirs(destdir)
        index = 1
        filename = os.path.join(destdir, 'Screenshot-%.2d.png' % index)
        while os.path.exists(filename):
            index += 1
            filename = os.path.join(destdir, 'Screenshot-%.2d.png' % index)
        im.save(filename)

        del bmp
