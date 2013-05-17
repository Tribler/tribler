# Written by Arno Bakker
# see LICENSE.txt for license information

import os
import sys

from Tribler.Core.Utilities.unicode import unicode2str
if (sys.platform == 'win32'):
    from Tribler.Core.Utilities.win32regchecker import Win32RegChecker, HKLM

videoextdefaults = ['aac', 'asf', 'avi', 'dv', 'divx', 'flac', 'flc', 'flv', 'mkv', 'mpeg', 'mpeg4', 'mpegts', 'mpg4', 'mp3', 'mp4', 'mpg', 'mkv', 'mov', 'm4v', 'ogg', 'ogm', 'ogv', 'oga', 'ogx', 'qt', 'rm', 'swf', 'ts', 'vob', 'wmv', 'wav', 'webm']
# Ric: added svc ext. for enhancement layers
svcextdefaults = ['dat']

DEBUG = False


def win32_retrieve_video_play_command(ext, videourl):
    """ Use the specified extension of to find the player in the Windows registry to play the url (or file)"""
    registry = Win32RegChecker()

    if DEBUG:
        print >>sys.stderr, "videoplay: Looking for player for", unicode2str(videourl)
    if ext == '':
        return [None, None]

    contenttype = None
    winfiletype = registry.readRootKey(ext)
    if DEBUG:
        print >>sys.stderr, "videoplay: winfiletype is", winfiletype, type(winfiletype)
    if winfiletype is None or winfiletype == '':
        # Darn.... Try this: (VLC seems to be the one messing the registry up in the
        # first place)
        winfiletype = registry.readRootKey(ext, value_name="VLC.Backup")
        if winfiletype is None or winfiletype == '':
            return [None, None]
        # Get MIME type
    if DEBUG:
        print >>sys.stderr, "videoplay: Looking for player for ext", ext, "which is type", winfiletype

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
        if idx > 0 and (len(suo) - 1) >= idx+2 and suo[idx-1] == '"' and suo[idx+2] == '"':
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
        if DEBUG:
            print >>sys.stderr, "videoplay: new urlopen is", suo
    return [contenttype, suo.replace(replace, videourl)]


def win32_retrieve_playcmd_from_mimetype(mimetype, videourl):
    """ Use the specified MIME type to find the player in the Windows registry to play the url (or file)"""
    registry = Win32RegChecker()

    if DEBUG:
        print >>sys.stderr, "videoplay: Looking for player for", unicode2str(videourl)
    if mimetype == '' or mimetype is None:
        return [None, None]

    keyname = '\\SOFTWARE\\Classes\\MIME\\Database\\Content Type\\' + mimetype
    valuename = 'Extension'
    ext = registry.readKeyRecursively(HKLM, keyname, value_name=valuename)
    if DEBUG:
        print >>sys.stderr, "videoplay: ext winfiletype is", ext
    if ext is None or ext == '':
        return [None, None]
    if DEBUG:
        print >>sys.stderr, "videoplay: Looking for player for mime", mimetype, "which is ext", ext

    return win32_retrieve_video_play_command(ext, videourl)


def quote_program_path(progpath):
    idx = progpath.find(' ')
    if idx != -1:
        # Contains spaces, should quote if it's really path
        if not os.access(progpath, os.R_OK):
            if DEBUG:
                print >>sys.stderr, "videoplay: Could not find assumed progpath", progpath
            return None
        return '"' + progpath +'"'
    else:
        return progpath
