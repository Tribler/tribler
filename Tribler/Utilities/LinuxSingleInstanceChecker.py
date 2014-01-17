# Written by Jelle Roozenburg, Arno Bakker
# see LICENSE.txt for license information

import sys
import commands
import logging


class LinuxSingleInstanceChecker:

    """ Looks for a process with argument basename.py """

    def __init__(self, basename):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.basename = basename

    def IsAnotherRunning(self):
        """ Uses pgrep to find other <self.basename>.py processes """
        # If no pgrep available, it will always start the app
        cmd = 'pgrep -fl "%s\.py" | grep -v pgrep' % (self.basename)
        progressInfo = commands.getoutput(cmd)

        self._logger.info("LinuxSingleInstanceChecker returned %s", progressInfo)

        numProcesses = len(progressInfo.split('\n'))
        # if DEBUG:
        #    print 'main: ProgressInfo: %s, num: %d' % (progressInfo, numProcesses)
        return numProcesses > 1
