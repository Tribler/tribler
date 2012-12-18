#!/usr/bin/env python
# Mircea Bardac
# Partial rewrite by Elric Milon (Dec. 2012)
# TODO: needs documentation

import subprocess
from time import sleep, time
from sys import argv, exit
from os import setpgrp, getpgrp, killpg, getpid, access, R_OK, path
from signal import SIGKILL, SIGTERM, signal
from glob import iglob

class ResourceMonitor(object):
    # adapted after http://stackoverflow.com/questions/276052/how-to-get-current-cpu-and-ram-usage-in-python

    def make_string_list(self, element_list):
        string_list = ""
        for e in element_list:
            string_list = string_list + str(e) + ","
        string_list = string_list[:-1]
        return string_list

    def __init__(self, pid_list):
        """Create new ResourceMonitor instance."""
        self.pid_list = pid_list
        self.process_group_id = getpgrp()
        self.own_pid = getpid()
        #print "PGRP ID:", self.process_group_id

    def get_raw_stats(self):
        for pid in self.pid_list:
            if pid == self.own_pid:
                self.pid_list.remove(pid)
                continue
            try:
                status = open('/proc/%s/stat' % pid, 'r' ).read()[:-1] #Skip the newline
                stats = [status]
                for line in open('/proc/%s/io' % pid, 'r' ).readlines():
                    stats.append(line.split(': ')[1][:-1]) #Skip the newline
                yield ' '.join(stats)
            except IOError:
                #print "Process with PID %s died." % pid
                self.pid_list.remove(pid)
            #self.monitor_file.flush()

    def is_everyone_dead(self):
        if len(self.pid_list) == 0:
            #If the process list is empty, update it just in case a subprocess fork()ed in the last moment.
            self.update_pid_tree()
        return len(self.pid_list) == 0

    def update_pid_tree(self):
        """Update the list of all PIDs in the process group"""
        #print 'i',parent_pids
        for pid_dir in iglob('/proc/[1-9]*'):
            pid = int(pid_dir.split('/')[-1])
            if pid in self.pid_list or pid == self.own_pid:
                continue
            stat_file = path.join(pid_dir, 'stat')
            io_file = path.join(pid_dir, 'io')
            if access(stat_file, R_OK) and access(io_file, R_OK):
                pgrp = int(open(stat_file, 'r').read().split()[4]) # 4 is PGRP
                if pgrp == self.process_group_id:
                    #This process if from our process group, add it to the pid list.
                    #print "New process with PID %s found in the group, adding it" % pid
                    #print "   ", open(stat_file, 'r').read()
                    self.pid_list.append(pid)

class ProcessController(object):
    def __init__(self, output_dir):
        self.cmd_id = 0
        self.pid_list = {}
        self.processes = []
        self.files = []
        self.output_dir = output_dir
        setpgrp() # creat new process group and become its leader

    def run(self, cmd):
        output_filename = output_dir + "/%05d.out" %self.cmd_id
        error_filename = output_dir + "/%05d.err" %self.cmd_id

        stdout = open(output_filename, "w")
        stderr = open(error_filename, "w")
        print >> stdout, "Starting #%05d: %s" %(self.cmd_id, cmd)

        p = subprocess.Popen(cmd, shell=True, stdout=stdout, stderr=stderr, close_fds=True)

        self.processes.append(p)
        self.files.append(stdout)
        self.files.append(stderr)

        self.pid_list[p.pid] = self.cmd_id
        self.cmd_id = self.cmd_id + 1

    def terminate(self):
        for file in self.files:
            try:
                file.flush()
                file.close()
            except:
                pass

        print "TERMinating group..."
        killpg(0, SIGTERM) # kill the entire process group, we are ignoring the SIGTERM.
        sleep(2)
        print "Nuking the whole thing, have a nice day..."
        killpg(0, SIGKILL) # kill the entire process group

    def get_pid_list(self):
        return self.pid_list.keys()

class ProcessMonitor(object):
    def __init__(self, process_list_file, output_dir, time_limit, cadence):
        self.start_time = time()
        self.end_time = self.start_time + time_limit
        self._cadence = cadence
        self._pc = ProcessController(output_dir)
        self.command_count = 0
        for f in open(process_list_file).readlines():
            cmd = f.strip()
            if cmd == "": continue
            self._pc.run(cmd)
            self.command_count = self.command_count + 1

        self._rm = ResourceMonitor(self._pc.get_pid_list())
        self.monitor_file = open(output_dir+"/resource_usage.log","w", (1024**2)*10) #Set the file's buffering to 10MB

        #Capture SIGTERM to kill all the child processes before dying
        self.stopping = False
        signal(SIGTERM, self._termTrap)

    def stop(self):
        self.stopping = True
        self.monitor_file.close()
        self._pc.terminate()

    def _termTrap(self, *argv):
        print "Captured TERM signal"
        if not self.stopping:
            self.stop()

    def monitoring_loop(self):
        time_start = time()
        sleep_time = self._cadence
        last_subprocess_update = time_start
        while True:
            if self._rm.is_everyone_dead():
                print "All child processes have died, exiting"
                break
            next_wake = time() + self._cadence

            timestamp = time()
            for line in self._rm.get_raw_stats():
                self.monitor_file.write("%f %s\n" % (timestamp, line))
            #Look for new subprocesses only once in a second and during the first 10 seconds
            if (timestamp < time_start+10) and (timestamp - last_subprocess_update >= 1):
                self._rm.update_pid_tree()
                last_subprocess_update = timestamp

            if time() > self.end_time:
                print "End time reached, killing monitored processes."
                self.stop()
                break
            sleep_time = next_wake - time()
            if sleep_time < 0:
                print "Can't keep up with this cadence, try a higher value!", sleep_time
                self.stop()
                break
            sleep(sleep_time)

    def terminate(self):
        self._pc.terminate()

if __name__ == "__main__":
    process_list_file = argv[1]
    output_dir = argv[2]
    time_limit = int(argv[3])*60
    cadence = float(argv[4])

    pm = ProcessMonitor(process_list_file, output_dir, time_limit, cadence)
    try:
        pm.monitoring_loop()
    except KeyboardInterrupt:
        print "Killing monitored processes..."
        pm.terminate()
        print "Done."
