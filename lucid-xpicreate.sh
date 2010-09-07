#!/bin/sh -x
#
# Script to build SwarmTransport on Ubuntu Linux
#

export LIBRARYNAME=Tribler
export XULRUNNER_IDL=$HOME/pkgs/xulrunner-1.9.1.7/share/idl/xulrunner-1.9.1.7/stable
export XULRUNNER_XPIDL=$HOME/pkgs/xulrunner-1.9.1.7/lib/xulrunner-1.9.1.7/xpidl

# ----- Clean up

/bin/rm -rf dist

# ----- Build

# Diego: building the deepest dir we get all of them.
mkdir -p dist/installdir/bgprocess/$LIBRARYNAME/Images

cp -r $LIBRARYNAME dist/installdir/bgprocess

rm dist/installdir/bgprocess/$LIBRARYNAME/Category/porncat.txt
rm dist/installdir/bgprocess/$LIBRARYNAME/Category/filter_terms.filter
rm dist/installdir/bgprocess/$LIBRARYNAME/*.txt
rm -rf dist/installdir/bgprocess/$LIBRARYNAME/Main
rm -rf dist/installdir/bgprocess/$LIBRARYNAME/Subscriptions
rm -rf dist/installdir/bgprocess/$LIBRARYNAME/Test/
rm -rf dist/installdir/bgprocess/$LIBRARYNAME/Web2/
rm -rf dist/installdir/bgprocess/$LIBRARYNAME/Images/*
rm -rf dist/installdir/bgprocess/$LIBRARYNAME/Video/Images
rm -rf dist/installdir/bgprocess/$LIBRARYNAME/Tools
rm -rf dist/installdir/bgprocess/$LIBRARYNAME/Plugin/*.html
rm -rf dist/installdir/bgprocess/$LIBRARYNAME/*/Build
rm -rf `find dist/installdir/bgprocess/$LIBRARYNAME -name .svn`
rm -rf `find dist/installdir/bgprocess/$LIBRARYNAME -name \*.pyc`

cp $LIBRARYNAME/Images/SwarmPlayerIcon.ico dist/installdir/bgprocess/$LIBRARYNAME/Images
cp $LIBRARYNAME/ns-LICENSE.txt dist/installdir
cp $LIBRARYNAME/ns-LICENSE.txt dist/installdir/LICENSE.txt

# ----- Build XPI of SwarmTransport
mv dist/installdir/bgprocess/$LIBRARYNAME/Transport/icon.png dist/installdir
mv dist/installdir/bgprocess/$LIBRARYNAME/Transport/install.rdf dist/installdir
mv dist/installdir/bgprocess/$LIBRARYNAME/Transport/chrome.manifest dist/installdir
mv dist/installdir/bgprocess/$LIBRARYNAME/Transport/components dist/installdir
mv dist/installdir/bgprocess/$LIBRARYNAME/Transport/skin dist/installdir
mv dist/installdir/bgprocess/$LIBRARYNAME/Transport/chrome dist/installdir
mv dist/installdir/bgprocess/$LIBRARYNAME/Transport/bgprocess/* dist/installdir/bgprocess
rm -rf dist/installdir/bgprocess/$LIBRARYNAME/Transport/bgprocess
rm dist/installdir/bgprocess/$LIBRARYNAME/Transport/*.html
rm dist/installdir/bgprocess/$LIBRARYNAME/Transport/*.tstream
rm dist/installdir/bgprocess/$LIBRARYNAME/Transport/*.sh
rm dist/installdir/bgprocess/$LIBRARYNAME/Transport/*.idl
rm dist/installdir/bgprocess/$LIBRARYNAME/Transport/*.txt



# ----- Turn .idl into .xpt
$XULRUNNER_XPIDL -m typelib -w -v -I $XULRUNNER_IDL -e dist/installdir/components/tribeIChannel.xpt $LIBRARYNAME/Transport/tribeIChannel.idl
$XULRUNNER_XPIDL -m typelib -w -v -I $XULRUNNER_IDL -e dist/installdir/components/tribeISwarmTransport.xpt $LIBRARYNAME/Transport/tribeISwarmTransport.idl

cd dist/installdir
# ----- Turn installdir into .xpi
zip -9 -r SwarmPlayer.xpi * 
mv SwarmPlayer.xpi ..
cd ../..
 
