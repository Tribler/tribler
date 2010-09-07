#!/bin/sh -x
#
# Written by Riccardo Petrocco
# see LICENSE.txt for license information
#
# Script to build SwarmTransport on Mac
#
# Build notes:
# - using libraries from macbinaries
# - simplejson needs to be installed for py2app to work
# - The latest version of XULrunner, working with the latest
#   Firefox, has a bug with libidl:
#   - install libidl with macports: /opt/local/bin/port
#   - link it: ln -s /opt/local/lib/libintl.8.dylib /opt/local/lib/libintl.3.dylib
#

APPNAME=SwarmPlayer
PYTHON_VER=2.5
PWD:=${shell pwd}
ARCH:=${shell arch}

PYTHON=python${PYTHON_VER}


export LIBRARYNAME=Tribler

xul_dir="../xulrunner-sdk/sdk/bin"

if [ -f $xul_dir/xpidl ]; then
    echo "Found XULRUNNER directory $xul_dir"
    export XULRUNNER_IDL=../xulrunner-sdk/idl
    export XULRUNNER_XPIDL=../xulrunner-sdk/sdk/bin/xpidl

else
	echo "|==============================================================================|"
	echo "| Failed to locate XULRUNNER directory, please modify the xul_dir variable |"
	echo "|==============================================================================|"
	exit
fi 

# ----- TODO check if we have the macbinaries

macbinaries=${PWD}/macbinaries
echo $macbinaries

if [ ! -d $macbinaries ]; then
    echo "No macbinaries"
    exit

else
    echo "Found macbinaries directory $macbinaries" 
fi

# ----- Set python paths TODO dynamic checkout
export PYTHONPATH=$macbinaries:${PWD}:$macbinaries/lib/python2.5/site-packages/
# apparently not needed.. TODO
export DYLD_LIBRARY_PATH=$macbinaries



# ----- Clean up
/bin/rm -rf dist build

# ----- Build
${PYTHON} -OO - < ${LIBRARYNAME}/Transport/Build/Mac/setupBGapp.py py2app 

mkdir -p dist/installdir/bgprocess
mv dist/SwarmPlayer.app dist/installdir/bgprocess/.
chmod 777 dist/installdir/bgprocess/SwarmPlayer.app/Contents/MacOS/SwarmPlayer

# ----- Build XPI of SwarmTransport
cp $LIBRARYNAME/Transport/icon.png dist/installdir
cp $LIBRARYNAME/Transport/install.rdf dist/installdir
cp $LIBRARYNAME/Transport/chrome.manifest dist/installdir
cp -rf $LIBRARYNAME/Transport/components dist/installdir
cp -rf $LIBRARYNAME/Transport/skin dist/installdir
cp -rf $LIBRARYNAME/Transport/chrome dist/installdir
rm -rf `find dist/installdir -name .svn`


# ----- Turn .idl into .xpt
export DYLD_LIBRARY_PATH=

$XULRUNNER_XPIDL -m typelib -w -v -I $XULRUNNER_IDL -e dist/installdir/components/tribeIChannel.xpt $LIBRARYNAME/Transport/tribeIChannel.idl
$XULRUNNER_XPIDL -m typelib -w -v -I $XULRUNNER_IDL -e dist/installdir/components/tribeISwarmTransport.xpt $LIBRARYNAME/Transport/tribeISwarmTransport.idl

cd dist/installdir
# ----- Turn installdir into .xpi
zip -9 -r SwarmPlayer.xpi * 
mv SwarmPlayer.xpi ..
cd ../..

