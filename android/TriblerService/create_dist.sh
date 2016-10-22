#!/bin/bash

set -e

echo Create dist

p4a create \
--force-build \
--require-perfect-match \
--release \
--sdk_dir=/opt/android-sdk \
--ndk_dir=/opt/android-ndk \
--ndk_version=13 \
--android_api=18 \
--arch=armeabi-v7a \
--package=org.tribler.android \
--service=Triblerd:Triblerd.py \
--private=./service \
--dist_name=TriblerService \
--bootstrap=service_only \
--requirements=libtribler_local \
--whitelist=.p4a-whitelist
