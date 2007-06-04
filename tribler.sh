#!/bin/sh

# Debian people haven't made python2.4-wxgtk2.6 available, hack around that
PYTHON=python2.5
EXECPYTHON=python2.5

# don't care about gtk/x11/whatever. Currently (3.4.0) must be unicode
WXPYTHONVER=`ls -1d /usr/lib/$PYTHON/site-packages/wx-2.6* | grep -v ansi | sed -e 's/.*wx-//g' -e 's/-.*//g' | sort -nr | head -1`
if [ "$WXPYTHONVER" = "" ];
then
	echo "Hmmm... No wxPython unicode package found for $PYTHON, cannot run Tribler, sorry"
	exit -1
fi	
WXPYTHON=`ls -1d /usr/lib/$PYTHON/site-packages/wx-$WXPYTHONVER* | grep -v ansi | head -1`

PYTHONPATH=/usr/share/tribler/:$WXPYTHON
export PYTHONPATH

exec $EXECPYTHON /usr/share/tribler/tribler.py > /tmp/$USER-tribler.log 2>&1
