#!/bin/sh
# Startup script for Ubuntu Linux

# don't care about gtk/x11/whatever. Currently (>= 3.4.0) must be unicode
WXPYTHONVER24=`ls -1d /usr/lib/python2.4/site-packages/wx-2.8* 2>/dev/null | grep -v ansi | sed -e 's/.*wx-//g' -e 's/-.*//g' | sort -nr | head -1`
WXPYTHONVER25=`ls -1d /usr/lib/python2.5/site-packages/wx-2.8* 2>/dev/null | grep -v ansi | sed -e 's/.*wx-//g' -e 's/-.*//g' | sort -nr | head -1`

if [ "$WXPYTHONVER24" = "" ] && [ "$WXPYTHONVER25" = "" ];
then
    echo "Hmmm... No wxPython unicode package found for python2.4 or 2.5, cannot run Tribler, sorry"
    exit -1
fi

if [ "$WXPYTHONVER25" = "" ];
then
    PYTHON="python2.4"
    WXPYTHONVER=$WXPYTHONVER24
    echo "Using python2.4"
else
    PYTHON="python2.5"
    WXPYTHONVER=$WXPYTHONVER25
    echo "Using python2.5"
fi

WXPYTHON=`ls -1d /usr/lib/$PYTHON/site-packages/wx-$WXPYTHONVER* | grep -v ansi | head -1`

PYTHONPATH=/usr/share/tribler/:$WXPYTHON
export PYTHONPATH

exec $PYTHON /usr/share/tribler/tribler.py "$@" > /tmp/$USER-tribler.log 2>&1
