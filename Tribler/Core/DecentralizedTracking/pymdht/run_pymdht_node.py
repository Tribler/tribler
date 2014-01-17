#! /usr/bin/env python

# Copyright (C) 2009-2011 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import core.ptime as time
import sys
import os
from optparse import OptionParser

import logging
import core.logging_conf as logging_conf

import core.identifier as identifier
import core.node as node
import core.pymdht as pymdht

logger = logging.getLogger(__name__)


def main(options, args):
    if not os.path.isdir(options.path):
        if os.path.exists(options.path):
            logger.critical('FATAL: %s must be a directory', options.path)
            return
        logger.info('%s does not exist. Creating directory...', options.path)
        os.mkdir(options.path)
    logs_path = options.path
    if options.lookup_delay and not options.daemon:
        logger.info('Switching to DAEMON mode (no user interface)')
    if options.lookup_delay or options.daemon:
        # redirect output
        stdout_file = os.path.join(options.path, 'pymdht.stdout')
        stderr_file = os.path.join(options.path, 'pymdht.stderr')
        logger.info('Redirecting output to %s and %s', stdout_file, stderr_file)
        sys.stdout = open(stdout_file, 'w')
        sys.stderr = open(stderr_file, 'w')

    my_addr = (options.ip, int(options.port))
    my_id = None
    if options.node_id:
        base_id = identifier.Id(options.node_id)
        my_id = base_id.generate_close_id(options.log_distance)
    my_node = node.Node(my_addr, my_id, version=pymdht.VERSION_LABEL)

    if options.debug:
        logs_level = logging.DEBUG  # This generates HUGE (and useful) logs
    else:
        # logs_level = logging.INFO # This generates some (useful) logs
        logs_level = logging.WARNING  # This generates warning and error logs

    logger.info('Using the following plug-ins:')
    logger.info('* %s', options.routing_m_file)
    logger.info('* %s', options.lookup_m_file)
    logger.info('* %s', options.experimental_m_file)
    logger.info('Path: %s', options.path)
    logger.info('Private DHT name: %s', options.private_dht_name)
    logger.info('debug mode: %s', options.debug)
    logger.info('bootstrap mode: %s', options.bootstrap_mode)
    logger.info('Swift tracker port: %s', options.swift_port)
    routing_m_name = '.'.join(os.path.split(options.routing_m_file))[:-3]
    routing_m_mod = __import__(routing_m_name, fromlist=[''])
    lookup_m_name = '.'.join(os.path.split(options.lookup_m_file))[:-3]
    lookup_m_mod = __import__(lookup_m_name, fromlist=[''])
    experimental_m_name = '.'.join(os.path.split(options.experimental_m_file))[:-3]
    experimental_m_mod = __import__(experimental_m_name, fromlist=[''])

    dht = pymdht.Pymdht(my_node, logs_path,
                        routing_m_mod,
                        lookup_m_mod,
                        experimental_m_mod,
                        options.private_dht_name,
                        logs_level,
                        options.bootstrap_mode,
                        options.swift_port)
    if options.lookup_delay:
        loop_forever = not options.num_lookups
        remaining_lookups = options.num_lookups
        while loop_forever or remaining_lookups:
            time.sleep(options.lookup_delay)
            if options.lookup_target:
                target = identifier.Id(options.lookup_target)
            else:
                target = identifier.RandomId()
            logger.info('lookup %s', target)
            dht.get_peers(None, target, None, options.announce_port)
            remaining_lookups = remaining_lookups - 1
        time.sleep(options.stop_delay)
        dht.stop()
    elif options.ttl:
        stop_timestamp = time.time() + int(options.ttl)
        while time.time() < stop_timestamp:
            time.sleep(1)
        dht.stop()
    elif options.daemon:
        # Just loop for ever
        while True:
            time.sleep(10)
    elif options.gui:
        import wx
        import ui.gui
        app = wx.PySimpleApp()
        frame = ui.gui.Interactive_GUI(
            None, "Interactive Look@MDHT", None, (1440, 900),
            dht, logs_path)
        frame.Show(True)
        app.MainLoop()
    elif options.telnet_port:
        import ui.telnet
        telnet_ui = ui.telnet.Telnet(dht, options.telnet_port)
        telnet_ui.start()
    elif options.cli:
        import ui.cli
        ui.cli.command_user_interface(dht)

if __name__ == '__main__':
    default_path = os.path.join(os.path.expanduser('~'), '.pymdht')
    parser = OptionParser()
    parser.add_option("-a", "--address", dest="ip",
                      metavar='IP', default='127.0.0.1',
                      help="IP address to be used")
    parser.add_option("-p", "--port", dest="port",
                      metavar='INT', default=7000,
                      help="port to be used")
    parser.add_option("--path", dest="path",
                      metavar='PATH', default=default_path,
                      help="pymdht.state and pymdht.log location")
    parser.add_option("-r", "--routing-plug-in", dest="routing_m_file",
                      metavar='FILE', default='plugins/routing_nice_rtt.py',
                      help="file containing the routing_manager code")
    parser.add_option("-l", "--lookup-plug-in", dest="lookup_m_file",
                      metavar='FILE', default='plugins/lookup_a4.py',
                      help="file containing the lookup_manager code")
#    parser.add_option("-z", "--logs-level", dest="logs_level",
#                      metavar='INT', default=0
#                      help="logging level")
    parser.add_option("-e", "--experimental-plug-in", dest="experimental_m_file",
                      metavar='FILE', default='core/exp_plugin_template.py',
                      help="file containing ping-manager code")
    parser.add_option("-d", "--private-dht", dest="private_dht_name",
                      metavar='STRING', default=None,
                      help="private DHT name")
    parser.add_option("--debug", dest="debug",
                      action='store_true', default=False,
                      help="DEBUG mode")
    parser.add_option("--gui", dest="gui",
                      action='store_true', default=False,
                      help="Graphical user interface")
    parser.add_option("--cli", dest="cli",
                      action='store_true', default=True,
                      help="Command line interface (no GUI) <- default")
    parser.add_option("--telnet-port", dest="telnet_port",
                      metavar='INT', default=0,
                      help="Telnet interface on given TCP port (see ui/telnet_api.txt).")
    parser.add_option("--daemon", dest="daemon",
                      action='store_true', default=False,
                      help="DAEMON mode (no user interface)")
    parser.add_option("--ttl", dest="ttl",
                      default=0,
                      help="Interactive DHT will run for the specified time\
    (in seconds). This option is ignored if lookup-delay is not 0")
#    parser.add_option("--telnet",dest="telnet",
#                      action='store_true', default=False,
#                      help="Telnet interface (only on DAEMON mode)")
    parser.add_option("--lookup-delay", dest="lookup_delay",
                      metavar='INT', default=0,
                      help="Perform a lookup every x seconds (it will switch\
    to DAEMON mode). The lookup-target option determines the lookup target")
    parser.add_option("--lookup-target", dest="lookup_target",
                      metavar='STRING', default='',
                      help="Hexadecimal (40 characters) representation of the\
    identifier (info_hash) to be looked up. Default is different random\
    targets each lookup (use in combination with lookup-delay")
    parser.add_option("--number-lookups", dest="num_lookups",
                      metavar='INT', default=0,
                      help="Exit after x lookups + stop_delay. Default\
    infinite (run forever) (use in combination with lookup-delay)")
    parser.add_option("--stop-delay", dest="stop_delay",
                      metavar='INT', default=60,
                      help="Sleep for x seconds before exiting (use in\
    combination with number-lookups). Default 60 seconds.")
    parser.add_option("--announce-port", dest="announce_port",
                      metavar='INT', default=0,
                      help="(only with lookup-delay) Announce after each\
    lookup. No announcement by default")
    parser.add_option("--node-id", dest="node_id",
                      metavar='STRING', default=None,
                      help="Hexadecimal (40 characters) representation of the\
    identifier (node id) to be used. This option overrides the node id saved\
    into pymdht.state. (option log-distance can modify the final node id)")
    parser.add_option("--log-distance", dest="log_distance",
                      metavar='INT', default=-1,
                      help="(only when option node-id is used) Modifies the\
    node id to be close to the node-id specified. This is useful to place\
    nodes close to a particular identifier. For instance, to collect get_peers\
    messages for a given info_hash")
    parser.add_option("--bootstrap-mode", dest="bootstrap_mode",
                      action='store_true', default=False,
                      help="Only for well-known bootsrap nodes. It will ignore\
    some incoming queries to avoid being added to too many routing tables.")
    parser.add_option("--swift-port", dest="swift_port",
                      metavar='INT', default=0,
                      help="Open a Swift tracker interface on the indicated\
    UDP port. Default 0, means do not run a swift tracker.")
    parser.add_option("--version", dest="version",
                      action='store_true', default=False,
                      help="Print Pymdhtversion and exit.")

    (options, args) = parser.parse_args()

    if options.version:
        logger.info('Pymdht %d.%d.%d' % pymdht.PYMDHT_VERSION)
        sys.exit()

    options.port = int(options.port)
#    options.logs_level = int(options.logs_level)
    options.telnet_port = int(options.telnet_port)
    options.lookup_delay = int(options.lookup_delay)
    options.num_lookups = int(options.num_lookups)
    options.stop_delay = int(options.stop_delay)
    options.announce_port = int(options.announce_port)
    options.log_distance = int(options.log_distance)
    options.swift_port = int(options.swift_port)
    main(options, args)
