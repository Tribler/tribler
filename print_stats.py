import sys
import hotshot, hotshot.stats
from time import time, sleep

stats = hotshot.stats.load("profiler_output.txt")

stats.strip_dirs()
stats.sort_stats('time', 'calls')
stats.print_stats(500)

sleep(1000000)