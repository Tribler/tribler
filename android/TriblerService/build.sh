#!/bin/bash

set -e

export PATH="~/.local/bin/:$PATH"

#./reinstall_p4a.sh

#copy bootstraps and recipes
cp -R bootstraps ~/.local/lib/python2.7/site-packages/pythonforandroid/
cp -R recipes ~/.local/lib/python2.7/site-packages/pythonforandroid/

#create dist and build
script -c "./clean_dist.sh"
script -a -c "./create_dist.sh"
script -a -c "./export_dist.sh"
script -a -c "./build_dist.sh"
script -a -c "./install_dist.sh"
