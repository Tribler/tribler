#!/bin/bash

# ==============
# MovePlugins.sh
# ==============
# Purpose: Move project directory plug-ins to plug-ins folder
# Description: Add files to be moved in the following format:
#
#    files[${#files[*]}]="SUBFOLDER/FILENAME"
#    files[${#files[*]}]="$HOME/.Tribler/plug-ins/SUBFOLDER"
#
# Note that the first of these couples must have a 0 index
# (see below).
# ==============

files[0]="Parser/IMDbParserPlugin.py"
files[${#files[*]}]="$HOME/.Tribler/plug-ins/Parser/"

files[${#files[*]}]="Parser/IMDbParser.yapsy-plugin"
files[${#files[*]}]="$HOME/.Tribler/plug-ins/Parser/"

files[${#files[*]}]="TorrentFinder/KatPhTorrentFinderPlugin.py"
files[${#files[*]}]="$HOME/.Tribler/plug-ins/TorrentFinder/"

files[${#files[*]}]="TorrentFinder/KatPhTorrentFinderPlugin.yapsy-plugin"
files[${#files[*]}]="$HOME/.Tribler/plug-ins/TorrentFinder/"

curdir=${PWD}"/"

for (( i = 0; i < ${#files[*]}; i=i+2 ))
do
    j=$i+1
    cd ${files[$j]}
    cp $curdir${files[$i]} "./"
done  
