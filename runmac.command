#!/bin/bash
#
# This script helps running Tribler .py files from the source tree. It is not meant to be used by the masses.
# If you have not already done so, build the Mac-specific libraries by executing
#    cd mac && make
# This will also create a 'lib' symlink to 'mac/build/lib' when finished. Alternatively, you can
# let it point to built libraries in a different source tree.
#
# Next to this, you need wxPython 2.8-unicode and Python 2.5 installed.

PYTHONVER=2.5
PYTHON=python$PYTHONVER

DIRCHANGE=`dirname $0`

if [ $DIRCHANGE != "" ]
then
  cd $DIRCHANGE
fi

if [ ! -e "lib" ]
then
  echo Please let the 'lib' symlink point to your built libraries [typically mac/build/lib].
  exit -1
fi

export PYTHONPATH=lib/Library/Frameworks/Python.framework/Versions/$PYTHONVER/lib/python$PYTHONVER/site-packages
exec $PYTHON $@
