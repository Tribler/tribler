# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import subprocess
import random
import binascii
import urllib
import json
import logging
from threading import RLock
from traceback import print_exc, print_stack
from collections import defaultdict

from Tribler.Core.simpledefs import *
# from Tribler.Utilities.Instance2Instance import *
from Tribler.Utilities.FastI2I import *
from Tribler.Core.Swift.SwiftDownloadImpl import CMDGW_PREBUFFER_BYTES

try:
    WindowsError
except NameError:
    WindowsError = Exception

DONE_STATE_WORKING = 0
DONE_STATE_EARLY_SHUTDOWN = 1
DONE_STATE_SHUTDOWN = 2


class SwiftProcess:

    """ Representation of an operating-system process running the C++ swift engine.
    A swift engine can participate in one or more swarms."""

    def __init__(self, binpath, workdir, zerostatedir, listenport, httpgwport, cmdgwport, spmgr):
        self._logger = logging.getLogger(self.__class__.__name__)

        # Called by any thread, assume sessionlock is held
        self.splock = RLock()
        self.binpath = binpath
        self.workdir = workdir
        self.zerostatedir = zerostatedir
        self.spmgr = spmgr

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

        # Security: only accept commands from localhost, enable HTTP gw,
        # no stats/webUI web server
        args = []
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
        args.append("-w")
        if zerostatedir is not None:
            if sys.platform == "win32":
                # Swift on Windows expects command line arguments as UTF-16.
                # popen doesn't allow us to pass params in UTF-16, hence workaround.
                # Format = hex encoded UTF-8
                args.append("-3")
                zssafe = binascii.hexlify(zerostatedir.encode("UTF-8"))
                args.append(zssafe)  # encoding that swift expects
            else:
                args.append("-e")
                args.append(zerostatedir)
            args.append("-T")  # zero state connection timeout
            args.append("180")  # seconds
        # args.append("-B")  # Enable debugging on swift

        self._logger.debug("SwiftProcess: __init__: Running %s workdir %s", args, workdir)

        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            creationflags = 0

        # See also SwiftDef::finalize popen
        # We would really like to get the stdout and stderr without creating a new thread for them.
        # However, windows does not support non-files in the select command, hence we cannot integrate
        # these streams into the FastI2I thread
        # A proper solution would be to switch to twisted for the communication with the swift binary
        self.popen = subprocess.Popen(args, cwd=workdir, creationflags=creationflags, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def read_and_print(socket):
            prefix = currentThread().getName() + ":"
            while True:
                line = socket.readline()
                if not line:
                    self._logger.info("%s readline returned nothing quitting", prefix)
                    break
                self._logger.info("%s %s", prefix, line.rstrip())
        self.popen_outputthreads = [Thread(target=read_and_print, args=(self.popen.stdout,), name="SwiftProcess_%d_stdout" % self.listenport), Thread(target=read_and_print, args=(self.popen.stderr,), name="SwiftProcess_%d_stderr" % self.listenport)]
        [thread.start() for thread in self.popen_outputthreads]

        self.roothash2dl = {}
        self.donestate = DONE_STATE_WORKING  # shutting down
        self.fastconn = None

        # callbacks for when swift detect a channel close
        self._channel_close_callbacks = defaultdict(list)

        # Only warn once when TUNNELRECV messages are received without us having a Dispersy endpoint.  This occurs after
        # Dispersy shutdown
        self._warn_missing_endpoint = True

    #
    # Instance2Instance
    #
    def start_cmd_connection(self):
        # Called by any thread, assume sessionlock is held

        if self.is_alive():
            self.fastconn = FastI2IConnection(self.cmdport, self.i2ithread_readlinecallback, self.connection_lost)
        else:
            self._logger.info("sp: start_cmd_connection: Process dead? returncode %s pid %s", self.popen.returncode, self.popen.pid)

    def i2ithread_readlinecallback(self, ic, cmd):
        # if DEBUG:
        # print >>sys.stderr,"sp: Got command #"+cmd+"#"

        if self.donestate != DONE_STATE_WORKING:
            return

        words = cmd.split()
        assert all(isinstance(word, str) for word in words)

        if words[0] == "TUNNELRECV":
            address, session = words[1].split("/")
            host, port = address.split(":")
            port = int(port)
            session = session.decode("HEX")
            length = int(words[2])

            # require LENGTH bytes
            if len(ic.buffer) < length:
                return length - len(ic.buffer)

            data = ic.buffer[:length]
            ic.buffer = ic.buffer[length:]

            try:
                self.roothash2dl["dispersy-endpoint"].i2ithread_data_came_in(session, (host, port), data)
            except KeyError:
                if self._warn_missing_endpoint:
                    self._warn_missing_endpoint = False
                    self._logger.error("sp: Dispersy endpoint is not available")

        else:
            roothash = binascii.unhexlify(words[1])

            if words[0] == "ERROR":
                self._logger.info("sp: i2ithread_readlinecallback: %s" % cmd)

            elif words[0] == "CLOSE_EVENT":
                roothash_hex = words[1]
                address = words[2].split(":")
                address = (address[0], int(address[1]))
                raw_bytes_up = int(words[3])
                raw_bytes_down = int(words[4])
                cooked_bytes_up = int(words[5])
                cooked_bytes_down = int(words[6])

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

            self.splock.acquire()
            try:
                if roothash not in self.roothash2dl.keys():
                    self._logger.debug("sp: i2ithread_readlinecallback: unknown roothash %s", words[1])
                    return

                d = self.roothash2dl[roothash]
            except:
                # print >>sys.stderr,"GOT", words
                # print >>sys.stderr,"HAVE", [key.encode("HEX") for key in self.roothash2dl.keys()]
                raise
            finally:
                self.splock.release()

            # Hide NSSA interface for SwiftDownloadImpl
            if words[0] == "INFO":  # INFO HASH status dl/total
                dlstatus = int(words[2])
                pargs = words[3].split("/")
                dynasize = int(pargs[1])
                if dynasize == 0:
                    progress = 0.0
                else:
                    progress = float(pargs[0]) / float(pargs[1])
                dlspeed = float(words[4])
                ulspeed = float(words[5])
                numleech = int(words[6])
                numseeds = int(words[7])
                contentdl = 0  # bytes
                contentul = 0  # bytes
                if len(words) > 8:
                    contentdl = int(words[8])
                    contentul = int(words[9])
                d.i2ithread_info_callback(dlstatus, progress, dynasize, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul)
            elif words[0] == "PLAY":
                # print >>sys.stderr,"sp: i2ithread_readlinecallback: Got PLAY",cmd
                httpurl = words[2]
                d.i2ithread_vod_event_callback(httpurl)
            elif words[0] == "MOREINFO":
                jsondata = cmd[len("MOREINFO ") + 40 + 1:]
                midict = json.loads(jsondata)
                d.i2ithread_moreinfo_callback(midict)
            elif words[0] == "ERROR":
                d.i2ithread_info_callback(DLSTATUS_STOPPED_ON_ERROR, 0.0, 0, 0.0, 0.0, 0, 0, 0, 0)

    #
    # Swift Mgmt interface
    #
    def start_download(self, d):
        self.splock.acquire()
        try:
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

        finally:
            self.splock.release()

    def add_download(self, d):
        self.splock.acquire()
        try:
            roothash = d.get_def().get_roothash()

            # Before send to handle INFO msgs
            self.roothash2dl[roothash] = d

        finally:
            self.splock.release()

    def remove_download(self, d, removestate, removecontent):
        self.splock.acquire()
        try:
            if self.donestate != DONE_STATE_WORKING or not self.is_alive():
                return

            roothash_hex = d.get_def().get_roothash_as_hex()

            self.send_remove(roothash_hex, removestate, removecontent)

            # After send to handle INFO msgs
            roothash = d.get_def().get_roothash()

            del self.roothash2dl[roothash]
        finally:
            self.splock.release()

    def get_downloads(self):
        self.splock.acquire()
        try:
            return self.roothash2dl.values()
        finally:
            self.splock.release()

    def get_pid(self):
        if self.popen is not None:
            return self.popen.pid
        else:
            return -1

    def get_listen_port(self):
        return self.listenport

    def set_max_speed(self, d, direct, speed):
        self.splock.acquire()
        try:
            if self.donestate != DONE_STATE_WORKING or not self.is_alive():
                return

            roothash_hex = d.get_def().get_roothash_as_hex()

            # In Tribler Core API  = unlimited. In Swift CMDGW API
            # 0 = none.
            if speed == 0.0:
                speed = 4294967296.0

            self.send_max_speed(roothash_hex, direct, speed)
        finally:
            self.splock.release()

    def checkpoint_download(self, d):
        self.splock.acquire()
        try:
            # Arno, 2012-05-15: Allow during shutdown.
            if not self.is_alive():
                return

            roothash_hex = d.get_def().get_roothash_as_hex()
            self.send_checkpoint(roothash_hex)
        finally:
            self.splock.release()

    def set_moreinfo_stats(self, d, enable):
        self.splock.acquire()
        try:
            if self.donestate != DONE_STATE_WORKING or not self.is_alive():
                return

            roothash_hex = d.get_def().get_roothash_as_hex()
            self.send_setmoreinfo(roothash_hex, enable)
        finally:
            self.splock.release()

    def set_subscribe_channel_close(self, download, enable, callback):
        # Note that CALLBACK is called on the i2ithread, and hence should not lock
        self.splock.acquire()
        try:
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
        finally:
            self.splock.release()

    def add_peer(self, d, addr):
        self.splock.acquire()
        try:
            if self.donestate != DONE_STATE_WORKING or not self.is_alive():
                return

            addrstr = addr[0] + ':' + str(addr[1])
            roothash_hex = d.get_def().get_roothash_as_hex()
            self.send_peer_addr(roothash_hex, addrstr)
        finally:
            self.splock.release()

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
        # assume splock is held to avoid concurrency on socket
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
        # assume splock is held to avoid concurrency on socket
        self.write('REMOVE ' + roothash_hex + ' ' + str(int(removestate)) + ' ' + str(int(removecontent)) + '\r\n')

    def send_checkpoint(self, roothash_hex):
        # assume splock is held to avoid concurrency on socket
        self.write('CHECKPOINT ' + roothash_hex + '\r\n')

    def send_shutdown(self):
        # assume splock is held to avoid concurrency on socket
        self.write('SHUTDOWN\r\n')

    def send_max_speed(self, roothash_hex, direct, speed):
        # assume splock is held to avoid concurrency on socket
        cmd = 'MAXSPEED ' + roothash_hex
        if direct == DOWNLOAD:
            cmd += ' DOWNLOAD '
        else:
            cmd += ' UPLOAD '
        cmd += str(float(speed)) + '\r\n'

        self.write(cmd)

    def send_tunnel(self, session, address, data):
        # assume splock is held to avoid concurrency on socket
        self._logger.debug("sp: send_tunnel:" + repr(len(data)) + "bytes -> %s:%d" % address)

        self.write("TUNNELSEND %s:%d/%s %d\r\n" % (address[0], address[1], session.encode("HEX"), len(data)))
        self.write(data)

    def send_setmoreinfo(self, roothash_hex, enable):
        # assume splock is held to avoid concurrency on socket
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
        # assume splock is held to avoid concurrency on socket
        self._logger.debug("sp: send_subscribe: %s %s %s", roothash_hex, event_type, enable)
        self.write("SUBSCRIBE %s %s %d\r\n" % (roothash_hex, event_type, int(enable),))

    def send_peer_addr(self, roothash_hex, addrstr):
        # assume splock is held to avoid concurrency on socket
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
        self.spmgr.connection_lost(port)
