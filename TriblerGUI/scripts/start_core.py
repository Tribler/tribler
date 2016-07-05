import os
import sys


print os.environ['base_path']
sys.path.append(os.path.join(os.environ['base_path'], "twisted"))

from twisted.scripts.twistd import run
run()
