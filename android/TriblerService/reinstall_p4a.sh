#!/bin/bash

pip uninstall python-for-android

rm -rf ~/.local/lib/python2.7/site-packages/pythonforandroid
rm -rf ~/.local/share/python-for-android

echo Get the latest P4A
pip install --user --upgrade git+https://github.com/kivy/python-for-android.git
