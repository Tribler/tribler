# Written by Arno Bakker
# see LICENSE.txt for license information

"""
This file contains some constants used by the video playback in Tribler.
"""

PLAYBACKMODE_INTERNAL = 0
PLAYBACKMODE_EXTERNAL_DEFAULT = 1
PLAYBACKMODE_EXTERNAL_MIME = 2

# Arno: These modes are not what vlc returns, but Fabian's summary of that
MEDIASTATE_PLAYING = 1
MEDIASTATE_PAUSED = 2
MEDIASTATE_STOPPED = 3
MEDIASTATE_ENDED = 4
