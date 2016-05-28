#!/bin/bash

echo Export dist

mkdir -p dist

p4a export_dist \
--require-perfect-match \
--android_api=16 \
--dist_name=TriblerService \
--bootstrap=service_only \
--requirements=libtribler_local \
--output=./dist
