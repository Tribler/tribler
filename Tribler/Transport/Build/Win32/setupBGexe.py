# Written by Diego Rabioli, Arno Bakker
# see LICENSE.txt for license information
#
# Run from console: "python createBGexe.py py2exe"
import os

from distutils.core import setup
import py2exe # Not a superfluous import!

from Tribler.__init__ import LIBRARYNAME
mainfile = os.path.join(LIBRARYNAME,'Transport','SwarmEngine.py')

# Arno: 2009-06-09: changed from console= to make sure py2exe writes
# a BackgroundProcess.exe.log
#
setup(windows=[mainfile]) 

