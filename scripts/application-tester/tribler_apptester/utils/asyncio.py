from asyncio import Future, iscoroutine, sleep


def maybe_coroutine(func, *args, **kwargs):
    value = func(*args, **kwargs)
    if iscoroutine(value) or isinstance(value, Future):
        return value

    async def coro():
        return value
    return coro()


async def looping_call(delay, interval, task, *args):
    await sleep(delay)
    while True:
        await maybe_coroutine(task, *args)
        await sleep(interval)
