#!/usr/bin/env python
# Mircea Bardac
# TODO: needs documentation

import subprocess
from time import sleep, time
from sys import argv, exit
from os import setpgrp, getpgrp, killpg, getpid
from signal import SIGKILL, SIGTERM, signal

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

    def get_raw_stats(self):
        return self.usage_pids(self.pid_list)

    def get_pid_tree(self,parent_pids):
        """Build a list of all PIDs in the process tree starting from a given set of parent PIDs)"""
        if len(parent_pids) == 0: return []
        #print 'i',parent_pids
        return_pid_list = []
        return_pid_list.extend(parent_pids)
        current_parent_pids = []
        current_parent_pids.extend(parent_pids)
        while len(current_parent_pids) > 0:
            #pid_list = self.make_string_list(current_parent_pids)
            pid_list = current_parent_pids
            process = subprocess.Popen("ps h --ppid %s -o pid" %pid_list, shell = True, stdout = subprocess.PIPE)
            r = process.communicate()[0]
            if len(r) == 0:
                break
            pid_strings = r.strip().split('\n')
            current_parent_pids = [ int(p) for p in pid_strings ]
            return_pid_list.extend(current_parent_pids)
        #print 'r',return_pid_list
        return return_pid_list

    def usage_pids(self, pid_list):
        pid_stats = []
        for pid in pid_list:
            if pid == self.own_pid:
                continue
            try:
                status = open('/proc/%s/stat' % pid, 'r' ).read().strip()
                iostats = []
                for line in open('/proc/%s/io' % pid, 'r' ).readlines():
                    if line:
                        iostats.append(line.split(':')[1].strip())
                pid_stats.append("%s %s" % ( status, ' '.join(iostats)))
            except IOError:
                pass
            #self.monitor_file.flush()
        return pid_stats

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
        while True:
            sleep(sleep_time)
            next_wake = time() + self._cadence
            #resource_usage = self._rm.usage()
            """
            if resource_usage['memory'] == 0:
                print "All child processes have finished."
                self.stop()
                break
            """

            timestamp = time()
            for line in self._rm.get_raw_stats():
                self.monitor_file.write("%f %s\n" % (timestamp, line))

            if time() > self.end_time:
                print "End time reached, killing monitored processes."
                self.stop()
                break
            sleep_time = next_wake - time()
            if sleep_time < 0:
                print "Can't keep up with this cadence, try a higher value!", sleep_time
                self.stop()
                break


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
