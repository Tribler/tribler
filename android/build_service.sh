#!/bin/bash

export ANDROIDSDK=/opt/android-sdk-linux
export ANDROIDNDK=/opt/android-ndk-r10e

export PATH="~/.local/bin/:$PATH"

#echo Get the latest P4A
#pip install --user --upgrade git+https://github.com/kivy/python-for-android.git

rm -rf dist/TriblerService/*

echo Export TriblerService build
p4a export_dist # uses .p4a config file

echo Copy build config
cd dist/TriblerService
cp ../.p4a ./.p4a

echo Build distribution
script -c "python build.py" # uses .p4a config file
