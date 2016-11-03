#!/bin/bash

timestamp=$(date +%s)

echo Making screenshot
$ADB shell screencap -p | sed 's/\r$//' > $DEVICE.$timestamp.png
