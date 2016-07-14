#!/bin/bash

echo Create dist

p4a create \
--force-build \
--require-perfect-match \
--copy-libs \
--debug \
--sdk_dir=/opt/android-sdk-linux \
--ndk_dir=/opt/android-ndk-r10e \
--android_api=16 \
--arch=armeabi-v7a \
--package=org.tribler.android \
--service=Triblerd:Triblerd.py \
--private=./service \
--dist_name=TriblerService \
--bootstrap=service_only \
--requirements=libtribler_local \
--whitelist=.p4a-whitelist
