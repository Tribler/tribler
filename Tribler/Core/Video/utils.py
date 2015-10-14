# Written by Arno Bakker
# see LICENSE.txt for license information

import os
import sys
import logging

from traceback import print_exc

if sys.platform == 'win32':
    from Tribler.Core.Utilities.win32regchecker import Win32RegChecker

from Tribler.Core.Video.defs import PLAYBACKMODE_INTERNAL, PLAYBACKMODE_EXTERNAL_MIME, PLAYBACKMODE_EXTERNAL_DEFAULT

videoextdefaults = ['aac', 'asf', 'avi', 'dv', 'divx', 'flac', 'flc', 'flv', 'mkv', 'mpeg', 'mpeg4', 'mpegts',
                    'mpg4', 'mp3', 'mp4', 'mpg', 'mkv', 'mov', 'm4v', 'ogg', 'ogm', 'ogv', 'oga', 'ogx', 'qt',
                    'rm', 'swf', 'ts', 'vob', 'wmv', 'wav', 'webm']

logger = logging.getLogger(__name__)


def win32_retrieve_video_play_command(ext, videourl):
    """ Use the specified extension of to find the player in the Windows registry to play the url (or file)"""
    registry = Win32RegChecker()

    logger.debug("videoplay: Looking for player for %s", repr(videourl))
    if ext == '':
        return [None, None]

    winfiletype = registry.readRootKey(ext)
    logger.debug("videoplay: winfiletype is %s %s", winfiletype, type(winfiletype))
    if winfiletype is None or winfiletype == '':
        # Darn.... Try this: (VLC seems to be the one messing the registry up in the
        # first place)
        winfiletype = registry.readRootKey(ext, value_name="VLC.Backup")
        if winfiletype is None or winfiletype == '':
            return [None, None]
        # Get MIME type
    logger.debug("videoplay: Looking for player for ext %s which is type %s", ext, winfiletype)

    contenttype = registry.readRootKey(ext, value_name="Content Type")

    playkey = winfiletype + "\shell\play\command"
    urlopen = registry.readRootKey(playkey)
    if urlopen is None:
        openkey = winfiletype + "\shell\open\command"
        urlopen = registry.readRootKey(openkey)
        if urlopen is None:
            return [None, None]

    # Default is e.g. "C:\Program Files\Windows Media Player\wmplayer.exe" /prefetch:7 /Play "%L"
    # Replace %L
    suo = urlopen.strip()  # spaces
    idx = suo.find('%L')
    if idx == -1:
        # Hrrrr: Quicktime uses %1 instead of %L and doesn't seem to quote the program path
        idx = suo.find('%1')
        if idx == -1:
            return [None, None]
        else:
            replace = '%1'
            idx2 = suo.find('%2', idx)
            if idx2 != -1:
                # Hmmm, a trailer, let's get rid of it
                if suo[idx - 1] == '"':
                    suo = suo[:idx + 3]  # quoted
                else:
                    suo = suo[:idx + 1]
    else:
        replace = '%L'

    # St*pid quicktime doesn't properly quote the program path, e.g.
    # C:\Program Files\Quicktime\bla.exe "%1" instead of
    # "C:\Program Files\Quicktime\bla.exe" "%1"
    if suo[0] != '"':
        if idx > 0 and (len(suo) - 1) >= idx + 2 and suo[idx - 1] == '"' and suo[idx + 2] == '"':
            # %x is quoted
            end = max(0, idx - 2)
        else:
            end = max(0, idx - 1)
        # I assume everthing till end is the program path
        progpath = suo[0:end]
        qprogpath = quote_program_path(progpath)
        if qprogpath is None:
            return [None, None]
        suo = qprogpath + suo[end:]
        logger.debug("videoplay: new urlopen is %s", suo)
    return [contenttype, suo.replace(replace, videourl)]


def quote_program_path(progpath):
    idx = progpath.find(' ')
    if idx != -1:
        # Contains spaces, should quote if it's really path
        if not os.access(progpath, os.R_OK):
            logger.debug("videoplay: Could not find assumed progpath %s", progpath)
            return None
        return '"' + progpath + '"'
    else:
        return progpath


def escape_path(path):
    if path[0] != '"' and path[0] != "'" and path.find(' ') != -1:
        if sys.platform == 'win32':
            # Add double quotes
            path = "\"" + path + "\""
        else:
            path = "\'" + path + "\'"
    return path


def return_feasible_playback_modes():
    if sys.platform == 'darwin':
        return [PLAYBACKMODE_EXTERNAL_DEFAULT]

    l = []
    try:
        # Make sure libvlc.dll will be found on windows
        if sys.platform.startswith('win'):
            env_entry =  os.path.join(os.path.dirname(sys.argv[0]), "vlc")
            if not env_entry in os.environ['PATH']:
                os.environ['PATH'] += ";" + env_entry

        import Tribler.vlc as vlc

        # Niels: check version of vlc
        version = vlc.libvlc_get_version()
        subversions = version.split(".")
        if len(subversions) > 2:
            version = subversions[0] + "." + subversions[1]
        version = float(version)
        if version < 0.9:
            raise Exception("Incorrect vlc version. We require at least version 0.9, this is %s" % version)

        l.append(PLAYBACKMODE_INTERNAL)
    except NameError:
        logger.error("libvlc_get_version couldn't be called, no playback possible")
    except Exception:
        print_exc()

    if sys.platform == 'win32':
        l.append(PLAYBACKMODE_EXTERNAL_MIME)
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    else:
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    return l
