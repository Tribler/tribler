# Written by Bram Cohen and Pawel Garbacki
# see LICENSE.txt for license information

from bisect import insort
from SocketHandler import SocketHandler
import socket
from cStringIO import StringIO
from traceback import print_exc
from select import error
from threading import Event, RLock
from clock import clock
import sys

try:
    True
except:
    True = 1
    False = 0

DEBUG = False

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
        self.lock = RLock()        

        if sockethandler is None:
            sockethandler = SocketHandler(timeout, ipv6_enable, READSIZE)
        self.sockethandler = sockethandler
        self.add_task(self.scan_for_timeouts, timeout_check_interval)

    def get_exception_flag(self):
        return self.excflag

    def _add_task(self, func, delay, id = None):
        if delay < 0:
            delay = 0
        insort(self.funcs, (clock() + delay, func, id))

    def add_task(self, func, delay = 0, id = None):
        #if DEBUG:
        #    print >>sys.stderr,"rawserver: add_task(",func,delay,")"
        if delay < 0:
            delay = 0
        self.lock.acquire()
        self.externally_added.append((func, delay, id))
        self.lock.release()

    def scan_for_timeouts(self):
        self.add_task(self.scan_for_timeouts, self.timeout_check_interval)
        self.sockethandler.scan_for_timeouts()

    def bind(self, port, bind = '', reuse = False,
                        ipv6_socket_style = 1):
        self.sockethandler.bind(port, bind, reuse, ipv6_socket_style)

    def find_and_bind(self, first_try, minport, maxport, bind = '', reuse = False, 
                      ipv6_socket_style = 1, randomizer = False):
# 2fastbt_
        result = self.sockethandler.find_and_bind(first_try, minport, maxport, bind, reuse, 
                                 ipv6_socket_style, randomizer)
# _2fastbt
        return result

    def start_connection_raw(self, dns, socktype, handler = None):
        return self.sockethandler.start_connection_raw(dns, socktype, handler)

    def start_connection(self, dns, handler = None, randomize = False):
        return self.sockethandler.start_connection(dns, handler, randomize)

    def get_stats(self):
        return self.sockethandler.get_stats()

    def pop_external(self):
        self.lock.acquire()
        while self.externally_added:
            (a, b, c) = self.externally_added.pop(0)
            self._add_task(a, b, c)
        self.lock.release()

    def listen_forever(self, handler):
        if DEBUG:
            print >>sys.stderr,"rawserver: listen forever()"
        # handler=btlanuchmany: MultiHandler, btdownloadheadless: Encoder
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
                        
                    #if DEBUG:
                    #    print >>sys.stderr,"rawserver: do_poll",period

                    events = self.sockethandler.do_poll(period)
                    if self.doneflag.isSet():
                        if DEBUG:
                            print >> sys.stderr,"rawserver: stopping because done flag set"
                        return
                    while self.funcs and self.funcs[0][0] <= clock():
                        garbage1, func, id = self.funcs.pop(0)
                        if id in self.tasks_to_kill:
                            pass
                        try:
#                            print func.func_name
                            if DEBUG:
                                if func.func_name != "_bgalloc":
                                    print >> sys.stderr,"RawServer:f",func.func_name
                            func()
                        except (SystemError, MemoryError), e:
                            self.failfunc(e)
                            return
                        except KeyboardInterrupt,e:
#                            self.exception(e)
                            return
                        except error:
                            if DEBUG:
                                print >> sys.stderr,"rawserver: func: ERROR exception"
                                print_exc()
                        except Exception,e:
                            if DEBUG:
                                print >> sys.stderr,"rawserver: func: any exception"
                                print_exc()
                            if self.noisy:
                                self.exception(e)
                    self.sockethandler.close_dead()
                    self.sockethandler.handle_events(events)
                    if self.doneflag.isSet():
                        if DEBUG:
                            print >> sys.stderr,"rawserver: stopping because done flag set2"
                        return
                    self.sockethandler.close_dead()
                except (SystemError, MemoryError), e:
                    if DEBUG:
                        print >> sys.stderr,"rawserver: SYS/MEM exception",e
                    self.failfunc(e)
                    return
                except error:
                    if DEBUG:
                        print >> sys.stderr,"rawserver: ERROR exception"
                        print_exc()
                    if self.doneflag.isSet():
                        return
                except KeyboardInterrupt,e:
                    self.failfunc(e)
                    return
                except Exception,e:
                    if DEBUG:
                        print >> sys.stderr,"rawserver: other exception"
                    print_exc()
                    self.exception(e)
                ## Arno: Don't stop till we drop
                ##if self.exccount > 10:
                ##    print >> sys.stderr,"rawserver: stopping because exccount > 10"
                ##    return
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

    def exception(self,e,kbint=False):
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
    def create_udpsocket(self,port,host):
        if DEBUG:
            print >>sys.stderr,"rawudp: create_udp_socket",host,port
        return self.sockethandler.create_udpsocket(port,host)
        
    def start_listening_udp(self,serversocket,handler):
        if DEBUG:
            print >>sys.stderr,"rawudp: start_listen:",serversocket,handler
        self.sockethandler.start_listening_udp(serversocket,handler)
    
    def stop_listening_udp(self,serversocket):
        if DEBUG:
            print >>sys.stderr,"rawudp: stop_listen:",serversocket
        self.sockethandler.stop_listening_udp(serversocket)
        