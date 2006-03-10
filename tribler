#!/bin/sh

PYTHON=python2.3

# don't care about gtk/x11/whatever. Currently (3.3.3) must be ansi
WXPYTHONVER=`ls -1d /usr/lib/$PYTHON/site-packages/wx-2.6* | grep -v unicode | sed -e 's/.*wx-//g' -e 's/-.*//g' | sort -nr | head -1`
WXPYTHON=`ls -1d /usr/lib/$PYTHON/site-packages/wx-$WXPYTHONVER* | head -1`

PYTHONPATH=/usr/share/tribler/:$WXPYTHON
export PYTHONPATH

if [ ! -d $HOME/.ABC ];
then
	mkdir $HOME/.ABC
fi
exec $PYTHON /usr/share/tribler/abc.py > $HOME/.ABC/stderr.log 2>&1
