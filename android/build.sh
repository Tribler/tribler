#!/bin/bash

export ANDROIDSDK=/opt/android-sdk-linux
export ANDROIDNDK=/opt/android-ndk-r10e

export PATH="~/.local/bin/:$PATH"

#echo Get the latest P4A
#pip install --user --upgrade git+https://github.com/kivy/python-for-android.git

#copy recipes
cp -R recipes ~/.local/lib/python2.7/site-packages/pythonforandroid/

echo Start build APK
script -c "p4a --copy-libs --debug apk" # uses .p4a config file

