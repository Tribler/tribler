# Written by Arno Bakker
# see LICENSE.txt for license information

import sys

from Tribler.Core.simpledefs import *
from Tribler.Core.DownloadConfig import DownloadConfigInterface
from Tribler.Core.APIImplementation.DownloadRuntimeConfigBaseImpl import DownloadRuntimeConfigBaseImpl
from Tribler.Core.exceptions import OperationNotPossibleAtRuntimeException

DEBUG = False

# 10/02/10 Boudewijn: pylint points out that member variables used in
# DownloadRuntimeConfig do not exist.  This is because they are set in
# Tribler.Core.Download which is a subclass of DownloadRuntimeConfig.
#
# We disable this error
# pylint: disable-msg=E1101

class SwiftDownloadRuntimeConfig(DownloadRuntimeConfigBaseImpl):
    """
    Implements the Tribler.Core.DownloadConfig.DownloadConfigInterface
    
    Only implement the setter for parameters that are actually runtime
    configurable here. Default behaviour implemented by BaseImpl.
    
    DownloadConfigInterface: All methods called by any thread
    """
    def set_max_speed(self,direct,speed):
        if DEBUG:
            print >>sys.stderr,"SwiftDownload: set_max_speed",self.get_def().get_name(),direct,speed
        #print_stack()
        
        self.dllock.acquire()
        try:
            # Don't need to throw an exception when stopped, we then just 
            # save the new value and use it at (re)startup.
            if self.sp is not None:
                self.sp.set_max_speed(self,direct,speed)
                
            # At the moment we can't catch any errors in the engine that this 
            # causes, so just assume it always works.
            DownloadConfigInterface.set_max_speed(self,direct,speed)
        finally:
            self.dllock.release()
