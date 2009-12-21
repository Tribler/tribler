# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from __future__ import with_statement
import threading
import time

from utils import log

from nose.tools import eq_, ok_, assert_raises
import test_const as tc

from minitwisted import Task, TaskManager, \
     ThreadedReactor, ThreadedReactorMock, \
     ThreadedReactorSocketError


ADDRS= (tc.CLIENT_ADDR, tc.SERVER_ADDR)
DATA = 'testing...'


class TestTaskManager:
    
    def callback_f(self, callback_id):
        self.callback_order.append(callback_id)
        
    def setup(self):
        # Order in which callbacks have been fired
        self.callback_order = []
        self.task_m = TaskManager()

    def test_simple(self):
        for i in xrange(5):
            self.task_m.add(Task(.01, self.callback_f, i))
        while True:
            task = self.task_m.consume_task()
            if task is None:
                break
            task.fire_callback()
        log.debug('%s' % self.callback_order)
        assert self.callback_order == []
        time.sleep(.01)
        while True:
            task = self.task_m.consume_task()
            if task is None:
                break
            task.fire_callbacks() 
        assert self.callback_order == range(5)

    def test_cancel(self):
        for i in xrange(5):
            self.task_m.add(Task(.1, self.callback_f, i))
        c_task = Task(.1, self.callback_f, 5)
        self.task_m.add(c_task)
        for i in xrange(6,10):
            self.task_m.add(Task(.1, self.callback_f, i))
        while True:
            task = self.task_m.consume_task()
            if task is None:
                break
            task.fire_callback()
        log.debug('%s' % self.callback_order)
        assert self.callback_order == []
        ok_(not c_task.cancelled)
        c_task.cancel()
        ok_(c_task.cancelled)
        
        time.sleep(.1)
        while True:
            task = self.task_m.consume_task()
            if task is None:
                break
            task.fire_callbacks()
        log.debug('%s' % self.callback_order)
        assert self.callback_order == [0,1,2,3,4,  6,7,8,9]
        # task 5 was cancelled        

    def test_different_delay(self):
#         NOTICE: this test might fail if your configuration
#         (interpreter/processor) is too slow
        
        task_delays = (1, 1, 1, .5, 1, 1, 2, 1, 1, 1,
                       1, 1.5, 1, 1, 1, 1, .3)
                       
        expected_list = ([],
                         ['a', 16, 3, 'b'], #9 is cancelled
                         ['a', 0, 1, 2, 4, 5, 7, 8, 10, 12, 13, 15, 'c', 'b'],
                         ['a', 11, 'c', 'b'],
                         ['a', 6, 'c', 'b'],
            )
        tasks = [Task(delay, self.callback_f, i) \
                 for i, delay in enumerate(task_delays)]
        for task in tasks:
            self.task_m.add(task)

        for i, expected in enumerate(expected_list):
            while True:
                task = self.task_m.consume_task()
                if task is None:
                    break
                task.fire_callbacks()
            log.debug('#: %d, result: %s, expected: %s' % (i,
                                              self.callback_order, expected))
            assert self.callback_order == expected
            self.callback_order = []
            self.task_m.add(Task(0, self.callback_f, 'a'))
            self.task_m.add(Task(.5, self.callback_f, 'b'))
            self.task_m.add(Task(1, self.callback_f, 'c'))
            time.sleep(.5)
            tasks[9].cancel() # too late (already fired) 
            tasks[14].cancel() # should be cancelled

    def _callback1(self, arg1, arg2):
        if arg1 == 1 and arg2 == 2:
            self.callback_order.append(1)
    def _callback2(self, arg1, arg2):
        if arg1 == 1 and arg2 == 2:
            self.callback_order.append(2)
    
    def test_callback_list(self):
        self.task_m.add(Task(tc.TASK_INTERVAL/2,
                              [self._callback1, self._callback2],
                              1, 2))
        ok_(self.task_m.consume_task() is None)
        eq_(self.callback_order, [])
        time.sleep(tc.TASK_INTERVAL)
        self.task_m.consume_task().fire_callbacks()
        eq_(self.callback_order, [1,2])

class TestMinitwisted:

    def on_datagram_received(self, data, addr):
        with self.lock:
            self.datagrams_received.append((data, addr))

    def callback_f(self, callback_id):
        with self.lock:
            self.callback_order.append(callback_id)
            
    def setup(self):
        self.lock = threading.Lock()
        self.datagrams_received = []
        self.callback_order = []
        self.client_r = ThreadedReactor(task_interval=tc.TASK_INTERVAL)
        self.server_r = ThreadedReactor(task_interval=tc.TASK_INTERVAL)
        self.client_r.listen_udp(tc.CLIENT_ADDR[1], self.on_datagram_received)
        self.server_r.listen_udp(tc.SERVER_ADDR[1], self.on_datagram_received)
        self.client_r.start()
        self.server_r.start()

    def test_listen_upd(self):
        r = ThreadedReactor()
        r.start()
        log.warning(''.join(
            ('TESTING LOGS ** IGNORE EXPECTED WARNING ** ',
             '(udp_listen has not been called)')))
        self.client_r.sendto(DATA, tc.SERVER_ADDR)
        while 1: #waiting for data
            with self.lock:
                if self.datagrams_received:
                    break
            time.sleep(tc.TASK_INTERVAL)
        with self.lock:
            first_datagram = self.datagrams_received.pop(0)
            log.debug('first_datagram: %s, %s' % (
                    first_datagram,
                    (DATA, tc.CLIENT_ADDR)))
            assert first_datagram, (DATA, tc.CLIENT_ADDR)
        r.stop()
            
    def test_network_callback(self):
        self.client_r.sendto(DATA, tc.SERVER_ADDR)
        time.sleep(tc.TASK_INTERVAL)
        with self.lock:
            first_datagram = self.datagrams_received.pop(0)
            log.debug('first_datagram: %s, %s' % (
                    first_datagram,
                    (DATA, tc.CLIENT_ADDR)))
            assert first_datagram, (DATA, tc.CLIENT_ADDR)

    def test_block_flood(self):
        from floodbarrier import MAX_PACKETS_PER_PERIOD as FLOOD_LIMIT
        for _ in xrange(FLOOD_LIMIT):
            self.client_r.sendto(DATA, tc.SERVER_ADDR)
        for _ in xrange(10):
            self.client_r.sendto(DATA, tc.SERVER_ADDR)
            log.warning(
                "TESTING LOGS ** IGNORE EXPECTED WARNING **")
        time.sleep(tc.TASK_INTERVAL)
        with self.lock:
            log.debug('datagram processed: %d/%d' % (
                              len(self.datagrams_received),
                              FLOOD_LIMIT))
            assert len(self.datagrams_received) <= FLOOD_LIMIT

    def test_call_later(self):
        self.client_r.call_later(.13, self.callback_f, 1)
        self.client_r.call_later(.11, self.callback_f, 2)
        self.client_r.call_later(.01, self.callback_f, 3)
        task4 = self.client_r.call_later(.01, self.callback_f, 4)
        task4.cancel()
        time.sleep(.03)
        with self.lock:
            log.debug('callback_order: %s' % self.callback_order)
            assert self.callback_order == [3]
            self.callback_order = []
        self.client_r.call_now(self.callback_f, 5)
        time.sleep(.03)
        with self.lock:
            log.debug('callback_order: %s' % self.callback_order)
            assert self.callback_order == [5]
            self.callback_order = []
        task6 = self.client_r.call_later(.03, self.callback_f, 6)
        task6.cancel()
        time.sleep(.1)
        with self.lock:
            log.debug('callback_order: %s' % self.callback_order)
            assert self.callback_order == [2, 1]

    def test_network_and_delayed(self):
        self.client_r.call_later(.2, self.callback_f, 0)
        self.client_r.call_now(self.callback_f, 1)
        task2 = self.client_r.call_later(.2, self.callback_f, 2)
        with self.lock:
            assert self.callback_order == []
        time.sleep(.1)

        with self.lock:
            log.debug('callback_order: %s' % self.callback_order)
            assert self.callback_order == [1]
            self.callback_order = []
            assert not self.datagrams_received
        self.server_r.sendto(DATA, tc.CLIENT_ADDR)
        time.sleep(.02) # wait for network interruption
        with self.lock:
            log.debug('callback_order: %s' % self.callback_order)
            assert self.callback_order == []
            log.debug('callback_order: %s' % self.callback_order)
            assert self.datagrams_received.pop(0) == (DATA, tc.SERVER_ADDR)
            task2.cancel() #inside critical region??
        time.sleep(.1) # wait for task 0 (task 2 should be cancelled)
        with self.lock:
            assert self.callback_order == [0]
            assert not self.datagrams_received

    def test_sendto_socket_error(self): 
        log.critical('TESTING: IGNORE CRITICAL MESSAGE')
        self.client_r.sendto('z', (tc.NO_ADDR[0], 0))

    def teardown(self):
        self.client_r.stop()
        self.server_r.stop()

class TestSocketErrors:

    def _callback(self, *args, **kwargs):
        self.callback_fired = True
    
    def setup(self):
        self.callback_fired = False
        self.r = ThreadedReactorSocketError()
        self.r.listen_udp(tc.CLIENT_ADDR[1], lambda x,y:None)

    def test_sendto(self):
        log.critical('TESTING: IGNORE CRITICAL MESSAGE')
        self.r.sendto('z', tc.NO_ADDR)

    def test_recvfrom(self):
        self.r.start()
        r2 = ThreadedReactor()
        r2.listen_udp(tc.SERVER_ADDR[1], lambda x,y:None)
        log.critical('TESTING: IGNORE CRITICAL MESSAGE')
        r2.sendto('z', tc.CLIENT_ADDR)
        # self.r will call recvfrom (which raises socket.error)
        time.sleep(tc.TASK_INTERVAL)
        ok_(not self.callback_fired)
        self.r.stop()

    def test_sendto_too_large_data_string(self):
        log.critical('TESTING: IGNORE CRITICAL MESSAGE')
        self.r.sendto('z'*12345, tc.NO_ADDR)
            


        
class TestMockThreadedReactor:

    def setup(self):
        pass

    def _callback(self, *args):
        pass

    def test_mock_threaded_reactor(self):
        '''
        Just making sure that the interface is the same

        '''
        r = ThreadedReactor(task_interval=.1)
        rm = ThreadedReactorMock(task_interval=.1)

        r.listen_udp(tc.CLIENT_ADDR[1], lambda x,y:None)
        rm.listen_udp(tc.CLIENT_ADDR[1], lambda x,y:None)

        r.start()
        rm.start()

        r.sendto(DATA, tc.CLIENT_ADDR)
        rm.sendto(DATA, tc.CLIENT_ADDR)
        
        r.call_later(.1, self._callback)
        rm.call_later(.1, self._callback)
#        time.sleep(.002)
        r.stop()
        rm.stop()
