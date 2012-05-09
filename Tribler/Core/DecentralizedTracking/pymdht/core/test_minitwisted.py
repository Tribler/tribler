# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from __future__ import with_statement

import logging
import sys
import threading
import socket

from nose.tools import eq_, ok_, assert_raises

import logging_conf
import ptime as time
import test_const as tc
from message import Datagram
from testing_mocks import MockTimeoutSocket

import minitwisted
from minitwisted import ThreadedReactor

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')

DATA1 = 'testing...1'
DATA2 = 'testing...2'
DATA3 = 'testing...3...................'
DATAGRAM1 = Datagram(DATA1, tc.SERVER_ADDR)
DATAGRAM2 = Datagram(DATA2, tc.SERVER2_ADDR)
DATAGRAM3 = Datagram(DATA3, tc.SERVER2_ADDR)

MAIN_LOOP_DELAY = tc.TASK_INTERVAL * 10

class CrashError(Exception):
    'Used to test crashing callbacks'
    pass

class TestMinitwisted:

    def _main_loop(self):
        print 'main loop call'
        self.main_loop_call_counter += 1
        return time.time() + self.main_loop_delay, []

    def _main_loop_return_datagrams(self):
        return time.time() + self.main_loop_delay, [DATAGRAM1]

    def _callback(self, value):
        self.callback_values.append(value)
        return []

    def _very_long_callback(self, value):
        time.sleep(tc.TASK_INTERVAL*11)
        return []

    def _on_datagram_received(self, datagram):
        print 'on_datagram', datagram, datagram.data, datagram.addr
        self.datagrams_received.append(datagram)
        return time.time() + 100, []

    def _crashing_callback(self):
        raise CrashError, 'Crash testing'

    def setup(self):
        time.mock_mode()
        self.main_loop_call_counter = 0
        self.callback_values = []
        self.datagrams_received = []
        
        self.main_loop_delay = MAIN_LOOP_DELAY
        self.reactor = ThreadedReactor(self._main_loop,
                                       tc.CLIENT_PORT,
                                       self._on_datagram_received,
                                       task_interval=tc.TASK_INTERVAL)
        self.reactor.s = _SocketMock()
        #self.reactor.start() >> instead of usint start(), we use run_one_step()

    def test_call_main_loop(self):
        eq_(self.main_loop_call_counter, 0)
        self.reactor.run_one_step()
        # main_loop is called right away
        eq_(self.main_loop_call_counter, 1)
        self.reactor.run_one_step()
        # no events
        eq_(self.main_loop_call_counter, 1)
        time.sleep(self.main_loop_delay)
        self.reactor.run_one_step()
        # main_loop is called again after 
        eq_(self.main_loop_call_counter, 2)
        
    def test_call_asap(self):
        eq_(self.callback_values, [])
        self.reactor.call_asap(self._callback, 0)
        eq_(self.callback_values, []) # stil nothing
        self.reactor.run_one_step()
        eq_(self.callback_values, [0]) #callback triggered
        for i in xrange(1, 5):
            self.reactor.call_asap(self._callback, i)
            self.reactor.run_one_step()
            eq_(self.callback_values, range(i + 1))
    
    def test_minitwisted_crashed(self):
        self.reactor.call_asap(self._crashing_callback)
        assert_raises(CrashError, self.reactor.run_one_step)

    def test_on_datagram_received_callback(self):
        eq_(self.datagrams_received, [])
        self.reactor.run_one_step()
        eq_(self.datagrams_received, [])
        datagram = Datagram(DATA1, tc.SERVER_ADDR)
        # This is equivalent to sending a datagram to reactor
        self.reactor.s.put_datagram_received(datagram)
        self.reactor.run_one_step()
        eq_(len(self.datagrams_received), 1)
        eq_(self.datagrams_received[0], datagram)

    def test_block_flood(self):
        from floodbarrier import MAX_PACKETS_PER_PERIOD as FLOOD_LIMIT
        for _ in xrange(FLOOD_LIMIT * 2):
            self.reactor.s.put_datagram_received(Datagram(DATA1, tc.SERVER_ADDR))
        for i in xrange(FLOOD_LIMIT): 
            eq_(len(self.datagrams_received), i)
            self.reactor.run_one_step()
        eq_(len(self.datagrams_received), FLOOD_LIMIT)
        for i in xrange(FLOOD_LIMIT):
            eq_(len(self.datagrams_received), FLOOD_LIMIT)
            logger.warning(
                "TESTING LOGS ** IGNORE EXPECTED WARNING **")
            self.reactor.run_one_step()
        eq_(len(self.datagrams_received), FLOOD_LIMIT)

    def test_network_and_callback(self):
        self.reactor.call_asap(self._callback, 1)
        eq_(self.main_loop_call_counter, 0)
        eq_(self.callback_values, [])
        time.sleep(.1)
        self.reactor.run_one_step()
        # call_asap and main_loop triggered
        eq_(self.callback_values, [1])
        eq_(self.main_loop_call_counter, 1)

        self.reactor.s.put_datagram_received(DATAGRAM1)
        eq_(self.datagrams_received, [])
        self.reactor.run_one_step()
        eq_(self.datagrams_received, [DATAGRAM1])

        self.reactor.call_asap(self._callback, 2)
        self.reactor.s.put_datagram_received(DATAGRAM3)
        self.reactor.run_one_step() # receive AND call_asap
        eq_(self.datagrams_received, [DATAGRAM1, DATAGRAM3])
        eq_(self.callback_values, [1, 2])

        
    def teardown(self):
        #self.reactor.stop() >> reactor is not really running
        time.normal_mode()


class TestMinitwistedRealThreading:

    def _main_loop(self):
        return time.time() + 1, []

    def _on_datagram_received(self, datagram):
        return time.time() + 1, []
        
    def test_start_and_stop(self):
        '''
        NOTE:
        This is the only test using real threading
        '''
        self.reactor = ThreadedReactor(self._main_loop,
                                       tc.CLIENT_PORT,
                                       self._on_datagram_received,
                                       task_interval=tc.TASK_INTERVAL)
        ok_(not self.reactor.running)
        self.reactor.start()
        time.sleep(.1)
        ok_(self.reactor.running)
        self.reactor.stop()
        ok_(not self.reactor.running)



class TestSend:
    
    def _main_loop(self):
        return time.time() + MAIN_LOOP_DELAY, [DATAGRAM1]

    def _callback(self, value):
        self.callback_values.append(value)
        return [DATAGRAM2]

    def _on_datagram_received(self, datagram):
        self.datagrams_received.append(datagram)
        return time.time() + MAIN_LOOP_DELAY, [DATAGRAM3]

    def _crashing_callback(self):
        raise CrashError, 'Crash testing'

    def setup(self):
        self.main_loop_call_counter = 0
        self.callback_values = []
        self.datagrams_received = []
        
        self.reactor = ThreadedReactor(self._main_loop,
                                       tc.CLIENT_PORT,
                                       self._on_datagram_received,
                                       task_interval=tc.TASK_INTERVAL)
        self.reactor.s = _SocketMock()
        
    def test_main_loop_send_data(self):
        eq_(self.reactor.s.get_datagrams_sent(), [])
        self.reactor.run_one_step()
        # main_loop sends DATAGRAM1
        eq_(self.reactor.s.get_datagrams_sent(), [DATAGRAM1])
    
    def test_call_asap_send_data(self):
        self.reactor.run_one_step()
        eq_(self.reactor.s.get_datagrams_sent(), [DATAGRAM1])
        self.reactor.call_asap(self._callback, 1)
        self.reactor.run_one_step()
        eq_(self.reactor.s.get_datagrams_sent(), [DATAGRAM1, DATAGRAM2])
        
    def test_on_datagram_received_send_data(self): 
        self.reactor.run_one_step()
        eq_(self.reactor.s.get_datagrams_sent(), [DATAGRAM1])
        self.reactor.s.put_datagram_received(Datagram(DATA1, tc.SERVER_ADDR))
        self.reactor.run_one_step()
        eq_(self.reactor.s.get_datagrams_sent(), [DATAGRAM1, DATAGRAM3])
        
    def test_capture(self):
        self.reactor.start_capture()
        ts1 = time.time()
        time.sleep(tc.TASK_INTERVAL/2)
        # out > DATAGRAM1 (main_loop)
        self.reactor.run_one_step()
        ts2 = time.time()
        incoming_datagram = Datagram(DATA1, tc.SERVER_ADDR)
        self.reactor.s.put_datagram_received(incoming_datagram)
        time.sleep(tc.TASK_INTERVAL/2)
        self.reactor.run_one_step() 
        # in < incoming_datagram (socket)
        # out > DATAGRAM3 (on_datagram_received)
        captured_msgs = self.reactor.stop_and_get_capture()

        eq_(len(captured_msgs), 3)
        for msg in  captured_msgs:
            print msg
        assert ts1 < captured_msgs[0][0] < ts2
        eq_(captured_msgs[0][1], tc.SERVER_ADDR)
        eq_(captured_msgs[0][2], True) #outgoing
        eq_(captured_msgs[0][3], DATA1)
        assert captured_msgs[1][0] > ts2
        eq_(captured_msgs[1][1], DATAGRAM1.addr)
        eq_(captured_msgs[1][2], False) #incoming
        eq_(captured_msgs[1][3], DATAGRAM1.data)
        assert captured_msgs[2][0] > captured_msgs[1][0]
        eq_(captured_msgs[2][1], DATAGRAM3.addr)
        eq_(captured_msgs[2][2], True) #outgoing
        eq_(captured_msgs[2][3], DATAGRAM3.data)
        
    def teardown(self):

        return

        
class TestSocketError:

    def _main_loop(self):
        return time.time() + tc.TASK_INTERVAL*10000, [DATAGRAM1]

    def _on_datagram_received(self):
        return
    
    def setup(self):
        self.main_loop_call_counter = 0
        self.callback_values = []
        self.datagrams_received = []
        
        self.reactor = ThreadedReactor(self._main_loop,
                                       tc.CLIENT_PORT,
                                       self._on_datagram_received,
                                       task_interval=tc.TASK_INTERVAL)
        self.reactor.s = _SocketMock()

    def test_socket_error(self):
        self.reactor.s.raise_error_on_next_sendto()
        self.reactor.run_one_step()
        self.reactor.s.raise_error_on_next_recvfrom()
        self.reactor.run_one_step()

    def teardown(self):
        return




class _TestError:

    def _main_loop(self):
        return time.time() + 100, []

    def _very_long_callback(self):
        time.sleep(tc.TASK_INTERVAL*15)
        return time.time() + 100, []

    def _on_datagram_received(self, datagram):
        return time.time() + 100, []

    def _crashing_callback(self):
        raise Exception, 'Crash testing'

    def test_failed_join(self):
        self.lock = threading.RLock()
        self.reactor = ThreadedReactor(self._main_loop,
                                       tc.CLIENT_PORT,
                                       self._on_datagram_received,
                                       task_interval=tc.TASK_INTERVAL)
        self.reactor.s = _SocketMock(tc.TASK_INTERVAL)
#        self.reactor.start()
        self.reactor.call_asap(self._very_long_callback)
        time.sleep(tc.TASK_INTERVAL*2)
        assert_raises(Exception, self.reactor.stop)
    




    
        
class _TestSocketErrors:

    def _main_loop(self): 
        return time.time() + tc.TASK_INTERVAL*10000, []
   
    def _main_loop_send(self):
        self.main_loop_send_called = True
        logger.critical('main loop returns datagram!!!!')
        return time.time() + tc.TASK_INTERVAL*10000, [DATAGRAM1]
   
    def _callback(self, *args, **kwargs):
        self.callback_fired = True

    def _on_datagram_received(self, datagram):
        return time.time() + 100, []

    def setup(self):
        self.main_loop_send_called = False
        self.callback_fired = False
        self.r = ThreadedReactor(self._main_loop_send, tc.CLIENT_PORT,
                                 self._on_datagram_received)
        self.r.s = _SocketErrorMock()
        #self.r.listen_udp(tc.CLIENT_PORT, lambda x,y:None)

    def test_sendto(self):
        logger.critical('TESTING: IGNORE CRITICAL MESSAGE')
        assert not self.main_loop_send_called
#        self.r.start()
        while not self.r.running:
            time.sleep(tc.TASK_INTERVAL)
        while not self.main_loop_send_called:
            time.sleep(tc.TASK_INTERVAL)
        assert self.r.s.error_raised
        assert self.r.running # reactor doesn't crashed

    def _test_recvfrom(self):
        #self.r.start()
        r2 = ThreadedReactor(self._main_loop, tc.CLIENT_PORT,
                             self._on_datagram_received,
                             task_interval=tc.TASK_INTERVAL)
        r2.s = _SocketErrorMock()
        assert not r2.running
#        r2.start()
        assert r2.running
        logger.critical('TESTING: IGNORE CRITICAL MESSAGE')
        # self.r will call recvfrom (which raises socket.error)
        while not r2.s.error_raised:
            time.sleep(tc.TASK_INTERVAL)
        assert r2.running # the error is ignored
        ok_(not self.callback_fired)
#        r2.stop()

    def _test_sendto_too_large_data_string(self):
        logger.critical('TESTING: IGNORE CRITICAL MESSAGE')
        self.r.sendto('z'*12345, tc.NO_ADDR)

    def tear_down(self):
        pass

class _SocketMock(object):

    def __init__(self):
        self.lock = threading.RLock()
        self.datagrams_sent = []
        self.datagrams_received = []
        self.num_send_errors = 0
        self.num_recvfrom_errors = 0
        self.num_recvfrom_timeouts = 0

        self.raise_error_on_sendto = False
        self.raise_error_on_recvfrom = False
        self.raise_timeout = False
        
    def sendto(self, data, addr):
        if self.raise_error_on_sendto:
            self.raise_error_on_sendto = False
            self.num_send_errors += 1
            raise socket.error
        with self.lock:
            self.datagrams_sent.append(Datagram(data, addr))
        return min(20, len(data))
    
    def recvfrom(self, buffer_size):
        datagram_received = None
        if self.raise_error_on_recvfrom:
            self.raise_error_on_recvfrom = False
            self.num_recvfrom_errors += 1
            raise socket.error
        if self.datagrams_received:
            datagram_received = self.datagrams_received.pop(0)
        if datagram_received:
            return (datagram_received.data, datagram_received.addr)
        # nothing to do, raise timeout
        self.raise_timeout_on_next_recvfrom = False
        self.num_recvfrom_timeouts += 1
        raise socket.timeout
        
    def put_datagram_received(self, datagram, delay=0):
        with self.lock:
            self.datagrams_received.append(datagram)

    def get_datagrams_sent(self):
        with self.lock:
            datagrams_sent = [d for d in self.datagrams_sent]
        return datagrams_sent

    def raise_error_on_next_recvfrom(self):
        self.raise_error_on_recvfrom = True

    def raise_timeout_on_next_recvfrom(self):
        self.raise_timeout = True

    def raise_error_on_next_sendto(self):
        self.raise_error_on_sendto = True
    
class _SocketErrorMock(object):

    def __init__(self):
        self.error_raised = False
    
    def sendto(self, data, addr):
        self.error_raised = True
        raise socket.error

    def recvfrom(self, buffer_size):
        self.error_raised = True
        raise socket.error

        
