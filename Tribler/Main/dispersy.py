#!/usr/bin/python

"""
Run Dispersy in standalone mode.  Tribler will not be started.
"""

import optparse
import sys
import threading

from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.Swift.SwiftProcessMgr import SwiftProcessMgr
from Tribler.Core.dispersy.callback import Callback
from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.endpoint import TunnelEndpoint, RawserverEndpoint

def main():
    def on_fatal_error(error):
        print >> sys.stderr, "Rawserver fatal error:", error
        global exit_exception
        exit_exception = error
        session_done_flag.set()

    def on_non_fatal_error(error):
        print >> sys.stderr, "Rawserver non fatal error:", error

    def start():
        # start Dispersy
        dispersy = Dispersy.get_instance(callback, unicode(opt.statedir))

        if opt.swiftproc:
            # start swift
            sesslock = threading.Lock()
            spm = SwiftProcessMgr(opt.swiftpath, opt.swiftcmdlistenport, opt.swiftdlsperproc, sesslock)
            swift_process = spm.get_or_create_sp(opt.statedir)
            dispersy.endpoint = TunnelEndpoint(swift_process, dispersy)
            swift_process.add_download(dispersy.endpoint)

        else:
            dispersy.endpoint = RawserverEndpoint(rawserver, dispersy, opt.port, opt.ip)

        # load the script parser
        if opt.script:
            from Tribler.Core.dispersy.script import Script
            script = Script.get_instance(callback)

            script_kargs = {}
            if opt.script_args:
                for arg in opt.script_args.split(','):
                    key, value = arg.split('=')
                    script_kargs[key] = value

            if opt.enable_dispersy_script:
                from Tribler.Core.dispersy.script import DispersyClassificationScript, DispersyTimelineScript, DispersyDestroyCommunityScript, DispersyBatchScript, DispersySyncScript, DispersyIdenticalPayloadScript, DispersySubjectiveSetScript, DispersySignatureScript, DispersyMemberTagScript, DispersyMissingMessageScript, DispersyUndoScript, DispersyCryptoScript, DispersyDynamicSettings, DispersyBootstrapServers
                script.add("dispersy-batch", DispersyBatchScript)
                script.add("dispersy-classification", DispersyClassificationScript)
                script.add("dispersy-crypto", DispersyCryptoScript)
                script.add("dispersy-destroy-community", DispersyDestroyCommunityScript)
                script.add("dispersy-dynamic-settings", DispersyDynamicSettings)
                script.add("dispersy-identical-payload", DispersyIdenticalPayloadScript)
                script.add("dispersy-member-tag", DispersyMemberTagScript)
                script.add("dispersy-missing-message", DispersyMissingMessageScript)
                script.add("dispersy-signature", DispersySignatureScript)
                script.add("dispersy-subjective-set", DispersySubjectiveSetScript)
                script.add("dispersy-sync", DispersySyncScript)
                script.add("dispersy-timeline", DispersyTimelineScript)
                script.add("dispersy-undo", DispersyUndoScript)
                script.add("dispersy-bootstrap-servers", DispersyBootstrapServers)

                from Tribler.Core.dispersy.tool.callbackscript import DispersyCallbackScript
                script.add("dispersy-callback", DispersyCallbackScript)

            if opt.enable_allchannel_script:
                # from Tribler.Community.allchannel.script import AllChannelScript
                # script.add("allchannel", AllChannelScript, include_with_all=False)

                from Tribler.community.allchannel.script import AllChannelScenarioScript
                script.add("allchannel-scenario", AllChannelScenarioScript, script_kargs, include_with_all=False)

            if opt.enable_walktest_script:
                from Tribler.community.walktest.script import ScenarioScript
                script.add("walktest-scenario", ScenarioScript, script_kargs, include_with_all=False)

            if opt.enable_ycsb_script:
                from Tribler.community.ycsb.script import YCSBScript
                script.add("ycsb-scenario", YCSBScript, script_kargs, include_with_all=False)

            if opt.enable_demers_script:
                from Tribler.community.demerstest.script import DemersScript
                script.add("demers-scenario", DemersScript, script_kargs, include_with_all=False)

            if opt.enable_udp_script:
                from Tribler.Core.dispersy.script import DispersyUDPScript
                script.add("udp-scenario", DispersyUDPScript, script_kargs, include_with_all=False)

            if opt.enable_effort_script:
                from Tribler.community.effort.script import ScenarioScript
                script.add("effort-scenario", ScenarioScript, script_kargs, include_with_all=False)

            # if opt.enable_barter_script:
            #     from Tribler.Community.barter.script import BarterScript, BarterScenarioScript
            #     script.add("barter", BarterScript)
            #     script.add("barter-scenario", BarterScenarioScript, script_kargs, include_with_all=False)

            # # bump the rawserver, or it will delay everything... since it sucks.
            # def bump():
            #     pass
            # rawserver.add_task(bump)

            script.load(opt.script)

    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir", default=u".")
    command_line_parser.add_option("--ip", action="store", type="string", default="0.0.0.0", help="Dispersy uses this ip")
    command_line_parser.add_option("--port", action="store", type="int", help="Dispersy uses this UDL port", default=12345)
    command_line_parser.add_option("--timeout-check-interval", action="store", type="float", default=1.0)
    command_line_parser.add_option("--timeout", action="store", type="float", default=300.0)
    command_line_parser.add_option("--enable-allchannel-script", action="store_true", help="Include allchannel scripts", default=False)
    command_line_parser.add_option("--enable-barter-script", action="store_true", help="Include barter scripts", default=False)
    command_line_parser.add_option("--enable-dispersy-script", action="store_true", help="Include dispersy scripts", default=False)
    command_line_parser.add_option("--enable-walktest-script", action="store_true", help="Include walktest scripts", default=False)
    command_line_parser.add_option("--enable-ycsb-script", action="store_true", help="Include ycsb scripts", default=False)
    command_line_parser.add_option("--enable-demers-script", action="store_true", help="Include demers scripts", default=False)
    command_line_parser.add_option("--enable-udp-script", action="store_true", help="Include udp-testing scripts", default=False)
    command_line_parser.add_option("--enable-effort-script", action="store_true", help="Include effort scripts", default=False)
    command_line_parser.add_option("--script", action="store", type="string", help="Runs the Script python file with <SCRIPT> as an argument")
    command_line_parser.add_option("--script-args", action="store", type="string", help="Executes --script with these arguments.  Example 'startingtimestamp=1292333014,endingtimestamp=12923340000'")
    command_line_parser.add_option("--yappi", action="store_true", help="Use Yappi to produce a performance profile")
    # swift
    command_line_parser.add_option("--swiftproc", action="store_true", help="Use swift to tunnel all traffic", default=False)
    command_line_parser.add_option("--swiftpath", action="store", type="string", default="./swift")
    command_line_parser.add_option("--swiftcmdlistenport", action="store", type="int", default=7760+481)
    command_line_parser.add_option("--swiftdlsperproc", action="store", type="int", default=1000)

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()
    print "Press Ctrl-C to stop Dispersy"

    if opt.yappi:
        import yappi
        yappi.start()

    # start threads
    session_done_flag = threading.Event()
    rawserver = RawServer(session_done_flag, opt.timeout_check_interval, opt.timeout, False, failfunc=on_fatal_error, errorfunc=on_non_fatal_error)
    callback = Callback()
    callback.start(name="Dispersy")

    # def rawserver_adrenaline():
    #     """
    #     The rawserver tends to wait for a long time between handling tasks.  Our tests will fail if
    #     they are delayed by the rawserver for too long.
    #     """
    #     rawserver.add_task(rawserver_adrenaline, 0.1)
    # rawserver.add_task(rawserver_adrenaline, 0.1)

    def watchdog():
        while True:
            try:
                yield 333.3
            except GeneratorExit:
                rawserver.shutdown()
                session_done_flag.set()
                break
    callback.register(watchdog)
    callback.register(start)
    rawserver.listen_forever(None)
    callback.stop()

    if callback.exception:
        global exit_exception
        exit_exception = callback.exception

    if opt.yappi:
        yappi.stop()
        print "YAPPI:", yappi.clock_type()
        stats = yappi.get_stats(yappi.SORTTYPE_TSUB)
        for func_stats in stats.func_stats[:50]:
            print "YAPPI: %10dx  %10.3fs" % (func_stats.ncall, func_stats.tsub), func_stats.name

if __name__ == "__main__":
    exit_exception = None
    main()
    if exit_exception:
        raise exit_exception
