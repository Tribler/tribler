__author__ = 'chris'

import subprocess
import sqlite3

subprocess.call(['scp', 'risto@pygmee.tribler.org:/home/risto/tribler/results.db', '.'])

db = sqlite3.connect("results.db")

stmt = db.execute('''
    SELECT rc.hops, COUNT(*) AS results, MIN(rc.bytes_down / rc.time) / 1024.0 AS minKBps, MAX(rc.bytes_down / rc.time) / 1024.0 AS maxKBps, AVG(rc.bytes_down / rc.time) / 1024.0 AS avgKBps
    FROM result r
        JOIN result_circuit rc ON r.result_id = rc.result_id
    GROUP BY rc.hops
    ORDER BY rc.hops''')

f = open('hop_speed.txt', 'w')

f.write("#hops\tresults\tmin_speed\tmax_speed\tavg_speed\n")
for row in stmt.fetchall():
    f.write("%d\t%d\t%.2f\t%.2f\t%.2f\n" % (row[0],row[1],row[2],row[3],row[4]))

f.close()
db.close()

subprocess.call(['./plot_results.plt'])
