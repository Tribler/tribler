#!/bin/sh

PYTHON=python2.3

# don't care about gtk/x11/whatever. Currently (3.4.0) must be unicode
WXPYTHONVER=`ls -1d /usr/lib/$PYTHON/site-packages/wx-2.6* | grep -v ansi | sed -e 's/.*wx-//g' -e 's/-.*//g' | sort -nr | head -1`
WXPYTHON=`ls -1d /usr/lib/$PYTHON/site-packages/wx-$WXPYTHONVER* | head -1`

PYTHONPATH=/usr/share/tribler/:$WXPYTHON
export PYTHONPATH

if [ ! -d $HOME/.Tribler ];
then
	mkdir $HOME/.Tribler
fi
exec $PYTHON /usr/share/tribler/abc.py > $HOME/.Tribler/stderr.log 2>&1
