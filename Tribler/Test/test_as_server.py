# Written by Arno Bakker, Jie Yang
# Improved and Modified by Niels Zeilemaker
# see LICENSE.txt for license information
import gc
import logging
import os
import re
import shutil
import sys
import time
import unittest
from threading import enumerate as enumerate_threads
from traceback import print_exc

# set wxpython version before importing wx or anything from Tribler
import wxversion
wxversion.select("2.8-unicode")

import wx

from Tribler.Core import defaults
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Utilities.twisted_thread import reactor


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__))))
STATE_DIR = os.path.join(BASE_DIR, u"_test_.Tribler")
DEST_DIR = os.path.join(BASE_DIR, u"_test_TriblerDownloads")
FILES_DIR = os.path.abspath(os.path.join(BASE_DIR, u"data"))

defaults.sessdefaults['general']['state_dir'] = STATE_DIR
defaults.sessdefaults['general']['minport'] = -1
defaults.sessdefaults['general']['maxport'] = -1
defaults.sessdefaults['dispersy']['dispersy_port'] = -1

defaults.dldefaults["downloadconfig"]["saveas"] = DEST_DIR

DEBUG = False

OUTPUT_DIR = os.environ.get('OUTPUT_DIR', 'output')


class AbstractServer(unittest.TestCase):

    _annotate_counter = 0

    def setUp(self, annotate=True):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.setUpCleanup()
        self.annotate_dict = {}

        if annotate:
            self.annotate(self._testMethodName, start=True)

    def setUpCleanup(self):
        # Elric: If the files are still there it means that either the last run segfaulted or
        # that there was some kind of lock on those and the tearDown wasn't able to delete them.
        # In either case the test would fail, so just remove the dirs.
        for path in os.listdir(BASE_DIR):
            path = os.path.join(BASE_DIR, path)
            if path.startswith(STATE_DIR) or path.startswith(DEST_DIR):
                shutil.rmtree(unicode(path))

    def tearDown(self, annotate=True):
        self.tearDownCleanup()
        if annotate:
            self.annotate(self._testMethodName, start=False)

        delayed_calls = reactor.getDelayedCalls()
        if delayed_calls:
            self._logger.debug("The reactor was dirty:")
            for dc in delayed_calls:
                self._logger.debug(">     %s" % dc)
        self.assertFalse(delayed_calls, "The reactor was dirty when tearing down the test")

    def tearDownCleanup(self):
        self.setUpCleanup()

    def getStateDir(self, nr=0):
        state_dir = STATE_DIR + (str(nr) if nr else '')
        if not os.path.exists(state_dir):
            os.mkdir(state_dir)
        return state_dir

    def getDestDir(self, nr=0):
        dest_dir = DEST_DIR + (str(nr) if nr else '')
        if not os.path.exists(dest_dir):
            os.mkdir(dest_dir)
        return dest_dir

    def annotate(self, annotation, start=True, destdir=OUTPUT_DIR):
        if not os.path.exists(destdir):
            os.makedirs(destdir)

        if start:
            self.annotate_dict[annotation] = time.time()
        else:
            filename = os.path.join(destdir, u"annotations.txt")
            if os.path.exists(filename):
                f = open(filename, 'a')
            else:
                f = open(filename, 'w')
                print >> f, "annotation start end"

            AbstractServer._annotate_counter += 1
            _annotation = re.sub('[^a-zA-Z0-9_]', '_', annotation)
            _annotation = u"%d_" % AbstractServer._annotate_counter + _annotation

            print >> f, _annotation, self.annotate_dict[annotation], time.time()
            f.close()


class TestAsServer(AbstractServer):

    """
    Parent class for testing the server-side of Tribler
    """

    def setUp(self):
        super(TestAsServer, self).setUp(annotate=False)
        self.setUpPreSession()

        self.quitting = False

        self.session = Session(self.config)
        upgrader = self.session.prestart()
        while not upgrader.is_done:
            time.sleep(0.1)
        assert not upgrader.failed, upgrader.current_status
        self.session.start()

        self.hisport = self.session.get_listen_port()

        while not self.session.lm.initComplete:
            time.sleep(1)

        self.annotate(self._testMethodName, start=True)

    def setUpPreSession(self):
        """ Should set self.config_path and self.config """
        self.config = SessionStartupConfig()
        self.config.set_tunnel_community_enabled(False)
        self.config.set_tunnel_community_optin_dialog_shown(True)
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_checking(False)
        self.config.set_multicast_local_peer_discovery(False)
        self.config.set_megacache(False)
        self.config.set_dispersy(False)
        self.config.set_mainline_dht(False)
        self.config.set_torrent_store(False)
        self.config.set_torrent_collecting(False)
        self.config.set_libtorrent(False)
        self.config.set_dht_torrent_collecting(False)
        self.config.set_videoplayer(False)

    def tearDown(self):
        self.annotate(self._testMethodName, start=False)

        """ unittest test tear down code """
        if self.session is not None:
            self._shutdown_session(self.session)
            Session.del_instance()

        time.sleep(10)
        gc.collect()

        ts = enumerate_threads()
        self._logger.debug("test_as_server: Number of threads still running %d", len(ts))
        for t in ts:
            self._logger.debug("Thread still running %s, daemon: %s, instance: %s", t.getName(), t.isDaemon(), t)

        super(TestAsServer, self).tearDown(annotate=False)

    def _shutdown_session(self, session):
        session_shutdown_start = time.time()
        waittime = 60

        session.shutdown()
        while not session.has_shutdown():
            diff = time.time() - session_shutdown_start
            assert diff < waittime, "test_as_server: took too long for Session to shutdown"

            self._logger.debug(
                "Waiting for Session to shutdown, will wait for an additional %d seconds", (waittime - diff))
            time.sleep(1)

        self._logger.debug("Session has shut down")

    def assert_(self, boolean, reason=None, do_assert=True):
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

    def CallConditional(self, timeout, condition, callback, assertMsg=None, assertCallback=None):
        t = time.time()

        def DoCheck():
            if not self.quitting:
                if time.time() - t < timeout:
                    try:
                        if condition():
                            self._logger.debug("condition satisfied after %d seconds, calling callback '%s'",
                                               (time.time() - t), callback.__name__)
                            callback()
                        else:
                            self.Call(0.5, DoCheck)

                    except:
                        print_exc()
                        self.assert_(False, 'Condition or callback raised an exception, quitting (%s)' %
                                     (assertMsg or "no-assert-msg"), do_assert=False)
                else:
                    self._logger.debug("%s, condition was not satisfied in %d seconds (%s)",
                                       ('calling callback' if assertCallback else 'quitting'),
                                       timeout,
                                       assertMsg or "no-assert-msg")
                    assertcall = assertCallback if assertCallback else self.assert_
                    assertcall(False, assertMsg if assertMsg else "Condition was not satisfied in %d seconds" %
                               timeout, do_assert=False)
        self.Call(0, DoCheck)

    def quit(self):
        self.quitting = True


class TestGuiAsServer(TestAsServer):

    """
    Parent class for testing the gui-side of Tribler
    """

    def setUp(self):
        AbstractServer.setUp(self, annotate=False)

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

    def assert_(self, boolean, reason, do_assert=True):
        if not boolean:
            self.screenshot("ASSERT: %s" % reason)
            self.quit()

            self.asserts.append((boolean, reason))

            if do_assert:
                assert boolean, reason

    def startTest(self, callback, min_timeout=5, autoload_discovery=True):
        from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
        from Tribler.Main import tribler_main
        tribler_main.ALLOW_MULTIPLE = True
        tribler_main.SKIP_TUNNEL_DIALOG = True

        self.hadSession = False
        starttime = time.time()

        def call_callback():
            took = time.time() - starttime
            if took > min_timeout:
                callback()
            else:
                self.Call(min_timeout - took, callback)

        def wait_for_frame():
            self._logger.debug("GUIUtility ready, starting to wait for frame to be ready")
            self.frame = self.guiUtility.frame
            self.frame.Maximize()
            self.CallConditional(30, lambda: self.frame.ready, call_callback)

        def wait_for_init():
            self._logger.debug("lm initcomplete, starting to wait for GUIUtility to be ready")
            self.guiUtility = GUIUtility.getInstance()
            self.CallConditional(30, lambda: self.guiUtility.registered, wait_for_frame)

        def wait_for_guiutility():
            self._logger.debug("waiting for guiutility instance")
            self.lm = self.session.lm
            self.CallConditional(30, lambda: GUIUtility.hasInstance(), wait_for_init)

        def wait_for_instance():
            self._logger.debug("found instance, starting to wait for lm to be initcomplete")
            self.session = Session.get_instance()
            self.hadSession = True
            self.CallConditional(30, lambda: self.session.lm and self.session.lm.initComplete, wait_for_guiutility)

        self._logger.debug("waiting for session instance")
        self.CallConditional(30, Session.has_instance, lambda: TestAsServer.startTest(self, wait_for_instance))

        # modify argv to let tribler think its running from a different directory
        sys.argv = [os.path.abspath('./.exe')]
        tribler_main.run(autoload_discovery=autoload_discovery)

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
            def close_dialogs():
                for item in wx.GetTopLevelWindows():
                    if isinstance(item, wx.Dialog):
                        if item.IsModal():
                            item.EndModal(wx.ID_CANCEL)
                        else:
                            item.Destroy()
                    else:
                        item.Close()

            def do_quit():
                self.app.ExitMainLoop()
                wx.WakeUpMainThread()

            self.Call(1, close_dialogs)
            self.Call(2, do_quit)
            self.Call(3, self.app.Exit)

        self.quitting = True

    def tearDown(self):
        self.annotate(self._testMethodName, start=False)

        """ unittest test tear down code """
        del self.guiUtility
        del self.frame
        del self.lm
        del self.session

        time.sleep(1)
        gc.collect()

        ts = enumerate_threads()
        if ts:
            self._logger.debug("Number of threads still running %s", len(ts))
            for t in ts:
                self._logger.debug("Thread still running %s, daemon %s, instance: %s", t.getName(), t.isDaemon(), t)

        dhtlog = os.path.join(STATE_DIR, 'pymdht.log')
        if os.path.exists(dhtlog):
            self._logger.debug("Content of pymdht.log")
            f = open(dhtlog, 'r')
            for line in f:
                line = line.strip()
                if line:
                    self._logger.debug("> %s", line)
            f.close()
            self._logger.debug("Finished printing content of pymdht.log")

        AbstractServer.tearDown(self, annotate=False)

        for boolean, reason in self.asserts:
            assert boolean, reason

    def screenshot(self, title=None, destdir=OUTPUT_DIR, window=None):
        try:
            from PIL import Image
        except ImportError:
            self._logger.error("Could not load PIL: not making screenshots")
            return

        if window is None:
            app = wx.GetApp()
            window = app.GetTopWindow()
            if not window:
                self._logger.error("Couldn't obtain top window and no window was passed as argument, bailing out")
                return

        rect = window.GetClientRect()
        size = window.GetSize()
        rect = wx.Rect(rect.x, rect.y, size.x, size.y)

        screen = wx.WindowDC(window)
        bmp = wx.EmptyBitmap(rect.GetWidth(), rect.GetHeight() + 30)

        mem = wx.MemoryDC(bmp)
        mem.Blit(0, 30, rect.GetWidth(), rect.GetHeight(), screen, rect.GetX(), rect.GetY())

        titlerect = wx.Rect(0, 0, rect.GetWidth(), 30)
        mem.DrawRectangleRect(titlerect)
        if title:
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
