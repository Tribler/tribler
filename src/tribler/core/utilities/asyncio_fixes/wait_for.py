import asyncio
import asyncio.tasks
import functools
import logging
import sys
import warnings
from asyncio import ensure_future, events, exceptions

logger = logging.getLogger(__name__)


def base_lost_result_handler(task_result):
    # It is possible for the task inside wait_for to return an object that require closing, such as a connection.
    # In a race condition situation when the task is done, but the wait_for coroutine is cancelled from the outside,
    # the task result is lost. This handler allows to gracefully close the object that requires it.
    # You have two possible ways how to close an object in that case:
    #
    #   1. You can use a `lost_task_result_handler` keyword argument to pass a custom handler to a specific
    #      wait_for() call;
    #
    #   2. You can override this top-level handler and add a generic code for closing the lost objects by type:
    #
    #        if isinstance(task_result, MyConnectionType):
    #            task_result.close
    #
    #      It may be useful to close objects that are created in some library outside the Tribler code
    #
    # The default handler behavior is to report the lost object to the log

    if task_result is not None:
        logger.error(f"The result of the task was lost: {task_result.__class__.__name__}: {task_result!r}")


async def _cancel_and_wait(fut, loop):
    """Cancel the *fut* future or task and wait until it completes."""

    waiter = loop.create_future()
    cb = functools.partial(_release_waiter, waiter)
    fut.add_done_callback(cb)

    try:
        fut.cancel()
        # We cannot wait on *fut* directly to make
        # sure _cancel_and_wait itself is reliably cancellable.
        await waiter
    finally:
        fut.remove_done_callback(cb)


def _release_waiter(waiter, *args):
    if not waiter.done():
        waiter.set_result(None)


async def wait_for(fut, timeout, *, loop=None, lost_result_handler=None):
    """Wait for the single Future or coroutine to complete, with timeout.

    Coroutine will be wrapped in Task.

    Returns result of the Future or coroutine.  When a timeout occurs,
    it cancels the task and raises TimeoutError.  To avoid the task
    cancellation, wrap it in shield().

    If the wait is cancelled, the task is also cancelled.

    This function is a coroutine.
    """
    if loop is None:
        loop = events.get_running_loop()
    else:
        warnings.warn("The loop argument is deprecated since Python 3.8, "
                      "and scheduled for removal in Python 3.10.",
                      DeprecationWarning, stacklevel=2)

    if timeout is None:
        return await fut

    fut = ensure_future(fut, loop=loop)
    if timeout <= 0:
        if fut.done():
            return fut.result()

        await _cancel_and_wait(fut, loop=loop)
        try:
            return fut.result()
        except exceptions.CancelledError as exc:
            raise exceptions.TimeoutError() from exc

    waiter = loop.create_future()
    timeout_handle = loop.call_later(timeout, _release_waiter, waiter)
    cb = functools.partial(_release_waiter, waiter)

    fut.add_done_callback(cb)

    try:
        # wait until the future completes or the timeout
        try:
            await waiter
        except exceptions.CancelledError:
            if fut.done():
                # ******************* START OF THE FIX ***************************************
                # return fut.result() - it was incorrect, as it swallowed CancelledError
                if fut.exception() is None:  # can raise another CancelledError, but that's OK
                    handler = lost_result_handler or base_lost_result_handler
                    handler(fut.result())
                raise
                # ******************* END OF THE FIX *****************************************

            fut.remove_done_callback(cb)
            # We must ensure that the task is not running
            # after wait_for() returns.
            # See https://bugs.python.org/issue32751
            await _cancel_and_wait(fut, loop=loop)
            raise

        if fut.done():  # pylint: disable=no-else-return
            return fut.result()
        else:
            fut.remove_done_callback(cb)
            # We must ensure that the task is not running
            # after wait_for() returns.
            # See https://bugs.python.org/issue32751
            await _cancel_and_wait(fut, loop=loop)
            # In case task cancellation failed with some
            # exception, we should re-raise it
            # See https://bugs.python.org/issue40607
            try:
                return fut.result()
            except exceptions.CancelledError as exc:
                raise exceptions.TimeoutError() from exc
    finally:
        timeout_handle.cancel()


wait_for.patched = True


def patch_wait_for():
    """ Patch asyncio.wait_for to fix the bug with swallowing CancelledError
    See: https://github.com/Tribler/tribler/issues/7570
    """
    if sys.version_info >= (3, 12):
        return  # wait_for should be fixed in 3.12

    if getattr(asyncio.wait_for, 'patched', False):
        return  # the patch was already applied

    asyncio.wait_for = asyncio.tasks.wait_for = wait_for
