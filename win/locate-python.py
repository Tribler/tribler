"""
Print the directory where Python is installed.

Author(s): Lipu Fei
"""
from __future__ import print_function
import os
import sys

if __name__ == "__main__":
    print(os.path.abspath(os.path.dirname(sys.executable)))
