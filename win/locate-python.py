"""
Print the directory where Python is installed.

Author(s): Lipu Fei
"""
import os
import sys

if __name__ == "__main__":
    print os.path.abspath(os.path.dirname(sys.executable))
