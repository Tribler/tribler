#!/bin/bash

echo Export dist

mkdir -p dist

p4a export_dist \
--android_api=16 \
--dist_name=TriblerService \
--output=./dist
