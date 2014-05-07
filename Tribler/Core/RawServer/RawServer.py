# Written by Bram Cohen and Pawel Garbacki
# see LICENSE.txt for license information

from bisect import insort
from SocketHandler import SocketHandler
import socket
from traceback import print_exc
from select import error
from threading import Event, RLock
from thread import get_ident
from Tribler.Core.Utilities.clock import clock
import sys
import logging

from Tribler.dispersy.decorator import attach_profiler

try:
    True
except:
    True = 1
    False = 0


def autodetect_ipv6():
    try:
        assert sys.version_info >= (2, 3)
        assert socket.has_ipv6
        socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    except:
        return 0
    return 1


def autodetect_socket_style():
    if sys.platform.find('linux') < 0:
        return 1
    else:
        try:
            f = open('/proc/sys/net/ipv6/bindv6only', 'r')
            dual_socket_style = int(f.read())
            f.close()
            return int(not dual_socket_style)
        except:
            return 0


READSIZE = 100000


class RawServer:

    def __init__(self, doneflag, timeout_check_interval, timeout, noisy=True,
                 ipv6_enable=True, failfunc= lambda x: None, errorfunc = None,
                 sockethandler=None, excflag= Event()):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.timeout_check_interval = timeout_check_interval
        self.timeout = timeout
        self.servers = {}
        self.single_sockets = {}
        self.dead_from_write = []
        self.doneflag = doneflag
        self.noisy = noisy
        self.failfunc = failfunc
        self.errorfunc = errorfunc
        self.exccount = 0
        self.funcs = []
        self.externally_added = []
        self.finished = Event()
        self.tasks_to_kill = []
        self.excflag = excflag
        self.lock = RLock()

        if sockethandler is None:
            sockethandler = SocketHandler(timeout, ipv6_enable, READSIZE)
        self.sockethandler = sockethandler

        self.thread_ident = None
        self.interrupt_socket = sockethandler.get_interrupt_socket()

        self.add_task(self.scan_for_timeouts, timeout_check_interval)

    def get_exception_flag(self):
        return self.excflag

    def _add_task(self, func, delay, id=None):
        if delay < 0:
            delay = 0
        insort(self.funcs, (clock() + delay, func, id))

    def add_task(self, func, delay=0, id= None):
        # if DEBUG:
        #    print >>sys.stderr,"rawserver: add_task(",func,delay,")"
        if delay < 0:
            delay = 0

        self.lock.acquire()
        self.externally_added.append((func, delay, id))
        self.lock.release()

        if self.thread_ident != get_ident():
            self.interrupt_socket.interrupt()

    def scan_for_timeouts(self):
        self.add_task(self.scan_for_timeouts, self.timeout_check_interval)
        self.sockethandler.scan_for_timeouts()

    def bind(self, port, bind='', reuse= False,
            ipv6_socket_style=1, handler=None):
        self.sockethandler.bind(port, bind, reuse, ipv6_socket_style, handler)

    def find_and_bind(self, first_try, minport, maxport, bind='', reuse = False,
                      ipv6_socket_style=1, randomizer= False, handler=None):
# 2fastbt_
        result = self.sockethandler.find_and_bind(first_try, minport, maxport, bind, reuse,
                                 ipv6_socket_style, randomizer, handler)
# _2fastbt
        return result

    def start_connection_raw(self, dns, socktype=socket.AF_INET, handler= None):
        return self.sockethandler.start_connection_raw(dns, socktype, handler)

    def start_connection(self, dns, handler=None, randomize= False):
        return self.sockethandler.start_connection(dns, handler, randomize)

    def get_stats(self):
        return self.sockethandler.get_stats()

    def pop_external(self):
        self.lock.acquire()
        while self.externally_added:
            (a, b, c) = self.externally_added.pop(0)
            self._add_task(a, b, c)
        self.lock.release()

    @attach_profiler
    def listen_forever(self, handler):
        self._logger.debug("rawserver: listen forever()")
        # handler=btlanuchmany: MultiHandler, btdownloadheadless: Encoder
        self.thread_ident = get_ident()
        self.sockethandler.set_handler(handler)
        try:
            while not self.doneflag.isSet():
                try:
                    self.pop_external()
                    self._kill_tasks()
                    if self.funcs:
                        period = self.funcs[0][0] + 0.001 - clock()
                    else:
                        period = 2 ** 30
                    if period < 0:
                        period = 0

                    # if DEBUG:
                    #    print >>sys.stderr,"rawserver: do_poll",period
                    events = self.sockethandler.do_poll(period)

                    if self.doneflag.isSet():
                        self._logger.debug("rawserver: stopping because done flag set")
                        return

                    # print >>sys.stderr,"RawServer: funcs is",`self.funcs`

                    while self.funcs and self.funcs[0][0] <= clock() and not self.doneflag.isSet():
                        garbage1, func, id = self.funcs.pop(0)
                        if id in self.tasks_to_kill:
                            pass
                        try:
#                            print func.func_name
                            if func.func_name != "_bgalloc":
                                self._logger.debug("RawServer:f %s", func.func_name)
                            # st = time.time()
                            func()
                            # et = time.time()
                            # diff = et - st
                            # print >>sys.stderr,func,"took %.5f" % (diff)

                        except (SystemError, MemoryError) as e:
                            self.failfunc(e)
                            return
                        except KeyboardInterrupt as e:
#                            self.exception(e)
                            return
                        except error:
                            self._logger.debug("rawserver: func: ERROR exception")
                            print_exc()
                            pass
                        except Exception as e:
                            # boudewijn: someone made a big mistake,
                            # the code will not function as expected.
                            # notify someone for *uck sake!  instead
                            # of silently hiding the problem and
                            # continuing...
                            # raise
                            self._logger.debug("rawserver: func: any exception")
                            print_exc()
                            if self.noisy:
                                self.exception(e)

                    self.sockethandler.close_dead()
                    self.sockethandler.handle_events(events)

                except (SystemError, MemoryError) as e:
                    self._logger.debug("rawserver: SYS/MEM exception %s", e)
                    self.failfunc(e)
                    return

                except error:
                    self._logger.debug("rawserver: ERROR exception")
                    print_exc()

                except KeyboardInterrupt as e:
                    self.failfunc(e)
                    return

                except Exception as e:
                    # boudewijn: someone made a big mistake, the code
                    # will not function as expected.  notify someone
                    # for *uck sake!  instead of silently hiding the
                    # problem and continuing...
                    # raise
                    self._logger.debug("rawserver: other exception")
                    print_exc()
                    self.exception(e)
                # Arno: Don't stop till we drop
                # if self.exccount > 10:
                # print >> sys.stderr,"rawserver: stopping because exccount > 10"
                # return
        finally:
#            self.sockethandler.shutdown()
            self.finished.set()

    def is_finished(self):
        return self.finished.isSet()

    def wait_until_finished(self):
        self.finished.wait()

    def _kill_tasks(self):
        if self.tasks_to_kill:
            new_funcs = []
            for (t, func, id) in self.funcs:
                if id not in self.tasks_to_kill:
                    new_funcs.append((t, func, id))
            self.funcs = new_funcs
            self.tasks_to_kill = []

    def kill_tasks(self, id):
        self.tasks_to_kill.append(id)

    def exception(self, e, kbint=False):
        if not kbint:
            self.excflag.set()
        self.exccount += 1
        if self.errorfunc is None:
            print_exc()
        else:
            if not kbint:   # don't report here if it's a keyboard interrupt
                self.errorfunc(e)

    def shutdown(self):
        self.sockethandler.shutdown()

    #
    # Interface for Khashmir
    #
    def create_udpsocket(self, port, host):
        self._logger.debug("rawudp: create_udp_socket %s %s", host, port)
        return self.sockethandler.create_udpsocket(port, host)

    def start_listening_udp(self, serversocket, handler):
        self._logger.debug("rawudp: start_listen: %s %s", serversocket, handler)
        self.sockethandler.start_listening_udp(serversocket, handler)

    def stop_listening_udp(self, serversocket):
        self._logger.debug("rawudp: stop_listen: %s", serversocket)
        self.sockethandler.stop_listening_udp(serversocket)
