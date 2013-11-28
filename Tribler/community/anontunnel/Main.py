import logging.config
import os
import re

logging.config.fileConfig(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import threading

try:
    import yappi
except:
    pass

from Tribler.community.anontunnel import DispersyTunnelProxy
from Tribler.community.anontunnel.CircuitLengthStrategies import RandomCircuitLengthStrategy, ConstantCircuitLengthStrategy
from Tribler.community.anontunnel.SelectionStrategies import RandomSelectionStrategy, LengthSelectionStrategy
from Tribler.community.anontunnel.AnonTunnel import AnonTunnel

import sys, argparse


def main(argv):
    try:
        parser = argparse.ArgumentParser(description = 'Anonymous Tunnel CLI interface')
        parser.add_argument('-p', '--socks5', help='Socks5 port')
        parser.add_argument('-y', '--yappi', help="Yappi profiling mode, 'wall' and 'cpu' are valid values")
        parser.add_argument('-c', '--cmd', help='The command UDP port to listen on')
        parser.add_argument('-l', '--length-strategy', default=[], nargs='*', help='Circuit length strategy')
        parser.add_argument('-s', '--select-strategy', default=[], nargs='*', help='Circuit selection strategy')
        parser.add_argument('--max-circuits', nargs=1, default=10, help='Maximum number of circuits to create')
        parser.add_argument('--record-on-incoming', help='Record stats from the moment the first data enters the tunnel')

        parser.add_help = True
        args = parser.parse_args(sys.argv[1:])

    except argparse.ArgumentError:
        parser.print_help()
        sys.exit(2)

    cmd_port = None
    socks5_port = None

    if args.yappi == 'wall':
        profile = "wall"
    elif args.yappi == 'cpu':
        profile = "cpu"
    else:
        profile = None

    if args.cmd:
        cmd_port = int(args.cmd)

    if args.socks5:
        socks5_port = int(args.socks5)

    if args.max_circuits:
        DispersyTunnelProxy.MAX_CIRCUITS_TO_CREATE = args.max_circuits

    if profile:
        yappi.set_clock_type(profile)
        yappi.start(builtins=True)
        print "Profiling using %s time" % yappi.get_clock_type()['type']

    anon_tunnel = AnonTunnel(socks5_port, cmd_port)

    if args.record_on_incoming:
        def on_enter_tunnel_data_head(ultimate_destination, payload):
            anon_tunnel.tunnel.record_stats = True
        anon_tunnel.socks5_server.once("enter_tunnel_data", on_enter_tunnel_data_head)

    # Circuit length strategy
    if args.length_strategy[:1] == ['random']:
        strategy = RandomCircuitLengthStrategy(*args.length_strategy[1:])
        anon_tunnel.tunnel.circuit_length_strategy = strategy
        logger.error("Using RandomCircuitLengthStrategy with arguments %s" % (', '.join(args.length_strategy[1:])))
    elif args.length_strategy[:1] == ['constant']:
        strategy = ConstantCircuitLengthStrategy(*args.length_strategy[1:])
        anon_tunnel.tunnel.circuit_length_strategy = strategy
        logger.error("Using ConstantCircuitLengthStrategy with arguments %s" % (', '.join(args.length_strategy[1:])))


    # Circuit selection strategies
    if args.select_strategy[:1] == ['random']:
        strategy = RandomSelectionStrategy(*args.select_strategy[1:])
        anon_tunnel.tunnel.circuit_selection_strategy = strategy
        logger.error("Using RandomCircuitLengthStrategy with arguments %s" % (', '.join(args.select_strategy[1:])))
    elif args.select_strategy[:1] == ['length']:
        strategy = LengthSelectionStrategy(*args.select_strategy[1:])
        anon_tunnel.tunnel.circuit_selection_strategy = strategy
        logger.error("Using LengthSelectionStrategy with arguments %s" % (', '.join(args.select_strategy[1:])))

    anon_tunnel.start()

    regex_cmd_extend_circuit = re.compile("e ?([0-9]+)\n")

    while 1:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            anon_tunnel.stop()
            os._exit(0)
            break

        if not line:
            break

        cmd_extend_match = regex_cmd_extend_circuit.match(line)

        if line == 'threads\n':
            for thread in threading.enumerate():
                print "%s \t %d" % (thread.name, thread.ident)
        elif line == 'p\n':
            if profile:

                for func_stats in yappi.get_func_stats().sort("subtime")[:50]:
                    print "YAPPI: %10dx  %10.3fs" % (func_stats.ncall, func_stats.tsub), func_stats.name
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'P\n':
            if profile:
                filename = 'callgrindc_%d.yappi' % anon_tunnel.dispersy.lan_address[1]
                yappi.get_func_stats().save(filename, type='callgrind')
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 't\n':
            if profile:
                yappi.get_thread_stats().sort("totaltime").print_all()

            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'c\n':
            print "========\nCircuits\n========\nid\taddress\t\t\t\t\tgoal\thops\tIN (MB)\tOUT (MB)\tIN (kBps)\tOUT (kBps)"
            for circuit in anon_tunnel.tunnel.circuits.values():
                if circuit.created:
                    print "%d\t%s\t%d\t%d\t\t%.2f\t\t%.2f\t\t%.2f\t\t%.2f" % (
                        circuit.id, circuit.candidate, circuit.goal_hops, len(circuit.hops),
                        circuit.bytes_downloaded / 1024.0 / 1024.0,
                        circuit.bytes_uploaded / 1024.0 / 1024.0,
                        circuit.speed_down / 1024.0,
                        circuit.speed_up / 1024.0
                    )

                    for hop in circuit.hops[1:]:
                        print "\t%s" % (hop,)

        elif cmd_extend_match:
            circuit_id = int(cmd_extend_match.group(1))

            if circuit_id in anon_tunnel.tunnel.circuits:
                circuit = anon_tunnel.tunnel.circuits[circuit_id]
                anon_tunnel.tunnel.extend_circuit(circuit)

        elif line == 'q\n':
            anon_tunnel.stop()
            os._exit(0)
            break

        elif line == 'r\n':
            print "circuit\t\t\tdirection\tcircuit\t\t\tTraffic (MB)\tSpeed (kBps)"

            from_to = anon_tunnel.tunnel.relay_from_to

            for key in from_to.keys():
                relay = from_to[key]

                print "%s-->\t%s\t\t%.2f\t\t%.2f" % (
                    (key[0].sock_addr, key[1]), (relay.candidate.sock_addr, relay.circuit_id), relay.bytes[1] / 1024.0 / 1024.0,
                    relay.speed / 1024.0
                )


if __name__ == "__main__":
    main(sys.argv[1:])

