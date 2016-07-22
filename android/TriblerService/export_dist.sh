#!/bin/bash

set -e

echo Export dist

mkdir -p dist

p4a export_dist \
--release \
--sdk_dir=/opt/android-sdk \
--ndk_dir=/opt/android-ndk \
--ndk_version=12b \
--android_api=16 \
--arch=armeabi-v7a \
--dist_name=TriblerService \
--bootstrap=service_only \
--requirements=libtribler_local \
./dist
