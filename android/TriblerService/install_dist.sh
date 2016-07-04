#!/bin/bash

echo Install dist

cd dist/TriblerService

mv libs jniLibs
mv python-install/include jni/include
mv python-install/lib jni/lib

rm -rf python-install
rm -rf collated_objects
rm -rf private
rm -rf python-install
rm -rf templates
rm -rf build
rm -r jni/*.mk
rm -r jni/src/*.mk
rm -f blacklist.txt
rm -f whitelist.txt
rm -f build.py
rm -f dist_info.json
rm -f project.properties

cd ../..

rm -rf dist/TriblerApp-import
mv dist/TriblerService dist/TriblerApp-import

rm -rf ../TriblerApp/app/src/main/assets
rm -rf ../TriblerApp/app/src/main/jni
rm -rf ../TriblerApp/app/src/main/jniLibs

cp -R dist/TriblerApp-import/assets ../TriblerApp/app/src/main
cp -R dist/TriblerApp-import/jni ../TriblerApp/app/src/main
cp -R dist/TriblerApp-import/jniLibs ../TriblerApp/app/src/main

