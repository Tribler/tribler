#!/bin/sh
# Startup script for Ubuntu Linux

check()
{
    # look for the python executable
    PYTHONBIN=`which $1`
    if [ "$PYTHONBIN" != "" ]; then
        _PYTHONBIN=$PYTHONBIN
    fi

    if [ -d "/usr/lib/$1" ]; then

        # look for the python-vlc library
        if [ -f "/usr/lib/$1/site-packages/vlc.so" ]; then
            _VLCPATH="/usr/lib/$1/site-packages"
        fi

        # look for the python-wx library
        WXPYTHONVER=`ls -1d /usr/lib/$1/site-packages/wx-2.8* 2>/dev/null | grep -v ansi | sed -e 's/.*wx-//g' -e 's/-.*//g' | sort -nr | head -1`
        if [ "$WXPYTHONVER" != "" ]; then
            _WXPYTHONPATH=`ls -1d /usr/lib/$1/site-packages/wx-$WXPYTHONVER* | grep -v ansi | head -1`
        fi
    fi
}

confirm()
{
    if [ "$1" = "" ]; then
        echo $2
        echo "Cannot run Tribler, sorry"
        exit 1
    fi
}

warn()
{
    if [ "$1" = "" ]; then
        echo $2
        echo "Some parts of Tribler may not function properly, sorry"
    fi
}

check "python2.4"
check "python2.5"
check "python2.6"

confirm "$_PYTHONBIN" "Unfortunatly we were not able to find python (version 2.4, 2.5, or 2.6)."
confirm "$_WXPYTHONPATH" "Unfortunatly we were not able to find a unicode package for wxPython 2.8 (python version 2.4, 2.5, or 2.6)."
warn "$_VLCPATH" "Unfortunatey we were not able to find the python bindings for vlc."

_TRIBLERPATH="/usr/share/tribler"

echo "_PYTHONBIN:    $_PYTHONBIN"
echo "_TRIBLERPATH:  $_TRIBLERPATH"
echo "_WXPYTHONPATH: $_WXPYTHONPATH"
echo "_VLCPATH:      $_VLCPATH"

export PYTHONPATH="$_TRIBLERPATH:$_PYTHONPATH:$_WXPYTHONPATH:$_VLCPATH"

echo "Starting Tribler..."
cd $_TRIBLERPATH
exec $_PYTHONBIN -O Tribler/Main/tribler.py "$@" > /tmp/$USER-tribler.log 2>&1
