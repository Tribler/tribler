import asyncio
import functools


async def switch():
    """ Coroutine that yields control to the event loop."""
    await asyncio.sleep(0)


def force_switch(func):
    """Decorator for forced coroutine switch. The switch will occur before calling the function.

    For more information, see the example at the end of this file.
     Also check this: https://stackoverflow.com/questions/59586879/does-await-in-python-yield-to-the-event-loop
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        await switch()
        return await func(*args, **kwargs)

    return wrapper

# the behavior of asyncio without using the force_switch decorator:
#
# import asyncio
#
#
# async def a():
#     async def a_print():
#         print('a')
#
#     while True:
#         await a_print()
#
#
# async def b():
#     async def b_print():
#         print('b')
#
#     while True:
#         await b_print()
#
#
# async def main():
#     tasks = {
#         asyncio.create_task(a()),
#         asyncio.create_task(b())
#     }
#
#     await asyncio.wait(tasks)
#
#
# asyncio.run(main())
#
# -------------------
# the output will be:
# a
# a
# a
# a
# a
# a
# ...
# a
