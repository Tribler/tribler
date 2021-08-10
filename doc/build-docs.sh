#!/bin/bash
# Script to build Tribler documentation
# Note: Run the script from root directory, eg.
# ./doc/build-docs.sh

if [[ ! -d doc ]]
then
  # shellcheck disable=SC2028
  echo "Please run this script from project root as:\n./doc/build-docs.sh"
fi

# Update git modules if necessary
git submodule sync
git submodule update --init --force --recursive src/pyipv8

# all commands are executed from the doc directory
cd doc

# Remove venv and _build directory if exists
if [ -d "venv" ]; then rm -Rf venv; fi
if [ -d "_build" ]; then rm -Rf _build; fi

# Create a new virtual environment
PYTHON=python3
$PYTHON -m pip install virtualenv
$PYTHON -m virtualenv venv
venv/bin/python -m pip install --upgrade --no-cache-dir pip setuptools

# the below dependencies (and specific version) are set by ReadTheDocs builder.
# Some of these dependencies are overridden later in requirements.txt.
doc/venv/bin/python -m pip install --upgrade --no-cache-dir \
  mock==1.0.1 \
  pillow==5.4.1 \
  "alabaster>=0.7,<0.8,!=0.7.5" \
  commonmark==0.8.1 \
  recommonmark==0.5.0 \
  sphinx<2 \  # this is overridden in requirements.txt
  "sphinx-rtd-theme<0.5" \
  "readthedocs-sphinx-ext<2.2"

venv/bin/python -m pip install --exists-action=w --no-cache-dir -r requirements.txt

# Build on different output formats
venv/bin/python -m sphinx -T -E -b html -d _build/doctrees -D language=en . _build/html
venv/bin/python -m sphinx -b latex -D language=en -d _build/doctrees . _build/latex
venv/bin/python -m sphinx -T -b epub -d _build/doctrees -D language=en . _build/epub
