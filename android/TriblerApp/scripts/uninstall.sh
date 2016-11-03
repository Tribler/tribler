#!/bin/bash

echo Uninstall app
$ADB uninstall org.tribler.android

echo Remove appstate
$ADB shell rm -rf /sdcard/.Tribler
