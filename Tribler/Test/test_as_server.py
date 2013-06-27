# Written by Arno Bakker, Jie Yang
# Improved and Modified by Niels Zeilemaker
# see LICENSE.txt for license information

import unittest

import os
import sys
import tempfile
import random
import shutil
import time
import gc
import wx
import Image
from traceback import print_exc

from threading import enumerate as enumerate_threads

from Tribler.Core.Session import *
from Tribler.Core.SessionConfig import *
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
import re
from Tribler.Utilities import LinuxSingleInstanceChecker

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__))))
STATE_DIR = os.path.join(BASE_DIR, "test_.Tribler")
DEST_DIR = os.path.join(BASE_DIR, "test_TriblerDownloads")
FILES_DIR = os.path.abspath(os.path.join(BASE_DIR, 'data'))

from Tribler.Core import defaults
defaults.sessdefaults["state_dir"] = STATE_DIR
defaults.dldefaults["saveas"] = DEST_DIR

DEBUG = False


class AbstractServer(unittest.TestCase):

    def setup(self):
        self.setUpCleanup()

    def setUpCleanup(self):
        # Elric: If the files are still there it means that either the last run segfaulted or
        # that there was some kind of lock on those and the tearDown wasn't able to delete them.
        # In either case the test would fail, so just remove the dirs.
        for path in os.listdir(BASE_DIR):
            path = os.path.join(BASE_DIR, path)
            if path.startswith(STATE_DIR) or path.startswith(DEST_DIR):
                shutil.rmtree(path)

    def tearDown(self):
        self.tearDownCleanup()

    def tearDownCleanup(self):
        self.setUpCleanup()

    def getStateDir(self, nr=0):
        dir = STATE_DIR + (str(nr) if nr else '')
        if not os.path.exists(dir):
            os.mkdir(dir)
        return dir

    def getDestDir(self, nr=0):
        dir = DEST_DIR + (str(nr) if nr else '')
        if not os.path.exists(dir):
            os.mkdir(dir)
        return dir

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

        print >> f, time.time(), annotation, '1' if start else '0'
        f.close()


class TestAsServer(AbstractServer):

    """
    Parent class for testing the server-side of Tribler
    """

    def setUp(self):
        self.setUpCleanup()
        self.setUpPreSession()

        self.quitting = False

        self.session = Session(self.config)
        self.session.start()

        self.hisport = self.session.get_listen_port()

        while not self.session.lm.initComplete:
            time.sleep(1)

        self.annotate(self._testMethodName, start=True)

    def setUpPreSession(self):
        """ Should set self.config_path and self.config """
        self.config = SessionStartupConfig()
        self.config.set_state_dir(self.getStateDir())
        self.config.set_listen_port(random.randint(10000, 60000))
        self.config.set_torrent_checking(False)
        self.config.set_multicast_local_peer_discovery(False)
        self.config.set_megacache(False)
        self.config.set_dispersy(False)
        self.config.set_swift_proc(False)
        self.config.set_mainline_dht(False)
        self.config.set_torrent_collecting(False)
        self.config.set_libtorrent(False)
        self.config.set_dht_torrent_collecting(False)

    def tearDown(self):
        self.annotate(self._testMethodName, start=False)

        """ unittest test tear down code """
        if self.session is not None:
            self._shutdown_session(self.session)
            Session.del_instance()

        time.sleep(10)
        gc.collect()

        ts = enumerate_threads()
        print >> sys.stderr, "test_as_server: Number of threads still running", len(ts)
        for t in ts:
            print >> sys.stderr, "test_as_server: Thread still running", t.getName(), "daemon", t.isDaemon(), "instance:", t

        if SQLiteCacheDB.hasInstance():
            SQLiteCacheDB.getInstance().close_all()
            SQLiteCacheDB.delInstance()

        self.tearDownCleanup()

    def _shutdown_session(self, session):
        session_shutdown_start = time.time()
        waittime = 60

        session.shutdown()
        while not session.has_shutdown():
            diff = time.time() - session_shutdown_start
            assert diff < waittime, "test_as_server: took too long for Session to shutdown"

            print >> sys.stderr, "test_as_server: ONEXIT Waiting for Session to shutdown, will wait for an additional %d seconds" % (waittime - diff)
            time.sleep(1)

        print >> sys.stderr, "test_as_server: Session is shutdown"

    def assert_(self, boolean, reason=None, doassert=True):
        if not boolean:
            self.quit()
            assert boolean, reason

    def startTest(self, callback):
        self.quitting = False
        callback()

    def Call(self, seconds, callback):
        if not self.quitting:
            if seconds:
                time.sleep(seconds)
            callback()

    def CallConditional(self, timeout, condition, callback, assertMsg=None):
        t = time.time()

        def DoCheck():
            if not self.quitting:
                if time.time() - t < timeout:
                    if condition():
                        print >> sys.stderr, "test_as_server: condition satisfied after %d seconds, calling callback" % (time.time() - t)
                        callback()
                    else:
                        self.Call(0.5, DoCheck)
                else:
                    print >> sys.stderr, "test_as_server: quitting, condition was not satisfied in %d seconds (%s)" % (timeout, assertMsg or "no-assert-msg")
                    self.assert_(False, assertMsg if assertMsg else "Condition was not satisfied in %d seconds" % timeout, doassert=False)
        self.Call(0, DoCheck)

    def quit(self):
        self.quitting = True

class TestGuiAsServer(TestAsServer):

    """
    Parent class for testing the gui-side of Tribler
    """

    def setUp(self):
        self.setUpCleanup()

        self.app = wx.GetApp()
        if not self.app:
            self.app = wx.PySimpleApp(redirect=False)

        self.guiUtility = None
        self.frame = None
        self.lm = None
        self.session = None

        self.hadSession = False
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
        from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
        from Tribler.Main.tribler import run

        self.hadSession = False

        def wait_for_frame():
            print >> sys.stderr, "tgs: GUIUtility ready, staring to wait for frame to be ready"
            self.frame = self.guiUtility.frame
            self.frame.Maximize()
            self.CallConditional(30, lambda: self.frame.ready, callback)

        def wait_for_init():
            print >> sys.stderr, "tgs: lm initcomplete, staring to wait for GUIUtility to be ready"
            self.guiUtility = GUIUtility.getInstance()
            self.CallConditional(30, lambda: self.guiUtility.frame, wait_for_frame)

        def wait_for_guiutility():
            print >> sys.stderr, "tgs: waiting for guiutility instance"
            self.CallConditional(30, lambda: GUIUtility.hasInstance(), wait_for_init)

        def wait_for_instance():
            print >> sys.stderr, "tgs: found instance, staring to wait for lm to be initcomplete"
            self.session = Session.get_instance()
            self.lm = self.session.lm

            self.CallConditional(30, lambda: self.lm.initComplete, wait_for_guiutility)

        def wait_for_session():
            self.hadSession = True
            print >> sys.stderr, "tgs: waiting for session instance"
            self.CallConditional(30, lambda: Session.has_instance(), wait_for_instance)

        self.CallConditional(30, Session.has_instance, wait_for_session)

        # modify argv to let tribler think its running from a different directory
        sys.argv = [os.path.abspath('./.exe')]
        run()

        TestAsServer.startTest(self, wait_for_session)

        assert self.hadSession, 'Did not even create a session'

    def Call(self, seconds, callback):
        if not self.quitting:
            if seconds:
                wx.CallLater(seconds * 1000, callback)
            elif not wx.Thread_IsMain():
                wx.CallAfter(callback)
            else:
                callback()

    def quit(self):
        if self.frame:
            self.frame.OnCloseWindow()
        else:
            def do_quit():
                self.app.ExitMainLoop
                wx.WakeUpMainThread()

            self.Call(1, do_quit)
            self.Call(2.5, self.app.Exit)

        self.quitting = True

    def tearDown(self):
        self.annotate(self._testMethodName, start=False)

        """ unittest test tear down code """
        del self.guiUtility
        del self.frame
        del self.lm
        del self.session

        time.sleep(10)
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

        self.tearDownCleanup()

        for boolean, reason in self.asserts:
            assert boolean, reason

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
