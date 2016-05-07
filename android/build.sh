#!/bin/bash

export ANDROIDSDK=/opt/android-sdk-linux
export ANDROIDNDK=/opt/android-ndk-r10e

export PATH="~/.local/bin/:$PATH"

#echo Get the latest P4A
#pip install --user --upgrade git+https://github.com/kivy/python-for-android.git

#copy bootstraps and recipes
cp -R bootstraps ~/.local/lib/python2.7/site-packages/pythonforandroid/
cp -R recipes ~/.local/lib/python2.7/site-packages/pythonforandroid/

#create dist and build
script -c "./clean_dist.sh"
script -a -c "./create_dist.sh"
script -a -c "./export_dist.sh"
script -a -c "./build_dist.sh"
script -a -c "./install_dist.sh"
