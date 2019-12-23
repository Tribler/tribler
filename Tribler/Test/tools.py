from asyncio import iscoroutinefunction, wait_for
from functools import wraps


def timeout(timeout):
    def decorator(coro):
        if not iscoroutinefunction(coro):
            raise TypeError('Timeout decorator should be used with coroutine functions only!')

        @wraps(coro)
        async def wrapper(*args, **kwargs):
            await wait_for(coro(*args, **kwargs), timeout)
        return wrapper
    return decorator
