# Written by Arno Bakker
# see LICENSE.txt for license information

import os
import sys
import logging

from traceback import print_exc

from Tribler.Core.Utilities.unicode import unicode2str

if sys.platform == 'win32':
    from Tribler.Core.Utilities.win32regchecker import Win32RegChecker, HKLM

from Tribler.Core.Video.defs import PLAYBACKMODE_INTERNAL, PLAYBACKMODE_EXTERNAL_MIME, PLAYBACKMODE_EXTERNAL_DEFAULT

videoextdefaults = ['aac', 'asf', 'avi', 'dv', 'divx', 'flac', 'flc', 'flv', 'mkv', 'mpeg', 'mpeg4', 'mpegts', 'mpg4', 'mp3', 'mp4', 'mpg', 'mkv', 'mov', 'm4v', 'ogg', 'ogm', 'ogv', 'oga', 'ogx', 'qt', 'rm', 'swf', 'ts', 'vob', 'wmv', 'wav', 'webm']

logger = logging.getLogger(__name__)


def win32_retrieve_video_play_command(ext, videourl):
    """ Use the specified extension of to find the player in the Windows registry to play the url (or file)"""
    registry = Win32RegChecker()

    logger.debug("videoplay: Looking for player for %s", unicode2str(videourl))
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
    except Exception:
        print_exc()

    if sys.platform == 'win32':
        l.append(PLAYBACKMODE_EXTERNAL_MIME)
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    else:
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    return l


# From: cherrypy.lib.httputil
def get_ranges(headervalue, content_length):
    """Return a list of (start, stop) indices from a Range header, or None.
    
    Each (start, stop) tuple will be composed of two ints, which are suitable
    for use in a slicing operation. That is, the header "Range: bytes=3-6",
    if applied against a Python string, is requesting resource[3:7]. This
    function will return the list [(3, 7)].
    
    If this function returns an empty list, you should return HTTP 416.
    """

    if not headervalue:
        return None

    result = []
    bytesunit, byteranges = headervalue.split("=", 1)
    for brange in byteranges.split(","):
        start, stop = [x.strip() for x in brange.split("-", 1)]
        if start:
            if not stop:
                stop = content_length - 1
            start, stop = int(start), int(stop)
            if start >= content_length:
                # From rfc 2616 sec 14.16:
                # "If the server receives a request (other than one
                # including an If-Range request-header field) with an
                # unsatisfiable Range request-header field (that is,
                # all of whose byte-range-spec values have a first-byte-pos
                # value greater than the current length of the selected
                # resource), it SHOULD return a response code of 416
                # (Requested range not satisfiable)."
                continue
            if stop < start:
                # From rfc 2616 sec 14.16:
                # "If the server ignores a byte-range-spec because it
                # is syntactically invalid, the server SHOULD treat
                # the request as if the invalid Range header field
                # did not exist. (Normally, this means return a 200
                # response containing the full entity)."
                return None
            result.append((start, stop + 1))
        else:
            if not stop:
                # See rfc quote above.
                return None
            # Negative subscript (last N bytes)
            result.append((content_length - int(stop), content_length))

    return result