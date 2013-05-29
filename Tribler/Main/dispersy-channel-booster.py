#!/usr/bin/python

"""
Logger format:
- Timestamp
- DISP_SYNC_IN
- Community ID
- Member ID
- LAN host
- LAN port
- WAN host
- WAN port
- Connection type
- Advice
- Sync time low (0 when sync disabled)
- Sync time high (0 when sync disabled)
- Sync modulo (1 when sync disabled)
- Sync offset (0 when sync disabled)
- Bytes transferred in response
"""

from traceback import print_exc
import optparse
import os
import sys
import time

from Tribler.Core.API import SessionStartupConfig, Session
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.message import Message


class BoosterDispersy(Dispersy):

    def __init__(self, callback, statedir):
        super(BoosterDispersy, self).__init__(callback, statedir)

        # logger
        session = Session.get_instance()
        port = session.get_listen_port()
        overlaylogpostfix = "bp" + str(port) + ".log"
        self._logger = OverlayLogger.getInstance(overlaylogpostfix, statedir)

    def check_sync(self, messages):
        for message in messages:
            _, before = self._statistics.total_up
            result = super(BoosterDispersy, self).check_sync([message]).next()
            _, after = self._statistics.total_up

            if isinstance(result, Message.Implementation) and message.payload.sync:
                payload = message.payload
                self._logger("DISP_SYNC_IN", message.community.cid.encode("HEX"), message.authentication.member.mid.encode("HEX"), message.candidate.lan_address[0], message.candidate.lan_address[1], message.candidate.wan_address[0], message.candidate.wan_address[1], payload.connection_type, payload.advice, payload.time_low, payload.time_high, payload.modulo, payload.offset, after - before)

            yield result


def main():
    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir")
    command_line_parser.add_option("--port", action="store", type="int", help="Listen at this port")
    command_line_parser.add_option("--dispersy-port", action="store", type="int", help="Dispersy uses this UDL port", default=6421)
    command_line_parser.add_option("--nickname", action="store", type="string", help="The moderator name", default="Booster")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()

    if not opt.statedir:
        command_line_parser.print_help()
        print "\nExample: python", sys.argv[0], "--statedir /home/tribler/booster --nickname Booster"
        sys.exit()

    print "Press Ctrl-C to stop the booster"

    sscfg = SessionStartupConfig()
    if opt.statedir:
        sscfg.set_state_dir(os.path.realpath(opt.statedir))
    if opt.port:
        sscfg.set_listen_port(opt.port)
    if opt.dispersy_port:
        sscfg.set_dispersy_port(opt.dispersy_port)
    if opt.nickname:
        sscfg.set_nickname(opt.nickname)

    sscfg.set_megacache(True)
    sscfg.set_overlay(True)
    # turn torrent collecting on. this will cause torrents to be distributed
    sscfg.set_torrent_collecting(True)
    sscfg.set_dialback(False)
    sscfg.set_internal_tracker(False)

    session = Session(sscfg)

    # KeyboardInterrupt
    try:
        while True:
            sys.stdin.read()
    except:
        print_exc()

    session.shutdown()
    print "Shutting down..."
    time.sleep(5)

if __name__ == "__main__":
    main()
