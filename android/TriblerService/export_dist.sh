#!/bin/bash

echo Export dist

mkdir -p dist

p4a export_dist \
--copy-libs \
--debug \
--android_api=16 \
--arch=armeabi-v7a \
--dist_name=TriblerService \
--bootstrap=service_only \
--requirements=libtribler_local \
--output=./dist
