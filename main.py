# coding: utf-8

"""
# Written by Wendo Sabée
# This file does little more than running ./service/main.py

import sys
import logging
import os

# SETUP ENVIRONMENT, DO THIS FIRST
from service.Environment import init_environment

init_environment()

# Print some interesting setup stuff before logger init
print 'os.getcwd(): %s' % os.getcwd()
print 'sys.platform: %s\nos.name: %s' % (sys.platform, os.name)

# Init logger
logging.basicConfig(level=logging.DEBUG)
_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    if os.environ['ANDROID_HOST'].startswith("ANDROID"):
        # Start android service
        from android import AndroidService

        service = AndroidService("TSAP Tribler Session", "A tribler session is running..")

        _logger.info("Starting service..")
        service.start()

    else:
        # Just run services/main.py
        import subprocess

        os.chdir(os.path.join(os.getcwd(), 'service'))
        subprocess.call(["python", "main.py"])"""

__version__ = "0.0.1"

import kivy
kivy.require('1.9.0')

import time
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.textinput import TextInput
from Tribler.Core.Utilities.twisted_thread import reactor, stop_reactor
import os, sys
import android
from binascii import hexlify, unhexlify

# SETUP ENVIRONMENT, DO THIS FIRST
from service.Environment import init_environment
init_environment()

# Init logger
import logging
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

arg = os.getenv('PYTHON_SERVICE_ARGUMENT')

# Setup the environment:
from jnius import autoclass
PythonActivity = autoclass('org.renpy.android.PythonActivity')
FILES_DIR = PythonActivity.mActivity.getFilesDir().getAbsolutePath()
os.environ["PYTHON_EGG_CACHE"] = FILES_DIR + '/files/.python-eggs' # TODO: set proper environment (it's already set in Environment.py)

from Tribler.Core.TorrentDef import TorrentDef

from service.XMLRpc import XMLRPCServer
from service.TriblerSession import TriblerSession
from service.ChannelManager import ChannelManager
from service.TorrentManager import TorrentManager
from service.DownloadManager import DownloadManager
from service.SettingsManager import SettingsManager

Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')

#URL = u'http://tracker.tasvideos.org/eryisaction-tas-bernka_512kb.mp4.torrent'
URL = u'http://www.mininova.org/get/3191238'

class TriblerPlay(App):

    tribler = None
    xmlrpc = None
    dm = None
    tm = None
    cm = None

    info_hash = None
    in_vod_mode = False
    started_streaming = False
    vod_uri = None

    # Called by Kivy
    def build(self):
        self.text_input = TextInput(text='Placeholder')
        print "----------------------RUNNING TRIBLER SETUP"
        tribler_play.setup()
        return self.text_input

    def setup(self):
        """
        This sets up a Tribler session, loads the managers and the XML-RPC server.
        :return: Nothing.
        """

        _logger.error("Loading XMLRPCServer")
        print "----------------------Loading XMLRPCServer"
        self.xmlrpc = XMLRPCServer(iface="0.0.0.0", port=8000)

        _logger.error("Loading TriblerSessionService")
        print "----------------------Loading TriblerSessionService"
        self.tribler = TriblerSession(self.xmlrpc)
        self.tribler.start_session()

        # Wait for dispersy to initialize
        print "----------------------Waiting for Dispersy to initialize"
        while not self.tribler.is_running():
            time.sleep(0.1)
        print "----------------------Dispersy is initialized!"

        # Disable ChannelManager
        #_logger.error("Loading ChannelManager")
        #self.cm = ChannelManager.getInstance(self.tribler.get_session(), self.xmlrpc)

        _logger.error("Loading TorrentManager")
        print "----------------------Loading TorrentManager"
        self.tm = TorrentManager.getInstance(self.tribler.get_session(), self.xmlrpc)

        _logger.error("Loading DownloadManager")
        print "----------------------Loading DownloadManager"
        self.dm = DownloadManager.getInstance(self.tribler.get_session(), self.xmlrpc)

        _logger.error("Loading ConfigurationManager")
        print "----------------------Loading ConfigurationManager"
        # Load this last because it sets settings in other managers
        self.sm = SettingsManager.getInstance(self.tribler.get_session(), self.xmlrpc)

        _logger.error("Now running XMLRPC on http://%s:%s/tribler" % (self.xmlrpc._iface, self.xmlrpc._port))
        print "----------------------Now running XMLRPC on http://%s:%s/tribler" % (self.xmlrpc._iface, self.xmlrpc._port)
        self.xmlrpc.start_server()

        # TODO: test streaming:
        tdef = TorrentDef.load_from_url(URL)
        if tdef is None:
            raise TypeError('Torrent could not be loaded from ' + URL + '. Check if you\'ve got an internet connection.')
        self.info_hash = hexlify(tdef.get_infohash())
        #self.tribler.get_session().set_install_dir(FILES_DIR + u'/lib/python2.7/site-packages')
        self.dm.add_torrent(self.info_hash, tdef.get_name())

        Clock.schedule_interval(lambda dt: self.poller(), 3.0)
        # TODO: end test streaming.

    def stop(self):
        self.tribler.stop_session()
        self.xmlrpc = None

    def keep_running(self):
        return self.tribler.is_running()

    def poller(self):
        if self.started_streaming:
            return
          
        downloads = self.tribler.get_session().get_downloads()
        if len(downloads) == 0:
            print "----------------------Download not started yet."
            return
        download = downloads[0]
        print "----------------------Download progress so far: " + str(download.progress)

        download_progress = self.dm.get_progress(self.info_hash)
        if download_progress == False:
            print "----------------------Can't query progress yet."
            return

        #print "----------------------vod_prebuf_frac = " + download_progress['vod_prebuf_frac']
        #print "----------------------down = " + download_progress['down']
        print "----------------------vod_eta = " + str(download_progress['vod_eta'])
        print "----------------------vod_playable = " + str(download_progress['vod_playable'])
        if download_progress["vod_playable"]:
            print "----------------------Download is VOD playable, starting external VLC player."
            self.started_streaming = True
            self.start_external_android_player()
        elif (download_progress["status"] == 3 or download_progress["status"] == 4 or download_progress["status"] == 5) and not self.in_vod_mode:
            print "----------------------Going into VOD mode."
            self.in_vod_mode = True
            self.vod_uri = self.dm.start_vod(self.info_hash)
            if self.vod_uri is False:
                raise TypeError('Could not start VOD download mode.')
        else:
            print "----------------------Not yet in VOD mode (and therefor also not yet started streaming)."

    def start_external_android_player(self):
        self.text_input.text = self.vod_uri # TODO: remove me, this is only for testing

        # Start the action chooser intent:
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(Uri.parse(self.vod_uri), "video/*")
        PythonActivity.mActivity.startActivity(Intent.createChooser(intent, "Complete action using"))

    def on_start(self):
        pass

    def on_stop(self):
        pass

    def on_pause(self):
        return True # Needed to start external VLC

    def on_resume(self):
        pass

if __name__ == '__main__':
    print "----------------------STARTING TRIBLER PLAY"
    tribler_play = TriblerPlay()
    tribler_play.run()

    # Needed when using the twisted XMLRPC server
    while tribler_play.keep_running():
        time.sleep(1)
