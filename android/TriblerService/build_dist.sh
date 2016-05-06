#!/bin/bash

python dist/TriblerService/build.py \
--package=org.tribler.android
--service=Triblerd:Triblerd.py
--private=./service
--whitelist=.p4a-whitelist
