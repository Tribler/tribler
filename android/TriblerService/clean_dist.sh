#!/bin/bash

echo Clean dist

p4a clean_dists
p4a clean_bootstraps

rm -rf dist/TriblerService/*
