#!/bin/bash

set -e

echo Clean dist

p4a clean_dists
p4a clean_bootstrap_builds

rm -rf dist/TriblerService/*
