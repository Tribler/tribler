#!/bin/bash

set -e

echo Clean dist

p4a clean_bootstrap_builds
p4a clean_dists

rm -rf dist/TriblerService/*
