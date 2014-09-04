# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import time
import subprocess
import random
import binascii
import urllib
import json
import logging
from threading import RLock, currentThread, Thread
from traceback import print_exc
from collections import defaultdict

from Tribler.Core.simpledefs import UPLOAD, DOWNLOAD, DLSTATUS_STOPPED_ON_ERROR
from Tribler.Utilities.FastI2I import FastI2IConnection

try:
    WindowsError
except NameError:
    WindowsError = Exception

DONE_STATE_WORKING = 0
DONE_STATE_EARLY_SHUTDOWN = 1
DONE_STATE_SHUTDOWN = 2


class SwiftProcess(object):

    """ Representation of an operating-system process running the C++ swift engine.
    A swift engine can participate in one or more swarms."""

    def __init__(self, binpath, workdir, zerostatedir, listenport, httpgwport, cmdgwport, spmgr, extra_subprocess_flags):
        self._logger = logging.getLogger(self.__class__.__name__)

        # Called by any thread, assume sessionlock is held
        self.splock = RLock()
        self.binpath = binpath
        self.workdir = workdir
        self.zerostatedir = zerostatedir
        self.spmgr = spmgr
        self.extra_subprocess_flags = extra_subprocess_flags

        # Main UDP listen socket
        if listenport is None:
            self.listenport = random.randint(10001, 10999)
        else:
            self.listenport = listenport
        # NSSA control socket
        if cmdgwport is None:
            self.cmdport = random.randint(11001, 11999)
        else:
            self.cmdport = cmdgwport
        # content web server
        if httpgwport is None:
            self.httpport = random.randint(12001, 12999)
        else:
            self.httpport = httpgwport

        self.popen = None
        self.popen_outputthreads = None
        self.pid = None

        # callbacks for when swift detect a channel close
        self._channel_close_callbacks = defaultdict(list)

        self.roothash2dl = dict()
        self.donestate = DONE_STATE_WORKING  # shutting down
        self.fastconn = None
        self.tunnels = dict()

        # Only warn once when TUNNELRECV messages are received without us having a Dispersy endpoint.  This occurs after
        # Dispersy shutdown
        self._warn_missing_endpoint = True

    def start_process(self):
        with self.splock:
            # Security: only accept commands from localhost, enable HTTP gw,
            # no stats/webUI web server
            args = list()
            # Arno, 2012-07-09: Unicode problems with popen
            args.append(self.binpath.encode(sys.getfilesystemencoding()))

            # Arno, 2012-05-29: Hack. Win32 getopt code eats first arg when Windows app
            # instead of CONSOLE app.
            args.append("-j")
            args.append("-l")  # listen port
            args.append("0.0.0.0:" + str(self.listenport))
            args.append("-c")  # command port
            args.append("127.0.0.1:" + str(self.cmdport))
            args.append("-g")  # HTTP gateway port
            args.append("127.0.0.1:" + str(self.httpport))

            if self.zerostatedir is not None:
                if sys.platform == "win32":
                    # Swift on Windows expects command line arguments as UTF-16.
                    # popen doesn't allow us to pass params in UTF-16, hence workaround.
                    # Format = hex encoded UTF-8
                    args.append("-3")
                    zssafe = binascii.hexlify(self.zerostatedir.encode("UTF-8"))
                    args.append(zssafe)  # encoding that swift expects
                else:
                    args.append("-e")
                    args.append(self.zerostatedir)
                args.append("-T")  # zero state connection timeout
                args.append("180")  # seconds
            # args.append("-B")  # Enable debugging on swift

            # make swift quiet
            args.append("-q")

            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                creationflags = 0
            creationflags |= self.extra_subprocess_flags

            # See also SwiftDef::finalize popen
            # We would really like to get the stdout and stderr without creating a new thread for them.
            # However, windows does not support non-files in the select command, hence we cannot integrate
            # these streams into the FastI2I thread
            # A proper solution would be to switch to twisted for the communication with the swift binary
            self.popen = subprocess.Popen(args, cwd=self.workdir, creationflags=creationflags,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.pid = self.popen.pid

            class ReadAndPrintThread(Thread):
                def __init__(self, sp, name, socket):
                    super(ReadAndPrintThread, self).__init__(name=name)
                    self.sp = sp
                    self.socket = socket
                    self.last_line = ''

                def run(self):
                    prefix = currentThread().getName() + ":"
                    while True:
                        self.last_line = self.socket.readline()
                        if not self.last_line:
                            self.sp._logger.info("%s readline returned nothing quitting", prefix)
                            break
                        self.sp._logger.debug("%s %s", prefix, self.last_line.rstrip())

                def get_last_line(self):
                    return self.last_line

            self.popen_outputthreads = [ReadAndPrintThread(self, "[%d]SwiftProc[%d]stdout" %
                                                           (self.pid, self.listenport), self.popen.stdout),
                                        ReadAndPrintThread(self, "[%d]SwiftProc[%d]stderr" %
                                                           (self.pid, self.listenport), self.popen.stderr)]
            [thread.start() for thread in self.popen_outputthreads]

    #
    # Instance2Instance
    #
    def start_cmd_connection(self):
        # Called by any thread, assume sessionlock is held
        with self.splock:
            if self.is_alive():
                self.fastconn = FastI2IConnection(self.cmdport, self.i2ithread_readlinecallback, self.connection_lost)

            else:
                self._logger.error("sp: start_cmd_connection: Process dead? returncode %s pid %s",
                                   self.popen.returncode, self.popen.pid)
                for thread in self.popen_outputthreads:
                    self._logger.error("sp popenthread %s last line %s", thread.getName(), thread.get_last_line())
                # restart process
                self.start_process()

                self.donestate = DONE_STATE_WORKING  # shutting down

                old_tunnels = self.tunnels
                self.tunnels = dict()


                # Only warn once when TUNNELRECV messages are received without us having a Dispersy endpoint.  This occurs after
                # Dispersy shutdown
                self._warn_missing_endpoint = True

                # Arno, 2011-10-13: On Linux swift is slow to start and
                # allocate the cmd listen socket?!
                # 2012-05-23: connection_lost() will attempt another
                # connect when the first fails, so not timing dependent,
                # just ensures no send_()s get lost. Executed by NetworkThread.
                # 2014-06-16: Having the same issues on Windows with multiple
                # swift processes. Now always sleep, no matter which
                # platform we're using.
                self._logger.warn("spm: Need to sleep 1 second for swift to start?! FIXME")
                time.sleep(1)

                self.fastconn = FastI2IConnection(self.cmdport, self.i2ithread_readlinecallback, self.connection_lost)

                # start the swift downloads again
                for _, swift_download in self.roothash2dl.items():
                    self.start_download(swift_download)


                # In case swift died and we are recovering from that, reregister all
                # the tunnels that existed in the previous session.
                for tunnel, callback in old_tunnels.iteritems():
                    self._logger.info("Reregistering tunnel from crashed swfit: %s %s", tunnel, callback)
                    self.register_tunnel(tunnel, callback)

    def i2ithread_readlinecallback(self, cmd_buffer):
        if self.donestate != DONE_STATE_WORKING:
            return ''

        while cmd_buffer.find(" ") >= 0:
            swift_cmd, swift_body = cmd_buffer.split(" ", 1)
            assert swift_cmd in ["TUNNELRECV", "ERROR", "CLOSE_EVENT", "INFO", "PLAY", "MOREINFO"], swift_cmd

            self._logger.debug("sp: Got command %s, buffer size %d", swift_cmd, len(cmd_buffer))

            if swift_cmd == "TUNNELRECV":
                header, _, payload = swift_body.partition("\r\n")
                if payload:
                    from_session, length = header.split(" ", 1)
                    address, session = from_session.split("/")
                    host, port = address.split(":")
                    port = int(port)
                    session = session.decode("HEX")
                    length = int(length)

                    if len(payload) >= length:
                        if session not in self.tunnels:
                            if self._warn_missing_endpoint:
                                self._warn_missing_endpoint = False
                                self._logger.error("missing endpoint for tunnel %s, listening on port %d", session, self.get_listen_port())
                        else:
                            self.tunnels[session](session, (host, port), payload[:length])

                        cmd_buffer = payload[length:]
                        continue

                return cmd_buffer

            else:
                if swift_body.find('\r\n') == -1:  # incomplete command
                    return cmd_buffer

                swift_body, _, cmd_buffer = swift_body.partition("\r\n")
                # print >> sys.stderr, "sp: Got command", swift_cmd, swift_body

                roothash_hex = swift_body.split(" ", 1)[0]
                roothash = binascii.unhexlify(roothash_hex)

                if swift_cmd == "CLOSE_EVENT":
                    _, address, raw_bytes_up, raw_bytes_down, cooked_bytes_up, cooked_bytes_down = swift_body.split(" ", 5)
                    address = address.split(":")
                    address = (address[0], int(address[1]))
                    raw_bytes_up = int(raw_bytes_up)
                    raw_bytes_down = int(raw_bytes_down)
                    cooked_bytes_up = int(cooked_bytes_up)
                    cooked_bytes_down = int(cooked_bytes_down)

                    if roothash_hex in self._channel_close_callbacks:
                        for callback in self._channel_close_callbacks[roothash_hex]:
                            try:
                                callback(roothash_hex, address, raw_bytes_up, raw_bytes_down, cooked_bytes_up, cooked_bytes_down)
                            except:
                                pass

                    for callback in self._channel_close_callbacks["ALL"]:
                        try:
                            callback(roothash_hex, address, raw_bytes_up, raw_bytes_down, cooked_bytes_up, cooked_bytes_down)
                        except:
                            pass

                else:
                    with self.splock:
                        if roothash not in self.roothash2dl:
                            self._logger.debug("sp: i2ithread_readlinecallback: unknown roothash %s", roothash)
                            continue

                        d = self.roothash2dl[roothash]

                    # Hide NSSA interface for SwiftDownloadImpl
                    if swift_cmd == "INFO":  # INFO HASH status dl/total
                        words = swift_body.split()
                        if len(words) > 8:
                            _, dlstatus, pargs, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul = words
                        else:
                            _, dlstatus, pargs, dlspeed, ulspeed, numleech, numseeds = words
                            contentdl, contentul = 0, 0

                        dlstatus = int(dlstatus)
                        pargs = pargs.split("/")
                        dynasize = int(pargs[1])
                        if dynasize == 0:
                            progress = 0.0
                        else:
                            progress = float(pargs[0]) / float(pargs[1])

                        dlspeed = float(dlspeed)
                        ulspeed = float(ulspeed)
                        numleech = int(numleech)
                        numseeds = int(numseeds)
                        contentdl = int(contentdl)
                        contentul = int(contentul)

                        d.i2ithread_info_callback(dlstatus, progress, dynasize, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul)

                    elif swift_cmd == "PLAY":
                        httpurl = swift_body.split(" ", 1)[1]
                        d.i2ithread_vod_event_callback(httpurl)

                    elif swift_cmd == "MOREINFO":
                        jsondata = swift_body[40:]
                        midict = json.loads(jsondata)
                        d.i2ithread_moreinfo_callback(midict)

                    elif swift_cmd == "ERROR":
                        d.i2ithread_info_callback(DLSTATUS_STOPPED_ON_ERROR, 0.0, 0, 0.0, 0.0, 0, 0, 0, 0)

                    else:
                        self._logger.debug("sp: unknown command %s", swift_cmd)

        return cmd_buffer

    # Swift Mgmt interface
    #

    def register_tunnel(self, prefix, callback):
        with self.splock:
            if prefix not in self.tunnels:
                # register new channel prefix
                self.tunnels[prefix] = callback
                self.send_tunnel_subscribe(prefix)
            else:
                raise RuntimeError("Tunnel already registered by another module")

    def unregister_tunnel(self, prefix, send_unsubscribe=False):
        with self.splock:
            if prefix in self.tunnels:
                # unregister channel prefix
                del self.tunnels[prefix]

                if send_unsubscribe:
                    self.send_tunnel_unsubscribe(prefix)
            else:
                self._logger.info("sp: unregister_tunnel: Error, no tunnel has been registered with prefix: %s" % prefix)

    def start_download(self, d):
        with self.splock:
            if self.donestate != DONE_STATE_WORKING or not self.is_alive():
                return

            roothash = d.get_def().get_roothash()
            roothash_hex = d.get_def().get_roothash_as_hex()

            # Before send to handle INFO msgs
            self.roothash2dl[roothash] = d
            url = d.get_def().get_url()

            # MULTIFILE
            if len(d.get_selected_files()) == 1:
                specpath = d.get_selected_files()[0]
                qpath = urllib.quote(specpath)
                url += "/" + qpath

            # Default is unlimited, so don't send MAXSPEED then
            maxdlspeed = d.get_max_speed(DOWNLOAD)
            if maxdlspeed == 0:
                maxdlspeed = None
            maxulspeed = d.get_max_speed(UPLOAD)
            if maxulspeed == 0:
                maxulspeed = None

            metadir = d.get_swift_meta_dir()

            self.send_start(url, roothash_hex=roothash_hex, maxdlspeed=maxdlspeed, maxulspeed=maxulspeed, destdir=d.get_dest_dir(), metadir=metadir)

    def add_download(self, d):
        with self.splock:
            roothash = d.get_def().get_roothash()

            # Before send to handle INFO msgs
            self.roothash2dl[roothash] = d

    def remove_download(self, d, removestate, removecontent):
        with self.splock:
            if self.donestate != DONE_STATE_WORKING or not self.is_alive():
                return

            roothash_hex = d.get_def().get_roothash_as_hex()

            self.send_remove(roothash_hex, removestate, removecontent)

            # After send to handle INFO msgs
            roothash = d.get_def().get_roothash()

            del self.roothash2dl[roothash]

    def get_downloads(self):
        return self.roothash2dl.values()

    def get_pid(self):
        if self.popen is not None:
            return self.popen.pid
        else:
            return -1

    def get_listen_port(self):
        return self.listenport

    def set_max_speed(self, d, direct, speed):
        if self.donestate != DONE_STATE_WORKING or not self.is_alive():
            return

        roothash_hex = d.get_def().get_roothash_as_hex()

        # In Tribler Core API  = unlimited. In Swift CMDGW API
        # 0 = none.
        if speed == 0.0:
            speed = 4294967296.0

        self.send_max_speed(roothash_hex, direct, speed)

    def checkpoint_download(self, d):
        # Arno, 2012-05-15: Allow during shutdown.
        if not self.is_alive():
            return

        roothash_hex = d.get_def().get_roothash_as_hex()
        self.send_checkpoint(roothash_hex)

    def set_moreinfo_stats(self, d, enable):
        if self.donestate != DONE_STATE_WORKING or not self.is_alive():
            return

        roothash_hex = d.get_def().get_roothash_as_hex()
        self.send_setmoreinfo(roothash_hex, enable)

    def set_subscribe_channel_close(self, download, enable, callback):
        if self.donestate != DONE_STATE_WORKING or not self.is_alive():
            return

        roothash_hex = download.get_def().get_roothash_as_hex() if (download is None or download != "ALL") else "ALL"
        if enable:
            if not self._channel_close_callbacks[roothash_hex]:
                self.send_subscribe(roothash_hex, "CHANNEL_CLOSE", True)
            self._channel_close_callbacks[roothash_hex].append(callback)

        else:
            self._channel_close_callbacks[roothash_hex].remove(callback)
            if not self._channel_close_callbacks[roothash_hex]:
                self.send_subscribe(roothash_hex, "CHANNEL_CLOSE", False)

    def add_peer(self, d, addr):
        if self.donestate != DONE_STATE_WORKING or not self.is_alive():
            return

        addrstr = addr[0] + ':' + str(addr[1])
        roothash_hex = d.get_def().get_roothash_as_hex()
        self.send_peer_addr(roothash_hex, addrstr)

    def early_shutdown(self):
        # Called by any thread, assume sessionlock is held
        # May get called twice, once by spm.release_sp() and spm.shutdown()
        if self.donestate == DONE_STATE_WORKING:
            self.donestate = DONE_STATE_EARLY_SHUTDOWN
        else:
            return

        if self.fastconn:
            # Tell engine to shutdown so it can deregister dls from tracker
            self._logger.info("sp: Telling process to shutdown")
            self.send_shutdown()

    def network_shutdown(self):
        # Called by network thread, assume sessionlock is held
        if self.donestate == DONE_STATE_EARLY_SHUTDOWN:
            self.donestate = DONE_STATE_SHUTDOWN
        else:
            return

        if self.popen is not None:
            try:
                self._logger.info("sp: Terminating process")
                self.popen.terminate()
                self.popen.wait()
                self.popen = None
            except WindowsError:
                pass
            except:
                print_exc()

        if self.fastconn:
            self.fastconn.stop()

    #
    # Internal methods
    #
    def send_start(self, url, roothash_hex=None, maxdlspeed=None, maxulspeed=None, destdir=None, metadir=None):
        self._logger.info("sp: send_start: %s, destdir=%s, metadir=%s", url, destdir, metadir)

        cmd = 'START ' + url
        if destdir is not None:
            cmd += ' ' + destdir.encode("UTF-8")
            if metadir is not None:
                cmd += ' ' + metadir.encode("UTF-8")
        cmd += '\r\n'
        if maxdlspeed is not None:
            cmd += 'MAXSPEED ' + roothash_hex + ' DOWNLOAD ' + str(float(maxdlspeed)) + '\r\n'
        if maxulspeed is not None:
            cmd += 'MAXSPEED ' + roothash_hex + ' UPLOAD ' + str(float(maxulspeed)) + '\r\n'

        self.write(cmd)

    def send_remove(self, roothash_hex, removestate, removecontent):
        self.write('REMOVE ' + roothash_hex + ' ' + str(int(removestate)) + ' ' + str(int(removecontent)) + '\r\n')

    def send_checkpoint(self, roothash_hex):
        self.write('CHECKPOINT ' + roothash_hex + '\r\n')

    def send_shutdown(self):
        self.write('SHUTDOWN\r\n')

    def send_max_speed(self, roothash_hex, direct, speed):
        cmd = 'MAXSPEED ' + roothash_hex
        if direct == DOWNLOAD:
            cmd += ' DOWNLOAD '
        else:
            cmd += ' UPLOAD '
        cmd += str(float(speed)) + '\r\n'

        self.write(cmd)

    def send_tunnel_subscribe(self, prefix):
        self._logger.debug("sp: send_tunnel_subcribe to prefix:" + prefix.encode("HEX"))

        self.write("TUNNELSUBSCRIBE %s\r\n" % (prefix.encode("HEX")))

    def send_tunnel_unsubscribe(self, prefix):
        self._logger.debug("sp: send_tunnel_unsubcribe prefix:" + prefix.encode("HEX"))

        self.write("TUNNELUNSUBSCRIBE %s\r\n" % (prefix.encode("HEX")))

    def send_tunnel(self, session, address, data):
        self._logger.debug("sp: send_tunnel:" + repr(len(data)) + "bytes -> %s:%d" % address)

        cmd = "TUNNELSEND %s:%d/%s %d\r\n" % (address[0], address[1], session.encode("HEX"), len(data))
        self.write(cmd + data)

    def send_setmoreinfo(self, roothash_hex, enable):
        onoff = "0"
        if enable:
            onoff = "1"
        self.write('SETMOREINFO ' + roothash_hex + ' ' + onoff + '\r\n')

    def send_subscribe(self, roothash_hex, event_type, enable):
        """
        Subscribe to a libswift event.

        ROOTHASH_HEX can currently only be "ALL"
        EVENT_TYPE can currently only be "CHANNEL_CLOSE"
        ENABLE can be either True or False
        """
        assert roothash_hex == "ALL"
        assert event_type == "CHANNEL_CLOSE"
        assert isinstance(enable, bool), type(enable)
        self._logger.debug("sp: send_subscribe: %s %s %s", roothash_hex, event_type, enable)
        self.write("SUBSCRIBE %s %s %d\r\n" % (roothash_hex, event_type, int(enable),))

    def send_peer_addr(self, roothash_hex, addrstr):
        self.write('PEERADDR ' + roothash_hex + ' ' + addrstr + '\r\n')

    def is_alive(self):
        if self.popen:
            self.popen.poll()
            return self.popen.returncode is None
        return False

    def write(self, msg):
        self.fastconn.write(msg)

    def get_cmdport(self):
        return self.cmdport

    def connection_lost(self, port):
        self._logger.warn("Connection lost for port %s", port)
        self.spmgr.connection_lost(port)
