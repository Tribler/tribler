#!/usr/bin/env python
# Mircea Bardac
# TODO: needs documentation 

import subprocess
from time import sleep, time
from sys import argv, exit
from os import setpgrp, getpgrp, killpg
from signal import SIGKILL

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

    def usage(self):
        return self.usage_pids(self.pid_list)

    def usage_by_process_group_not_working(self):
        # -g parameter for 'ps' does not work as expected (does not filter by process group)
        self.process = subprocess.Popen( \
            "ps h -g %d -o rss,pcpu | awk '{sum_mem+=$1; sum_cpu+=$2} END {print sum_mem, sum_cpu}'" %self.process_group_id,
            shell=True,
            stdout=subprocess.PIPE,
            )
        stdout_list = self.process.communicate()[0].strip().split()
        m = int(stdout_list[0])
        c = float(stdout_list[1])
        self.process = subprocess.Popen( \
            "ps h -p %d -o rss,pcpu'" %(getpid()),
            shell=True,
            stdout=subprocess.PIPE,
            )
        stdout_list = self.process.communicate()[0].strip().split()
        return {'memory': m - int(stdout_list[0]), 'cpu': c - float(stdout_list[0])}
    

    def get_pid_tree(self,parent_pids):
        """Build a list of all PIDs in the process tree starting from a given set of parent PIDs)"""
        if len(parent_pids) == 0: return []
        #print 'i',parent_pids
        return_pid_list = []
        return_pid_list.extend(parent_pids)
        current_parent_pids = []
        current_parent_pids.extend(parent_pids)
        while len(current_parent_pids) > 0:
            pid_list = self.make_string_list(current_parent_pids)
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
        pid_list = self.get_pid_tree(pid_list)
        pid_list = self.make_string_list(pid_list) # we need it as a string
        self.process = subprocess.Popen( \
            "ps h -p %s -o rss,pcpu | awk '{sum_mem+=$1; sum_cpu+=$2} END {print sum_mem, sum_cpu}'" %pid_list,
            shell=True,
            stdout=subprocess.PIPE,
            )
        self.stdout_list = self.process.communicate()[0].strip().split()
        return {'memory': int(self.stdout_list[0]), 'cpu': float(self.stdout_list[1])}

class ProcessController(object):
    def __init__(self, output_dir):
        self.cmd_id = 0
        self.pid_list = []
        self.processes = []
        self.output_dir = output_dir
        setpgrp() # creat new process group and become its leader

    def run(self, cmd):
        output_filename = output_dir + "/%05d.out" %self.cmd_id
        error_filename = output_dir + "/%05d.err" %self.cmd_id
        print "Starting #%05d: %s" %(self.cmd_id, cmd)
        p = subprocess.Popen(cmd, shell=True, \
            stdout = open(output_filename, "w"), \
            stderr = open(error_filename, "w"))
        self.processes.append(p)
        self.pid_list.append(p.pid)
        self.cmd_id = self.cmd_id + 1

    def terminate(self):
        killpg(0, SIGKILL) # kill the entire process group
        #for p in self.processes:
        #    p.kill()

    def get_pid_list(self):
        return self.pid_list


class ProcessMonitor(object):
    def __init__(self, process_list_file, output_dir, time_limit):
        self.time_limit = time_limit
        self._pc = pc = ProcessController(output_dir)
        self.command_count = 0
        for f in open(process_list_file).readlines():
            cmd = f.strip()
            if cmd == "": continue
            self._pc.run(cmd)
            self.command_count = self.command_count + 1
        self._rm = ResourceMonitor(self._pc.get_pid_list())
        #self.monitor_file = open(output_dir+"/resource_usage.log","w")

    def stop(self):
        #self.monitor_file.close()
        self._pc.terminate()

    def monitoring_loop(self):
        time_start = time()
        sleep_time = 1.0
        while True:
            sleep(sleep_time)
            resource_usage = self._rm.usage()
            if resource_usage['memory'] == 0:
                print "All child processes have finished."
                self.stop()
                break
            time_elapsed = (time() - time_start)
            #self.monitor_file.write("%d %d %3.2f %3.2f\n" %(int(time_elapsed), resource_usage['memory']/1024, resource_usage['cpu'], resource_usage['cpu'] / self.command_count))
            #self.monitor_file.flush()
            if time_elapsed > self.time_limit:
                print "Killing monitored processes (time elapsed: %d sec)" %(self.time_limit)
                self.stop()
                break
            sleep_time = 1.0 - time_elapsed + int(time_elapsed)

    def terminate(self):
        self._pc.terminate()


if __name__ == "__main__":
    process_list_file = argv[1]
    output_dir = argv[2]
    time_limit = int(argv[3])*60

    pm = ProcessMonitor(process_list_file, output_dir, time_limit)
    try:
        pm.monitoring_loop()
    except KeyboardInterrupt:
        print "Killing monitored processes..."
        pm.terminate()
        print "Done."

