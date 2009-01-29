# Written by Diego Rabioli, Arno Bakker
# see LICENSE.txt for license information
#
# Run from console: "python createBGexe.py py2exe"
import os

from distutils.core import setup
import py2exe

from Tribler.__init__ import LIBRARYNAME
mainfile = os.path.join(LIBRARYNAME,'Plugin','BackgroundProcess.py')

setup(console=[mainfile]) 

