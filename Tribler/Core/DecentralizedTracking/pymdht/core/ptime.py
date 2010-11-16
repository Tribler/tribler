from sys import platform
import time


sleep = time.sleep

if platform == 'win32':
    time = time.clock
elif platform == 'linux2':
    time = time.time
else:
    raise 

