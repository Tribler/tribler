#! /usr/bin/env python

'''
usage: %(progname)s [args]

   --help -- display this info

   --verbose -- display verbose info

   --type -- type of the simulation; possible values are: simple
 
   --file siminfile -- the file with simulation parameters

'''

__author__ = 'Pawel Garbacki';
__email__ = 'p.garbacki at ewi.tudelft.nl';
__file__ = 'simulation.py';
__version__ = '$Revision: 0.1$';
__date__ = "$Date: 2005/11/17 21:48:25 $"
__copyright__ = "Copyright (c) 2005 Pawel Garbacki"
__license__ = "Python" 
 
# input file: .simin file
# output file: .simout file

from sys import exit, argv
from glob import glob
from getopt import getopt, GetoptError
from os import system, path, mkdir, makedirs, chdir
from shutil import copyfile, rmtree
from time import sleep
from random import random
from math import log
from time import time

# Ensure booleans exist (not needed for Python 2.2.1 or higher)
try:
    True
except NameError:
    False = 0
    True = not False

verbose = False
parameters = {}

SLEEPING_TIME = 10
SHORT_SLEEPING_TIME = 2

MAX_ITERATIONS = 5

def print_v(str):
    if verbose:
        print str

def read_properties_file(properties_file_name):
    print_v("read_simin_file")
    properties = {}
    properties_file = open(properties_file_name, 'r')
    while 1:
        lines = properties_file.readlines(100000)
        if not lines:
            break

        #-- process lines
        for line in lines:
            line = line.strip()
            #-- exclude comment and empty lines
            if (len(line) > 0) and (line[0] != '#'): 
                #-- line contents:
                #   <param_name> = <param_value>
                print_v("reading line: " + line + " len: " + str(len(line)))
                try:
                    property_name, property_value = line.split('=')
                    properties[property_name.strip()] = property_value.strip()
                except:
                    pass
    return properties

def prepare_execution_dir(execution_dir):
    global parameters

    rmtree(execution_dir, True)
    torrents_dir = path.join(execution_dir, 'torrents')
    makedirs(torrents_dir) # execution_dir will be created implicitely
    superpeer_file = parameters['superpeer_file']
    print_v(superpeer_file)
    print_v(path.join(execution_dir, path.basename(superpeer_file)))
    copyfile(superpeer_file, path.join(execution_dir, path.basename(superpeer_file)))
    torrent_file = parameters['torrent_file']
    copyfile(torrent_file, path.join(torrents_dir, path.basename(torrent_file)))
    

# Warning: all data stored currently in the simulation directory will be lost!
def prepare_simulation_dir():
    global parameters

    simulation_dir = parameters['simulation_dir']
    rmtree(simulation_dir, True)

    makedirs(path.join(simulation_dir, 'results'))

    prepare_execution_dir(path.join(simulation_dir, 'coordinator'))

    n_helpers = int(parameters['n_helpers'])
    for i in range(1, n_helpers + 1):
        prepare_execution_dir(path.join(simulation_dir, 'helper' + str(i)))

    n_originals = int(parameters['n_originals'])
    for i in range(1, n_originals + 1):
        prepare_execution_dir(path.join(simulation_dir, 'original' + str(i)))

def gather_logs(execution_dir):
    global parameters

    simulation_dir = parameters['simulation_dir']
    results_dir = path.join(simulation_dir, 'results')
    log_files_pattern = path.join(execution_dir, '*.log')
    result_files_pattern = path.join(results_dir, '*.log.*')
    n_files = len(glob(result_files_pattern))
    for log_file in glob(log_files_pattern):
        copyfile(log_file, path.join(results_dir, path.basename(log_file) + '.' + str(n_files)))
        n_files += 1

def gather_simulation_logs():
    global parameters

    simulation_dir = parameters['simulation_dir']
    coordinator_dir = path.join(simulation_dir, 'coordinator')
    gather_logs(coordinator_dir)
    n_helpers = int(parameters['n_helpers'])
    for i in range(1, n_helpers + 1):
        helper_dir = path.join(simulation_dir, 'helper' + str(i))
        gather_logs(helper_dir)
    n_originals = int(parameters['n_originals'])
    for i in range(1, n_originals + 1):
        original_dir = path.join(simulation_dir, 'original' + str(i))
        gather_logs(original_dir)

def process_results():
    global parameters

    pass

def execute_command(command, working_dir):
    global parameters

    chdir(working_dir)
    system(command)
    chdir(parameters['initial_dir'])

def create_helpers_file():
    global parameters

    helpers_file_name = path.join(parameters['simulation_dir'], 'coordinator', 'helpers.txt')
    helpers_file = open(helpers_file_name, "w")

    for port in parameters['helpers_ports']:
        helpers_file.write("127.0.0.1 " + str(port) + "\n")
    helpers_file.close()

def start_coordinator():
    global parameters

    print_v("start_coordinator")
    command = parameters['screen_executable'] + ' ' + parameters['screen_command_wrapper']
    command += ' ' + parameters['python']
    command += ' ' + path.join(parameters['software_dir'], parameters['coordinator_executable'])
    command += ' ' + parameters['coordinator_fixed_params']
    command += ' --max_upload_rate ' + parameters['coordinator_max_upload_rate']
    command += ' --max_download_rate ' + parameters['coordinator_max_download_rate']
    coordinator_dir = path.join(parameters['simulation_dir'], 'coordinator')
    log_file = path.join(coordinator_dir, 'coordinator.log')
    command += ' --2fastbtlog ' + log_file
    if parameters['mode'] == 'passive':
        helpers_file = path.join(coordinator_dir, 'helpers.txt')
        command += ' --helpers_file ' + helpers_file
#    n_helpers = int(parameters['n_helpers'])
#    min_uploads = 4 + n_helpers
#    max_uploads = 7 + n_helpers
#    command += ' --min_uploads ' +  str(min_uploads) + ' --max_uploads ' + str(max_uploads)
    if parameters.has_key('coordinator_exclude_ips'):
        command += ' --exclude_ips ' + parameters['coordinator_exclude_ips']
    command += ' ' + path.join(coordinator_dir, 'torrents')
    execute_command(command, coordinator_dir)
    print_v(command)
#    print_v(coordinator_dir)
    print_v("before sleep")
    sleep(10)
    print_v("after sleep")

    if parameters['mode'] == 'active':
        for i in range(0, MAX_ITERATIONS):
            sleep(SHORT_SLEEPING_TIME)
            coordinator_properties = read_properties_file(log_file)
            if coordinator_properties.has_key('port'):
                parameters['coordinator_port'] = coordinator_properties['port']
                print_v("got coordinator port: " + str(parameters['coordinator_port']))
                break

def start_helper(helper_id):
    global parameters

    print_v("start_helper")
    command = parameters['screen_executable'] + ' ' + parameters['screen_command_wrapper']
    command += ' ' + parameters['python']
    command += ' ' + path.join(parameters['software_dir'], parameters['helper_executable'])
    command += ' ' + parameters['helper_fixed_params']
    command += ' --max_upload_rate ' + parameters['helper_max_upload_rate']
    command += ' --max_download_rate ' + parameters['helper_max_download_rate']
    helper_dir = path.join(parameters['simulation_dir'], 'helper' + str(helper_id))
    command += ' --2fastbtlog ' + path.join(helper_dir, 'helper.log')
#    min_uploads = 4 + 1
#    max_uploads = 7 + 1
#    command += ' --min_uploads ' +  str(min_uploads) + ' --max_uploads ' + str(max_uploads)
    if parameters['mode'] == 'active':
        command += ' --role helper'
        command += ' --coordinator_port ' + parameters['coordinator_port']
    if parameters.has_key('helper_exclude_ips'):
        command += ' --exclude_ips ' + parameters['helper_exclude_ips']
    command += ' ' + path.join(helper_dir, 'torrents')
    print_v(command)
    execute_command(command, helper_dir)

    if parameters['mode'] == 'passive':
        if not parameters.has_key('helpers_ports'):
            parameters['helpers_ports'] = []
        for i in range(0, MAX_ITERATIONS):
            sleep(SHORT_SLEEPING_TIME)
            helper_properties = read_properties_file(log_file)
            if helper_properties.has_key('port'):
                parameters['helpers_ports'].append(helper_properties['port'])
                print_v("got helper port: " + str(helper_properties['port']))
                break

def start_original(original_id):
    global parameters

    print_v("start_original")
    command = parameters['screen_executable'] + ' ' + parameters['screen_command_wrapper']
    command += ' ' + parameters['python']
    command += ' ' + path.join(parameters['software_dir'], parameters['original_executable'])
    command += ' ' + parameters['original_fixed_params']
    command += ' --max_upload_rate ' + parameters['original_max_upload_rate']
    command += ' --max_download_rate ' + parameters['original_max_download_rate']
    original_dir = path.join(parameters['simulation_dir'], 'original' + str(original_id))
    command += ' --2fastbtlog ' + path.join(original_dir, 'original.log')
    if parameters.has_key('original_exclude_ips'):
        command += ' --exclude_ips ' + parameters['original_exclude_ips']
    command += ' ' + path.join(original_dir, 'torrents')
    execute_command(command, original_dir)

def try_start_originals(n_waiting_originals):
    global parameters

    simulation_dir = parameters['simulation_dir']
    finished = get_finished_originals()
    while finished != [] and n_waiting_originals > 0:
        original_id = finished.pop()
        original_dir = path.join(simulation_dir, 'original' + str(original_id))
        gather_logs(original_dir)
        prepare_execution_dir(original_dir)
        start_original(original_id)
        n_waiting_originals -= 1
    return n_waiting_originals

def coordinator_finished():
    global parameters

    lock_file = path.join(parameters['simulation_dir'], 'coordinator', '.lock')
    if path.isfile(lock_file):
        return False
    return True

def helper_finished(helper_id):
    global parameters

    lock_file = path.join(parameters['simulation_dir'], 'helper' + str(helper_id), '.lock')
    if path.isfile(lock_file):
        return False
    return True

def original_finished(original_id):
    global parameters

    lock_file = path.join(parameters['simulation_dir'], 'original' + str(original_id), '.lock')
    if path.isfile(lock_file):
        return False
    return True

def get_finished_helpers():
    global parameters

    finished = []
    n_helpers = int(parameters['n_helpers'])
    for i in range(1, n_helpers + 1):
        if helper_finished(i):
            finished.append(i)
    return finished

def get_finished_originals():
    global parameters

    finished = []
    n_originals = int(parameters['n_originals'])
    for i in range(1, n_originals + 1):
        if original_finished(i):
            finished.append(i)
    return finished

def wait_for_coordinator():
    global parameters

    while True:
        if coordinator_finished():
            return
        print_v("sleeping...")
        sleep(SLEEPING_TIME)

def kill_simulation():
    global parameters

    execute_command(parameters['killall_executable'], '.')

def simple_simulation():
    global parameters

    prepare_simulation_dir()

    if parameters['mode'] == 'active':
        start_coordinator()
        n_helpers = int(parameters['n_helpers'])
        for i in range(1, n_helpers + 1):
            start_helper(i)
    else: # parameters['mode'] == 'passive'
        n_helpers = int(parameters['n_helpers'])
        for i in range(1, n_helpers + 1):
            start_helper(i)
        create_helpers_file()
        start_coordinator()

    n_originals = int(parameters['n_originals'])
    for i in range(1, n_originals + 1):
        start_original(i)

    sleep(10)
    wait_for_coordinator()

    kill_simulation()

    gather_simulation_logs()

def compute_poisson_interarrival_time():
    global parameters

    l = float(parameters['lambda'])
    r = random()
    t = -1. * log(r) / l
    return t

def wait(n_waiting_originals, waiting_time):
    start_time = time()
    delta = 0
    while n_waiting_originals > 0 and delta < waiting_time:
        sleeping_time = min(waiting_time - delta, SHORT_SLEEPING_TIME)
        print_v("sleeping... " + str(sleeping_time))
        sleep(sleeping_time)
        n_waiting_originals = try_start_originals(n_waiting_originals)
        delta = time() - start_time
    if delta < waiting_time:
        print_v("sleeping... " + str(waiting_time - delta))
        sleep(waiting_time - delta)
    return n_waiting_originals

def poisson_simulation():
    global parameters

#    for i in range(0, 100):
#        print_v("interarrival_time = " + str(compute_poisson_interarrival_time()))

    prepare_simulation_dir()

    n_waiting_originals = 0
    n_bootstrapping_phases = int(parameters['n_bootstrapping_phases'])
    for i in range(0, n_bootstrapping_phases):
#        finished = wait_for_original_slot(compute_poisson_interarrival_time())
        waiting_time = compute_poisson_interarrival_time()
        n_waiting_originals = wait(n_waiting_originals, waiting_time) + 1

    if parameters['mode'] == 'active':
        start_coordinator()
        n_helpers = int(parameters['n_helpers'])
        for i in range(1, n_helpers + 1):
            start_helper(i)
    else: # parameters['mode'] == 'passive'
        n_helpers = int(parameters['n_helpers'])
        for i in range(1, n_helpers + 1):
            start_helper(i)
        create_helpers_file()
        start_coordinator()

    while True:
        if coordinator_finished():
            break
        waiting_time = compute_poisson_interarrival_time()
        n_waiting_originals = wait(n_waiting_originals, waiting_time) + 1

    kill_simulation()

    gather_simulation_logs()

'''
def save_results_to_file(output_file_name, list, format, desc = '', create_new = True):
    if create_new:
        output_file = open(output_file_name, "w")
    else:
        output_file = open(output_file_name, "a")
    if desc != '':
        output_file.write('# ' + desc + '\n')
    for item in list:
        output_file.write(format %item)
    output_file.close()
'''

def usage(progname):
    print __doc__ % vars()

def main(argv):
    global parameters
    global verbose

#    execute_command("/usr/bin/screen -m -d /home/pawel/2fast_simulation/control/screen_cmd.sh /home/pawel/phd/soft/install_abc/usr/local/bin/python /home/pawel/phd/soft/abc310/btlaunchmany.py --role coordinator --rerequest_interval 120 --min_peers 200 --security 0 --max_upload_rate 512 --max_download_rate 2048 --2fastbtlog /home/pawel/2fast_simulation/work/coordinator/coordinator.log --min_uploads 4 --max_uploads 7 /home/pawel/2fast_simulation/work/coordinator/torrents", ".")
#    sleep(10)
    try:                                
        opts, args = getopt(argv, "hvt:f:", ["help", "verbose", "type=", "file="])
    except GetoptError:
        usage(path.basename(argv[0]))
        exit(2)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage(path.basename(argv[0]))
            exit()
        elif opt in ('-v', "--verbose"):
            verbose = True
            print "***VERBOSE***"
        elif opt in ("-t", "--type"):
            simulation_type = arg.strip()
            if not simulation_type == 'simple' and not simulation_type == 'poisson':
                usage(path.basename(argv[0]))
                exit(2)
        elif opt in ("-f", "--file"):
            simin_file_name = arg.strip()
    parameters = read_properties_file(simin_file_name)
    parameters['initial_dir'] = path.abspath(".")
    if simulation_type == 'simple':
        simple_simulation()
    elif simulation_type == 'poisson':
        poisson_simulation()

if __name__ == "__main__":
    if len(argv) == 1:
        usage(path.basename(argv[0]))
        exit(3)

    main(argv[1:])
