#!/bin/bash

set -e

echo Install dist

cd dist/TriblerService

mv -f libs jniLibs
mv -f python-install/include jni/include
mv -f python-install/lib jni/lib

rm -rf python-install
rm -rf collated_objects
rm -rf private
rm -rf python-install
rm -rf templates
rm -rf build
rm -rf jni/*.mk
rm -rf jni/src/*.mk
rm -f blacklist.txt
rm -f whitelist.txt
rm -f build.py
rm -f dist_info.json
rm -f project.properties

cd ../..

rm -rf dist/TriblerApp-import
mv -f dist/TriblerService dist/TriblerApp-import

rm -rf ../TriblerApp/app/src/main/assets
rm -rf ../TriblerApp/app/src/main/jni
rm -rf ../TriblerApp/app/src/main/jniLibs

cp -rf dist/TriblerApp-import/assets ../TriblerApp/app/src/main
cp -rf dist/TriblerApp-import/jni ../TriblerApp/app/src/main
cp -rf dist/TriblerApp-import/jniLibs ../TriblerApp/app/src/main

echo Add VLC.apk to app assets
if [ -z $VLC_APK ]
then
    cp dist/VLC-Android-2.0.6-ARMv7.apk ../TriblerApp/app/src/main/assets
else
    cp $VLC_APK ../TriblerApp/app/src/main/assets
fi
