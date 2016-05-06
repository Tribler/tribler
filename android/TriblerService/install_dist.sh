#!/bin/bash

echo Install dist

cd dist/TriblerService

rm -rf collated_objects
rm -rf private
rm -rf python-install
rm -rf templates
rm -rf build
rm -f blacklist.txt
rm -f whitelist.txt
rm -f build.py
rm -f dist_info.json
rm -f project.properties
rm -f local.properties

cd ../..

mv dist/TriblerService dist/TriblerApp
