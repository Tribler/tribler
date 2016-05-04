#!/bin/bash

export ANDROIDSDK=/opt/android-sdk-linux
export ANDROIDNDK=/opt/android-ndk-r10e

export PATH="~/.local/bin/:$PATH"

#echo Get the latest P4A
#pip install --user --upgrade git+https://github.com/kivy/python-for-android.git

echo Export TriblerService build
script -c "p4a export_dist" # uses .p4a config file
