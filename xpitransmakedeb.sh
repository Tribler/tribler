#!/bin/sh

rm -rf debian
cp -r */Transport/Build/Ubuntu debian
cd debian
dch -i --check-dirname-level 0
debuild --check-dirname-level 0

