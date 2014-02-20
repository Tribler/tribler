# Written by Jelle Roozenburg, Arno Bakker
# see LICENSE.txt for license information

import sys
import commands
import wx
import logging


class SingleInstanceChecker(object):

    """ Looks for a process with argument basename.py """

    def __init__(self, basename):
        super(SingleInstanceChecker, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        if sys.platform != 'linux2':
            self._wx_instance_name = "tribler-" + wx.GetUserId()
            self._wx_checker = wx.SingleInstanceChecker(self._wx_instance_name)

        self._basename = basename

    def IsAnotherRunning(self):
        if sys.platform == 'linux2':
            return self.__get_process_num_on_linux()
        else:
            return self.__get_process_num_on_other()

    def __get_process_num_on_other(self):
        return self._wx_checker.IsAnotherRunning()

    def __get_process_num_on_linux(self):
        cmd = 'pgrep -fl "%s\.py" | grep -v pgrep' % (self._basename)
        progressInfo = commands.getoutput(cmd)

        self._logger.info(u"Linux cmd returned %s", progressInfo)

        numProcesses = len(progressInfo.split('\n'))
        return numProcesses > 1
