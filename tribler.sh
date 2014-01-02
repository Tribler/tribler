#!/bin/bash
# Run Tribler from source tree

if [ ! -e Tribler/Main/tribler.py ]; then
    echo "ERROR: Script must be called from source tree root"
    echo "  Try the following commands:"
    echo "cd $(dirname $0)"
    echo "./$(basename $0)"
    exit 1
fi

UNAME=$(uname -s)

if [ $UNAME == "Linux"]; then
    # Find the Tribler dir
    TRIBLER_DIR=$( dirname $(readlink -f "$0"))
    if [ ! -d "$TRIBLER_DIR" ]; then
        TRIBLER_DIR=$( dirname $(readlink -f $(which "$0")))
    fi
    if [ ! -d "$TRIBLER_DIR" ]; then
        echo "Couldn't figure out where Tribler is, bailing out."
        exit 1
    fi

    cd $TRIBLER_DIR

    PYTHONPATH=.:"$PYTHONPATH"

    export PYTHONPATH


    python Tribler/Main/tribler.py

else
    if [ $UNAME == "Darwin" ]; then

        PYTHONVER=2.5
        PYTHON=/usr/local/bin/python$PYTHONVER

        DIRCHANGE=`dirname $0`

        if [ $DIRCHANGE != "" ]; then
            cd $DIRCHANGE
        fi

        if [ ! -e "macbinaries" ]; then
            echo Please unpack macbinaries-`arch`.tar.gz here, so that the macbinaries directory will be created and filled with the binaries required for operation.
            exit -1
        fi

        export PYTHONPATH=`pwd`/macbinaries:`pwd`/lib/Library/Frameworks/Python.framework/Versions/2.5/lib/python2.5/site-packages/
        export DYLD_LIBRARY_PATH=`pwd`/macbinaries

        # use a hardlink so the script is in the current directory, otherwise
        # python will start to chdir all over the place
        rm -f tmp.py
        ln $1 tmp.py
        shift
        $PYTHON tmp.py $@
    fi
fi
