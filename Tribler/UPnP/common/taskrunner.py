# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
The taskrunner module implements a light-weight framework
for asynchronous (delayed) execution of non-blocking Tasks.
"""

__all__ = ['TaskRunner']

import select
import time
import threading
import exceptions

##############################################
# TASK HANDLE
##############################################

class TaskHandle:
    """
    A Task Handle is returned to clients after having
    registered a Task with the TaskRunner.
    
    Its only purpose is to enable clients to cancel a Task,
    without exposing the internal Task objects to clients.
    """
    
    def __init__(self, task_runner, task_id):
        self._task_runner = task_runner
        self.tid = task_id

    def cancel(self):
        """Cancel a Task within the TaskRunner."""
        self._task_runner.cancel_task(self.tid)


##############################################
# TASK
##############################################

class _Task:

    """
    A Task can be executed by the TaskRunner a given number 
    of times.
    
    taskRunner -- reference to TaskRunner object.
    max -- defines the maximum number of executions for a Task. 
    method -- a method object to be executed.
    args -- a tuple containing method arguments.

    If max is -1 this means that the number of executions is unlimited.
    """

    def __init__(self, task_runner, limit, method, args):
        self._counter = 0
        self._cancelled = False
        self._task_runner = task_runner
        self._limit = limit
        self._method = method
        self._args = args
        self.name = method.__name__
        self.tid = None
        self._task_runner.register_task(self) # initialises self.tid
        
    def cancel(self):
        """Causes the Task to never be executed."""
        self._cancelled = True

    def execute(self):
        """Execution of Task"""
        success = self._execute_ok()
        if success:
            self._counter += 1
            self._method(*self._args)
        success = self._execute_ok()
        if not success:
            self._task_runner.cancel_task(self.tid)
        return success

    def _execute_ok(self):
        """Checks if Task may be executed on more time. Returns bool."""
        if self._cancelled : 
            return False
        elif (self._limit == TaskRunner.TASK_NO_LIMIT): 
            return True
        elif (self._counter + 1 <= self._limit): 
            return True
        return False    

    def __str__(self):
        if self._limit == TaskRunner.TASK_NO_LIMIT:
            return "%s [%s] %s[%s/INF]" % (self.__class__.__name__, 
                                             self.tid, self.name, self._counter)
        else:
            return "%s [%d] %s [%d/%d]" % (self.__class__.__name__, 
                                            self.tid, self.name, 
                                            self._counter, self._limit) 


        
##############################################
# READ TASK
##############################################

class _ReadTask(_Task):

    """
    A ReadTask is executed after its associated filedescriptor
    has become readable.
    """
    def __init__(self, task_runner, limit, file_descriptor, method, args):
        _Task.__init__(self, task_runner, limit, method, args)
        self._file_descriptor = file_descriptor
        self._task_runner.enter_rd_set(self)
    def fileno(self):
        """Return file descriptor of IoTask."""
        return self._file_descriptor
    def cancel(self):
        """Cancel ReadTask."""
        self._task_runner.leave_rd_set(self) 
        _Task.cancel(self)

##############################################
# WRITE TASK
##############################################

class _WriteTask(_Task):

    """
    A WriteTask is executed after its associated filedescriptor
    has become writeable.
    """
    def __init__(self, task_runner, limit, file_descriptor, method, args):
        _Task.__init__(self, task_runner, limit, method, args)
        self._file_descriptor = file_descriptor
        self._task_runner.enter_wr_set(self)
    def fileno(self):
        """Return file descriptor of IoTask."""
        return self._file_descriptor
    def cancel(self):
        """Cancel WriteTask."""
        self._task_runner.leave_wr_set(self)
        _Task.cancel(self)


##############################################
# DELAY TASK
##############################################

class _DelayTask(_Task):

    """
    Delay Task are to be executed at a given point in time.

    limit -- max number of executions
    delay -- amount of time from now to expiry
    period -- interval between executions
    """

    def __init__(self, task_runner, limit, delay, period, method, args):
        _Task.__init__(self, task_runner, limit, method, args)
        self._created = time.time()
        self._delay = delay
        self._period = period
        self.register_timeout()

    def execute(self):
        """Overrides execute to register a new timeout just after the
        execution."""
        success = _Task.execute(self)
        if success:
            self.register_timeout()
        return success

    def register_timeout(self):
        """Register a new timeout with task_runner."""
        expiry = self._created + self._delay + self._counter*self._period 
        self._task_runner.register_timeout(expiry, self)
            


##############################################
# TIMEOUT
##############################################

class _Timeout:
    
    """
    A Timeout represents a point in time where the
    attached Task is due for execution.
    
    expiry -- absolute point in time ( time.time() )
    task -- the Task
    """

    def __init__(self, expiry, task):
        self.expiry = expiry
        self.task = task
    def __eq__(self, other):
        return self.expiry == other.expiry
    def __lt__(self, other):
        return self.expiry < other.expiry
    def __gt__(self, other):
        return self.expiry > other.expiry
    def __le__(self, other):
        return self.expiry <= other.expiry
    def __ge__(self, other):
        return self.expiry >= other.expiry
    def __ne__(self, other):
        return self.expiry != other.expiry

##############################################
# DELAY TASK HEAP
##############################################

import heapq

class _DelayTaskHeap:

    """
    Heap of Timeouts. Timeouts are kept sorted with respect to
    expiry. Next Timeout first.
    """

    def __init__(self):
        self._array = []

    def push(self, expiry, task):
        """Register a timeout for Task."""
        timeout = _Timeout(expiry, task)
        heapq.heappush(self._array, timeout)

    def poll(self):
        """Polls the TimeoutHeap to see if any Delayed Tasks
        are due for execution."""
        task_list = []
        time_stamp = time.time()
        while self._array and self._array[0].expiry < time_stamp:
            timeout = heapq.heappop(self._array)
            task_list.append(timeout.task)
        return task_list

##############################################
# TASK RUNNER ERROR
##############################################

class TaskRunnerError (exceptions.Exception): 
    """Error associated with running the TaskRunner. """
    pass


##############################################
# TASK RUNNER
##############################################

class TaskRunner:

    """
    TaskRunner runs Tasks asynchronously (delayed).
    
    It supports four types of Tasks.
    Task -- simple task for immediate execution.
    ReadTask -- Task to be executed after its file descriptor became readable.
    WriteTask -- Task to be executed after its file descriptor became writeable.
    DelayTask -- Task to be executed at one (or multiple) specified points in time.
    """

    TASK_NO_LIMIT = -1

    def __init__(self):
        # Read Set
        self._rd_set = []
        # Write Set
        self._wr_set = []
        # Timeout Heap
        self._delay_task_heap = _DelayTaskHeap()
        # TaskQueue
        self._task_queue = []
        # Stop Flag
        self._internal_stop_event = threading.Event()
        self._external_stop_event = None
        # Task ID
        self._task_id = 0L
        # Task Map
        self._task_map = {}
        # Task Runner Lock protecting critical sections.
        # Conservative locking is implemented, using only
        # one lock for all critical sections. 
        self._lock = threading.Lock()
        # Bad filedescriptor exists in read and/or writeset
        self._bad_fd = False

    ##############################################
    # UTILITY (Used only by internal Tasks)
    ##############################################

    def enter_rd_set(self, io_task):
        """Add filedescriptor of IoTask to read set."""
        if not io_task in self._rd_set:
            self._rd_set.append(io_task)
            return True
        else : return False

    def leave_rd_set(self, io_task):
        """Remove filedescriptor of IoTask from read set."""
        if io_task in self._rd_set:
            self._rd_set.remove(io_task)
            return True
        else : return False

    def enter_wr_set(self, io_task):
        """Add filedescriptor of IoTask to write set."""
        if not io_task in self._wr_set:
            self._wr_set.append(io_task)
            return True
        else : return False

    def leave_wr_set(self, io_task):
        """Remove filedescriptor of IoTask from write set."""
        if io_task in self._wr_set:
            self._wr_set.remove(io_task)
            return True
        else : return False

    def register_timeout(self, expiry, task):
        """Register a Timeout for a Delayed Task."""
        self._delay_task_heap.push(expiry, task)

    def register_task(self, task):
        """Stores reference to Task internally."""
        self._task_id += 1
        task.tid = self._task_id
        self._task_map[self._task_id] = task
        return task.tid


    ##############################################
    # PUBLIC API
    ##############################################

    def add_task(self, method, args=()):
        """Add Task. Returns TaskHandle."""
        self._lock.acquire()
        task = _Task(self, 1, method, args)
        self._task_queue.append(task)
        handle = TaskHandle(self, task.tid)
        self._lock.release()
        return handle

    def add_read_task(self, file_descriptor, method, args=()):
        """Add Read Task. Returns TaskHandle."""
        self._lock.acquire()
        task = _ReadTask(self, TaskRunner.TASK_NO_LIMIT, 
                         file_descriptor, method, args)
        handle = TaskHandle(self, task.tid)
        self._lock.release()
        return handle

    def add_write_task(self, file_descriptor, method, args=()):
        """Add Write Taks. Returns TaskHandle."""
        self._lock.acquire()
        task = _WriteTask(self, TaskRunner.TASK_NO_LIMIT, 
                          file_descriptor, method, args)
        handle = TaskHandle(self, task.tid)
        self._lock.release()
        return handle

    def add_delay_task(self, delay, method, args=()):
        """Add Delay Task. Returns TaskHandle."""
        self._lock.acquire()
        task = _DelayTask(self, 1, delay, 0, method, args)
        handle = TaskHandle(self, task.tid)
        self._lock.release()
        return handle

    def add_periodic_task(self, period, method, args=(), 
                          delay=0, limit=None):
        """Add Periodic Task. Returns TaskHandle."""
        if limit == None: 
            limit = TaskRunner.TASK_NO_LIMIT
        self._lock.acquire()
        task = _DelayTask(self, limit, delay, period, method, args)
        handle = TaskHandle(self, task.tid)
        self._lock.release()
        return handle

    def cancel_task(self, task_id):
        """
        Causes Task to be invalidated so that it 
        will not be exectuted.
        """
        self._lock.acquire()
        task = self._task_map.get(task_id, None)
        if task:
            task.cancel()
            del self._task_map[task.tid]
        self._lock.release()


    ##############################################
    # EXECUTION API
    ##############################################
        
    def run_forever(self, frequency=.1, stop_event=None):
        """Run the TaskRunner until it is stopped."""
        self._external_stop_event = stop_event
        while not self.is_stopped():
            self.run_once(frequency)

    def run_batch(self, limit=None, timeout=0):
        """
        Run the TaskRunner until it has got no more to do, or limit is reached.
        timeout -- if no tasks are available immediately, block max timeout seconds
        limit -- maximum number of tasks to execute (limit >= 1, None means no limit)
        """
        if limit <= 0:
            limit = 1
        count = 0
        did_something = True
        while not self.is_stopped() and did_something:
            if count == 0:
                did_something = self.run_once(timeout=timeout)
            else:
                did_something = self.run_once(timeout=0)
            if did_something:
                count += 1
                if limit != None and count >= limit:
                    return

    def is_stopped(self):
        """Returns true if the TaskRunner has been requested to stop."""
        if self._internal_stop_event.is_set(): 
            return True
        if self._external_stop_event != None:
            if self._external_stop_event.is_set():
                return True
        return False

    def run_once(self, timeout=0):
        """Run at most a single Task within the TaskRunner."""

        if self.is_stopped(): 
            return False

        self._lock.acquire()

        # Poll Timeouts
        if not self._task_queue:
            d_list = self._delay_task_heap.poll()
            if d_list: 
                self._task_queue += d_list

        # Poll File Descriptors
        if not self._task_queue:
            # release lock before potentially blocking on select.
            self._lock.release()
            try:
                lists = select.select(self._rd_set, self._wr_set, 
                                      self._rd_set + self._wr_set, timeout)
            except select.error:
                # A bad file descriptor in readset and/or writeset
                # This could happen if a read/write task is cancelled
                # from another thread - and then the socket is closed
                # immediately afterwards. This only-once type of error 
                # can safely be ignored.
                # However, if a socket is closed but the task is not cancelled,
                # this is an error, and the programmer should be signaled.
                if self._bad_fd == True:
                    msg = "Read/Write Task with Bad File Descriptor."
                    raise TaskRunnerError, msg
                self._bad_fd = True
                return False
            else:
                # Reset bad_fd flag is no error occured.
                self._bad_fd = False


            r_list, w_list, e_list = lists
            if e_list: 
                for task in e_list:
                    print "Error", task
                    self.cancel_task(task.tid)

            self._lock.acquire()
            if r_list: 
                self._task_queue += r_list
            if w_list: 
                self._task_queue += w_list
        
        # Execute at most one Task
        if self._task_queue:
            task = self._task_queue.pop(0)
            # Release lock before executing a task.
            self._lock.release() 
            return task.execute()
        else:
            self._lock.release()
            return False
        
    def stop(self):
        """Requests that the TaskRunner stops itself."""
        self._internal_stop_event.set()


##############################################
# MAIN
##############################################

if __name__ == '__main__':

    def tick(): 
        """Tick Task."""
        print "Tick", time.time()

    def tack():
        """Tack Task.""" 
        print "Tack", time.time()

    def tock(): 
        """Tock Task."""
        print "Tock", time.time()

    TASK_RUNNER = TaskRunner()
    TASK_RUNNER.add_periodic_task(1, tick)
    TASK_RUNNER.add_delay_task(2, tack)
    TASK_RUNNER.add_periodic_task(3, tock, delay=.5, limit=4)
    try:
        TASK_RUNNER.run_forever()
    except KeyboardInterrupt:
        pass
