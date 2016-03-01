import sys
import os
import urllib
import urlparse
import re
import time
import subprocess
import atexit

import wx

from Tribler.Core.simpledefs import dlstatus_strings, DLSTATUS_SEEDING, NTFY_ACT_NEW_VERSION
from Tribler.Core.exceptions import DuplicateDownloadException
from Tribler.Core.TorrentDef import TorrentDef

from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.vwxGUI import forceWxThread


def checkVersion(self):
    raise NotImplementedError("This next line needs to be called on the thread pool.")
    #call in thread pool(self._checkVersion, 5.0)


def _checkVersion(self):
    # Called from the ThreadPool
    my_version = self.utility.getVersion()
    try:
        curr_status = urllib.urlopen('http://tribler.org/version').readlines()
        line1 = curr_status[0]
        if len(curr_status) > 1:
            self.update_url = curr_status[1].strip()
        else:
            self.update_url = 'http://tribler.org'

        info = {}
        if len(curr_status) > 2:
            # the version file contains additional information in
            # "KEY:VALUE\n" format
            pattern = re.compile("^\s*(?<!#)\s*([^:\s]+)\s*:\s*(.+?)\s*$")
            for line in curr_status[2:]:
                match = pattern.match(line)
                if match:
                    key, value = match.group(1, 2)
                    if key in info:
                        info[key] += "\n" + value
                    else:
                        info[key] = value

        _curr_status = line1.split()
        self.curr_version = _curr_status[0]
        if self.newversion(self.curr_version, my_version):
            # Arno: we are a separate thread, delegate GUI updates to MainThread
            self.upgradeCallback()

            # Boudewijn: start some background downloads to
            # upgrade on this separate thread
            if len(info) > 0:
                self._upgradeVersion(my_version, self.curr_version, info)
            else:
                self._manualUpgrade(my_version, self.curr_version, self.update_url)

        # Also check new version of web2definitions for youtube etc. search
        # Web2Updater(self.utility).checkUpdate()
    except Exception as e:
        self._logger.error("Tribler: Version check failed %s %s", time.ctime(time.time()), str(e))
        # print_exc()


def _upgradeVersion(self, my_version, latest_version, info):
    # check if there is a .torrent for our OS
    torrent_key = "torrent-%s" % sys.platform
    notes_key = "notes-txt-%s" % sys.platform
    if torrent_key in info:
        self._logger.info("-- Upgrade %s -> %s", my_version, latest_version)
        notes = []
        if "notes-txt" in info:
            notes.append(info["notes-txt"])
        if notes_key in info:
            notes.append(info[notes_key])
        notes = "\n".join(notes)
        if notes:
            for line in notes.split("\n"):
                self._logger.info("-- Notes: %s", line)
        else:
            notes = "No release notes found"
        self._logger.info("-- Downloading %s for upgrade", info[torrent_key])

        # prepare directory and .torrent file
        location = os.path.join(self.utility.session.get_state_dir(), "upgrade")
        if not os.path.exists(location):
            os.mkdir(location)
        self._logger.info("-- Dir: %s", location)
        filename = os.path.join(location, os.path.basename(urlparse.urlparse(info[torrent_key])[2]))
        self._logger.info("-- File: %s", filename)
        if not os.path.exists(filename):
            urllib.urlretrieve(info[torrent_key], filename)

        # torrent def
        tdef = TorrentDef.load(filename)
        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        dscfg = defaultDLConfig.copy()

        # figure out what file to start once download is complete
        files = tdef.get_files_as_unicode()
        executable = None
        for file_ in files:
            if sys.platform == "win32" and file_.endswith(u".exe"):
                self._logger.info("-- exe: %s", file_)
                executable = file_
                break

            elif sys.platform == "linux2" and file_.endswith(u".deb"):
                self._logger.info("-- deb: %s", file_)
                executable = file_
                break

            elif sys.platform == "darwin" and file_.endswith(u".dmg"):
                self._logger.info("-- dmg: %s", file_)
                executable = file_
                break

        if not executable:
            self._logger.info("-- Abort upgrade: no file found")
            return

        # start download
        try:
            download = self.utility.session.start_download_from_tdef(tdef)

        except DuplicateDownloadException:
            self._logger.error("-- Duplicate download")
            download = None
            for random_download in self.utility.session.get_downloads():
                if random_download.get_def().get_infohash() == tdef.get_infohash():
                    download = random_download
                    break

        # continue until download is finished
        if download:
            def start_upgrade():
                """
                Called by python when everything is shutdown.  We
                can now start the downloaded file that will
                upgrade tribler.
                """
                executable_path = os.path.join(download.get_dest_dir(), executable)

                if sys.platform == "win32":
                    args = [executable_path]

                elif sys.platform == "linux2":
                    args = ["gdebi-gtk", executable_path]

                elif sys.platform == "darwin":
                    args = ["open", executable_path]

                self._logger.info("-- Tribler closed, starting upgrade")
                self._logger.info("-- Start: %s", args)
                subprocess.Popen(args)

            def wxthread_upgrade():
                """
                Called on the wx thread when the .torrent file is
                downloaded.  Will ask the user if Tribler can be
                shutdown for the upgrade now.
                """
                if self.Close():
                    atexit.register(start_upgrade)
                else:
                    self.shutdown_and_upgrade_notes = None

            def state_callback(state):
                """
                Called every n seconds with an update on the
                .torrent download that we need to upgrade
                """
                self._logger.debug("-- State: %s %s", dlstatus_strings[state.get_status()], state.get_progress())
                # todo: does DLSTATUS_STOPPED mean it has completely downloaded?
                if state.get_status() == DLSTATUS_SEEDING:
                    self.shutdown_and_upgrade_notes = notes
                    wx.CallAfter(wxthread_upgrade)
                    return (0.0, False)
                return (1.0, False)

            download.set_state_callback(state_callback)


@forceWxThread
def _manualUpgrade(self, my_version, latest_version, url):
    dialog = wx.MessageDialog(self, 'There is a new version of Tribler.\nYour version:\t\t\t\t%s\nLatest version:\t\t\t%s\n\nPlease visit %s to upgrade.' %
                              (my_version, latest_version, url), 'New version of Tribler is available', wx.OK | wx.ICON_INFORMATION)
    dialog.ShowModal()


def newversion(self, curr_version, my_version):
    curr = curr_version.split('.')
    my = my_version.split('.')
    if len(my) >= len(curr):
        nversion = len(my)
    else:
        nversion = len(curr)
    for i in range(nversion):
        if i < len(my):
            my_v = int(my[i])
        else:
            my_v = 0
        if i < len(curr):
            curr_v = int(curr[i])
        else:
            curr_v = 0
        if curr_v > my_v:
            return True
        elif curr_v < my_v:
            return False
    return False


@forceWxThread
def upgradeCallback(self):
    self.setActivity(NTFY_ACT_NEW_VERSION)
    wx.CallLater(6000, self.upgradeCallback)
