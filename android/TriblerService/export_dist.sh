#!/bin/bash

echo Export dist

p4a export_dist \
--android_api=16 \
--dist_name=TriblerService \
--output=./dist
