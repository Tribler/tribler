#!/usr/bin/env python
#
# Written by Lipu Fei, 2014-01-29
#
# This file prints the directory where Python is installed.
#
import os
import sys

if __name__ == "__main__":
    print os.path.abspath(os.path.dirname(sys.executable))
