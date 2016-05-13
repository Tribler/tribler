#!/bin/bash

echo Export dist

mkdir -p dist/TriblerService

p4a export_dist \
--android_api=16 \
--dist_name=TriblerService \
--output=./dist/TriblerService
