#!/bin/bash

echo Update app
$ADB install -r ../app/build/outputs/apk/app-debug.apk
