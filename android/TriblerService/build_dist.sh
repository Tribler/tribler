#!/bin/bash

set -e

echo Build dist

cd dist/TriblerService

python build.py \
--package=org.tribler.android \
--service=Triblerd:Triblerd.py \
--private=../../service \
--whitelist=../../.p4a-whitelist

cd ../..
