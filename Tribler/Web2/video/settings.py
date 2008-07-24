# Written by Fabian van der Werf
# see LICENSE.txt for license information

import os
import os.path

from settings import *


if os.name == "nt":
    FFMPEG_FILE       =   os.path.join(os.path.dirname(os.path.realpath(os.sys.argv[0])), "res", "ffmpeg.exe") 
elif os.name == "posix":
    FFMPEG_FILE       =   os.path.join(os.path.dirname(os.path.realpath(os.sys.argv[0])), "res", "ffmpeg") 

VIDDECODE_CMD = [FFMPEG_FILE, "-i", None, "-vcodec", "mpeg2video", "-r", "30", "-ar", "44100", "-y", "-sameq", None]
VIDDECODE_CMD_IO = (2,11)

