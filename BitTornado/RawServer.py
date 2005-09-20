# Written by Bram Cohen
# see LICENSE.txt for license information

from bisect import insort
from SocketHandler import SocketHandler, UPnP_ERROR
import socket
from cStringIO import StringIO
from traceback import print_exc
from select import error
from threading import Thread, Event
from time import sleep
from clock import clock
import sys
try:
    True
except:
    True = 1
    False = 0


def autodetect_ipv6():
    try:
        assert sys.version_info >= (2,3)
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
			f = open('/proc/sys/net/ipv6/bindv6only','r')
			dual_socket_style = int(f.read())
			f.close()
			return int(not dual_socket_style)
		except:
			return 0


READSIZE = 100000

class RawServer:
    def __init__(self, doneflag, timeout_check_interval, timeout, noisy = True,
                 ipv6_enable = True, failfunc = lambda x: None, errorfunc = None,
                 sockethandler = None, excflag = Event()):
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
        
        if sockethandler is None:
            sockethandler = SocketHandler(timeout, ipv6_enable, READSIZE)
        self.sockethandler = sockethandler
        self.add_task(self.scan_for_timeouts, timeout_check_interval)

    def get_exception_flag(self):
        return self.excflag

    def _add_task(self, func, delay, id = None):
        assert float(delay) >= 0
        insort(self.funcs, (clock() + delay, func, id))

    def add_task(self, func, delay = 0, id = None):
        assert float(delay) >= 0
        self.externally_added.append((func, delay, id))

    def scan_for_timeouts(self):
        self.add_task(self.scan_for_timeouts, self.timeout_check_interval)
        self.sockethandler.scan_for_timeouts()

    def bind(self, port, bind = '', reuse = False,
                        ipv6_socket_style = 1, upnp = False):
        self.sockethandler.bind(port, bind, reuse, ipv6_socket_style, upnp)

    def find_and_bind(self, minport, maxport, bind = '', reuse = False,
                      ipv6_socket_style = 1, upnp = 0, randomizer = False):
        return self.sockethandler.find_and_bind(minport, maxport, bind, reuse,
                                 ipv6_socket_style, upnp, randomizer)

    def start_connection_raw(self, dns, socktype, handler = None):
        return self.sockethandler.start_connection_raw(dns, socktype, handler)

    def start_connection(self, dns, handler = None, randomize = False):
        return self.sockethandler.start_connection(dns, handler, randomize)

    def get_stats(self):
        return self.sockethandler.get_stats()

    def pop_external(self):
        while self.externally_added:
            (a, b, c) = self.externally_added.pop(0)
            self._add_task(a, b, c)


    def listen_forever(self, handler):
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
                    events = self.sockethandler.do_poll(period)
                    if self.doneflag.isSet():
                        return
                    while self.funcs and self.funcs[0][0] <= clock():
                        garbage1, func, id = self.funcs.pop(0)
                        if id in self.tasks_to_kill:
                            pass
                        try:
#                            print func.func_name
                            func()
                        except (SystemError, MemoryError), e:
                            self.failfunc(str(e))
                            return
                        except KeyboardInterrupt:
#                            self.exception(True)
                            return
                        except:
                            if self.noisy:
                                self.exception()
                    self.sockethandler.close_dead()
                    self.sockethandler.handle_events(events)
                    if self.doneflag.isSet():
                        return
                    self.sockethandler.close_dead()
                except (SystemError, MemoryError), e:
                    self.failfunc(str(e))
                    return
                except error:
                    if self.doneflag.isSet():
                        return
                except KeyboardInterrupt:
#                    self.exception(True)
                    return
                except:
                    self.exception()
                if self.exccount > 10:
                    return
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

    def exception(self, kbint = False):
        if not kbint:
            self.excflag.set()
        self.exccount += 1
        if self.errorfunc is None:
            print_exc()
        else:
            data = StringIO()
            print_exc(file = data)
#            print data.getvalue()   # report exception here too
            if not kbint:           # don't report here if it's a keyboard interrupt
                self.errorfunc(data.getvalue())

    def shutdown(self):
        self.sockethandler.shutdown()
