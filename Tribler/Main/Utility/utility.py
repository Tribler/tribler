# Written by ABC authors and Arno Bakker
# see LICENSE.txt for license information
import os
import ast
import sys

from random import gauss

from Tribler.Lang.lang import Lang
from Tribler.Core.__init__ import version_id
from Tribler.Core.Utilities.utilities import find_prog_in_PATH
from Tribler.Core.SessionConfig import CallbackConfigParser
from Tribler.Main.globals import DefaultDownloadStartupConfig

if sys.platform == 'win32':
    from Tribler.Main.Utility.regchecker import RegChecker

#
#
# Class: Utility
#
# Generic "glue" class that contains commonly used helper functions
#
#


class Utility:

    def __init__(self, abcpath, configpath):

        self.version = version_id
        self.abcpath = abcpath

        # Find the directory to save config files, etc.
        self.dir_root = configpath

        self.setupConfig()

        # Setup language files
        self.lang = Lang(self)

        warned = self.read_config('torrentassociationwarned')
        if (sys.platform == 'win32' and not warned):
            self.regchecker = RegChecker(self)
            self.write_config('torrentassociationwarned', 1)
        else:
            self.regchecker = None

        # Is ABC in the process of shutting down?
        self.abcquitting = False

    def setupConfig(self):
        tribler_defaults = {'language_file': 'english.lang',
                            'confirmonclose': 1,
                            # RateLimitPanel
                            'maxuploadrate': 0,
                            'maxdownloadrate': 0,
                            'maxseeduploadrate': 0,
                            # VideoPanel
                            'videoplaybackmode': 0,
                            # Misc
                            'torrentassociationwarned': 0,
                            # GUI
                            'window_width': 1024,
                            'window_height': 670,
                            'sash_position':-185,
                            't4t_option': 0, # Seeding items added by Boxun
                            't4t_ratio': 100, # T4T seeding ratio added by Niels
                            't4t_hours': 0,
                            't4t_mins': 30,
                            'g2g_option': 1,
                            'g2g_ratio': 75,
                            'g2g_hours': 0,
                            'g2g_mins': 30,
                            'family_filter': 1,
                            'window_x': "",
                            'window_y': "",
                            'use_bundle_magic': 0,
                            # WebUI
                            'use_webui': 0,
                            'webui_port': 8080,
                            # Swift reseed
                            'swiftreseed': 1}

        if sys.platform == 'win32':
            tribler_defaults['mintray'] = '2'
            tribler_defaults['videoplayerpath'] = os.path.expandvars('${PROGRAMFILES}') + '\\Windows Media Player\\wmplayer.exe'
            tribler_defaults['videoanalyserpath'] = self.getPath() + '\\ffmpeg.exe'
        elif sys.platform == 'darwin':
            tribler_defaults['mintray'] = '0'  # tray doesn't make sense on Mac
            tribler_defaults['videoplayerpath'] = find_prog_in_PATH("vlc") or ("/Applications/VLC.app" if os.path.exists("/Applications/VLC.app") else None) or "/Applications/QuickTime Player.app"
            tribler_defaults['videoanalyserpath'] = find_prog_in_PATH("ffmpeg") or "vlc/ffmpeg"
        else:
            tribler_defaults['mintray'] = '0'  # Still crashes on Linux sometimes
            tribler_defaults['videoplayerpath'] = find_prog_in_PATH("vlc") or "vlc"
            tribler_defaults['videoanalyserpath'] = find_prog_in_PATH("ffmpeg") or "ffmpeg"

        self.defaults = {'Tribler': tribler_defaults}
        self.configfilepath = os.path.join(self.getConfigPath(), "tribler.conf")
        self.config = CallbackConfigParser()

        # Load the config file.
        self.config.read(self.configfilepath)
        if not self.config.has_section('Tribler'):
            self.config.add_section('Tribler')

        # Tribler.conf also contains the default download config. So we need to merge it now.
        if not self.config.has_section('downloadconfig'):
            self.config.add_section('downloadconfig')
        for k, v in DefaultDownloadStartupConfig.getInstance().dlconfig._sections['downloadconfig'].iteritems():
            if not self.config.has_option('downloadconfig', k):
                self.config.set('downloadconfig', k, v)

        # Make sure we use the same ConfigParser instance for both Utility and DefaultDownloadStartupConfig.
        DefaultDownloadStartupConfig.getInstance().dlconfig = self.config

    def getVersion(self):
        return self.version

    def getConfigPath(self):
        return self.dir_root

    def getPath(self):
        return self.abcpath

    def getMaxDown(self):
        maxdownloadrate = self.read_config('maxdownloadrate')
        if maxdownloadrate == -1:
            return '0'
        elif maxdownloadrate == 0:
            return 'unlimited'
        return str(maxdownloadrate)

    def setMaxDown(self, valdown):
        if valdown == 'unlimited':
            self.write_config('maxdownloadrate', 0)
        elif valdown == '0':
            self.write_config('maxdownloadrate', -1)
        else:
            self.write_config('maxdownloadrate', valdown)

    def getMaxUp(self):
        maxuploadrate = self.read_config('maxuploadrate')
        if maxuploadrate == -1:
            return '0'
        elif maxuploadrate == 0:
            return 'unlimited'
        return str(maxuploadrate)

    def setMaxUp(self, valup):
        if valup == 'unlimited':
            self.write_config('maxuploadrate', 0)
            self.write_config('maxseeduploadrate', 0)
        elif valup == '0':
            self.write_config('maxuploadrate', -1)
            self.write_config('maxseeduploadrate', -1)
        else:
            self.write_config('maxuploadrate', valup)
            self.write_config('maxseeduploadrate', valup)

    def read_config(self, option, section='Tribler', literal_eval=True):
        if not self.config.has_option(section, option):
            return self.defaults.get(section, {}).get(option, None)

        return self.config.get(section, option, literal_eval=literal_eval)

    def write_config(self, option, value, section='Tribler', flush=False):
        self.config.set(section, option, value)
        if flush:
            self.flush_config()

    def flush_config(self):
        with open(self.configfilepath, "wb") as config_file:
            self.config.write(config_file)

    def eta_value(self, n, truncate=3):
        if n == -1:
            return '<unknown>'
        if not n:
            return ''
        n = int(n)
        week, r1 = divmod(n, 60 * 60 * 24 * 7)
        day, r2 = divmod(r1, 60 * 60 * 24)
        hour, r3 = divmod(r2, 60 * 60)
        minute, sec = divmod(r3, 60)

        if week > 1000:
            return '<unknown>'

        weekstr = '%d' % (week) + self.lang.get('l_week')
        daystr = '%d' % (day) + self.lang.get('l_day')
        hourstr = '%d' % (hour) + self.lang.get('l_hour')
        minutestr = '%d' % (minute) + self.lang.get('l_minute')
        secstr = '%02d' % (sec) + self.lang.get('l_second')

        if week > 0:
            text = weekstr
            if truncate > 1:
                text += ":" + daystr
            if truncate > 2:
                text += "-" + hourstr
        elif day > 0:
            text = daystr
            if truncate > 1:
                text += "-" + hourstr
            if truncate > 2:
                text += ":" + minutestr
        elif hour > 0:
            text = hourstr
            if truncate > 1:
                text += ":" + minutestr
            if truncate > 2:
                text += ":" + secstr
        else:
            text = minutestr
            if truncate > 1:
                text += ":" + secstr

        return text

    def speed_format(self, s):
        if s != None:
            if s < 102400:
                text = '%2.1f KB/s' % (s / 1024.0)
            elif s < 1022797:
                text = '%d KB/s' % (s // 1024)
            elif s < 104857600:
                text = '%2.1f MB/s' % (s / 1048576.0)
            elif s < 1047527425:
                text = '%d MB/s' % (s // 1048576)
            elif s < 107374182400:
                text = '%2.1f GB/s' % (s / 1073741824.0)
            elif s < 1072668082177:
                text = '%d GB/s' % (s // 1073741824)
            else:
                text = '%2.1f TB/s' % (s // 1099511627776)

            return text
        return ''

    def size_format(self, s, truncate=None, stopearly=None, applylabel=True, rawsize=False, showbytes=False, labelonly=False, textonly=False):
        size = 0.0

        if truncate is None:
            truncate = 2

        if ((s < 1024) and showbytes and stopearly is None) or stopearly == "Byte":
            truncate = 0
            size = s
            text = "Byte"
        elif ((s < 1048576) and stopearly is None) or stopearly == "KB":
            size = (s / 1024.0)
            text = "KB"
        elif ((s < 1073741824) and stopearly is None) or stopearly == "MB":
            size = (s / 1048576.0)
            text = "MB"
        elif ((s < 1099511627776) and stopearly is None) or stopearly == "GB":
            size = (s / 1073741824.0)
            text = "GB"
        else:
            size = (s / 1099511627776.0)
            text = "TB"

        if textonly:
            return text

        label = self.lang.get(text)
        if labelonly:
            return label

        if rawsize:
            return size

        # At this point, only accepting 0, 1, or 2
        if truncate == 0:
            text = ('%.0f' % size)
        elif truncate == 1:
            text = ('%.1f' % size)
        else:
            text = ('%.2f' % size)

        if applylabel:
            text += ' ' + label

        return text

    def round_range(self, x):
        returnar = set()
        for _ in range(2500):
            value = int(gauss(x, 100))
            if value < 0:
                continue

            diff = abs(value - x)
            if diff < 2:
                pass
            elif diff < 10 and x < 50:
                value = int(round(value / 3.0) * 3)
            elif diff < 75:
                value = int(round(value / 25.0) * 25)
            elif diff < 450:
                value = int(round(value / 75.0) * 75)
            else:
                value = int(round(value / 150.0) * 150)

            returnar.add(value)
        returnar = sorted(returnar)
        return returnar
