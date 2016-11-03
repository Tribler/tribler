#!/bin/bash

echo Install app and grant all runtime permissions
$ADB install -g ../app/build/outputs/apk/app-debug.apk
